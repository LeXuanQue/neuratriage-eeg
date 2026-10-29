"""POST /api/infer (port from api/index.py:276-361).

Offline inference on an uploaded file ID or an allow-listed replay case.
Loads the trained model on first call via ModelManager and feeds the EEG
record through run_offline_inference().
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional

import eeg_stroke_pipeline as pipeline
from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel

from ..auth import DemoUser
from ..config import get_settings
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..services.model_manager import get_manager
from ..services.rate_limit import infer_limiter


router = APIRouter(prefix="/api", tags=["inference"])


def _num(value: object, default: Optional[float] = None) -> Optional[float]:
    """Coerce to a finite float; return ``default`` for None/NaN/inf/non-numeric.

    Window probabilities and SQI are NaN for SQI-gated windows. A frame that is
    entirely gated would otherwise produce NaN aggregates, which serialise as the
    invalid JSON token ``NaN`` and break the client.
    """
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


class InferRequest(BaseModel):
    upload_id: Optional[str] = None
    case_id: Optional[str] = None
    # Development-only compatibility with the old workbench flow. The
    # production demo UI sends upload_id/case_id instead of raw server paths.
    eeg_path: Optional[str] = None
    patient_id: str = "unknown"
    label: str = "non-stroke"
    max_duration_sec: Optional[float] = 30.0


def _ensure_model_loaded() -> str:
    mgr = get_manager()
    if mgr.is_loaded:
        return mgr.model_path or ""
    settings = get_settings()
    found = mgr.auto_load(settings.candidate_model_paths())
    if not found:
        raise EnvelopeError(
            "No trained model found. Run training or load a model first.",
            "NO_MODEL",
            503,
        )
    return found


def _resolve_infer_path(body: InferRequest) -> Path:
    from ..config import REPO_ROOT, UPLOAD_DIR
    from ..services.replay_cases import resolve_replay_case, resolve_uploaded_file

    if body.upload_id:
        path = resolve_uploaded_file(body.upload_id)
        if path:
            return path
        raise EnvelopeError(
            f"Uploaded EEG file not found: {body.upload_id}",
            "UPLOAD_NOT_FOUND",
            404,
        )

    if body.case_id:
        path = resolve_replay_case(body.case_id)
        if path:
            return path
        raise EnvelopeError(
            f"Replay case not found: {body.case_id}",
            "CASE_NOT_FOUND",
            404,
        )

    settings = get_settings()
    if settings.app_env.lower() == "development" and body.eeg_path:
        path = Path(body.eeg_path).resolve()
        allowed_roots = [
            UPLOAD_DIR.resolve(),
            (REPO_ROOT / "dataset_real").resolve(),
            (REPO_ROOT / "dataset_ischemic").resolve(),
            (REPO_ROOT / "dataset_healthy").resolve(),
            (REPO_ROOT / "dataset_npz").resolve(),
        ]
        if path.is_file() and any(path.is_relative_to(root) for root in allowed_roots):
            return path
        raise EnvelopeError(
            "Development eeg_path must point to an allow-listed project data folder.",
            "PATH_NOT_ALLOWED",
            403,
        )

    raise EnvelopeError("Provide upload_id or case_id.", "MISSING_EEG_SOURCE", 422)


@router.post("/reload-model")
def reload_model(
    _: DemoUser = Depends(get_current_user),
):
    """Force-reload the model from disk (picks up a newly trained model)."""
    mgr = get_manager()
    settings = get_settings()
    candidates = settings.candidate_model_paths()
    mgr.reset()
    found = mgr.auto_load(candidates)
    if not found:
        raise EnvelopeError("No trained model found on disk.", "NO_MODEL", 503)
    return ok({"loaded": found, "features": len(mgr.get_model().feature_names)})


@router.post("/infer")
def infer(
    request: Request,
    body: InferRequest = Body(...),
    _: DemoUser = Depends(get_current_user),
    _rl: None = Depends(infer_limiter),
):
    eeg_path = _resolve_infer_path(body)

    model_path = _ensure_model_loaded()
    trained = get_manager().get_model()

    try:
        try:
            cfg = pipeline.PipelineConfig(**trained.config)
        except TypeError:
            # A model saved by a different pipeline version may carry config
            # keys this PipelineConfig no longer accepts. Filter to known fields.
            _allowed = set(pipeline.PipelineConfig().__dict__.keys())
            cfg = pipeline.PipelineConfig(
                **{k: v for k, v in trained.config.items() if k in _allowed}
            )
        data, channels, fs_file = pipeline.load_array_file(str(eeg_path))
        source_channel_count = len(channels)
        source_sample_count = int(data.shape[1]) if getattr(data, "ndim", 0) == 2 else 0
        source_fs = float(fs_file or cfg.fs)
        analysis_sample_count = source_sample_count
        if body.max_duration_sec and body.max_duration_sec > 0 and source_sample_count:
            max_samples = max(1, int(round(float(body.max_duration_sec) * source_fs)))
            if data.shape[1] > max_samples:
                data = data[:, :max_samples]
                analysis_sample_count = int(data.shape[1])
        record = pipeline.EEGRecord(
            patient_id=body.patient_id,
            label=pipeline.parse_label(body.label),
            data=pipeline.reorder_to_target_channels(data, channels, cfg.channels),
            channels=list(cfg.channels),
            fs=source_fs,
        )
        frame = pipeline.run_offline_inference(trained, record, cfg)
    except Exception as exc:
        raise EnvelopeError(str(exc), "INFER_ERROR", 500)

    if frame.empty:
        raise EnvelopeError(
            "No windows produced — check signal length and SQI threshold.",
            "NO_WINDOWS",
        )

    last = frame.tail(1).iloc[0]
    timeline: List[dict] = []
    for i, (_idx, row) in enumerate(frame.iterrows()):
        timeline.append(
            {
                "t": _num(row.get("t_end_sec"), float(i)),
                "NS": _num(row.get("p_nonstroke_smooth"), 0.0),
                "IS": _num(row.get("p_ischemic_smooth"), 0.0),
                "sqi": _num(row.get("sqi_total"), 0.0),
                "cls": str(row.get("pred_class", "")),
            }
        )

    # "no-decision" windows (SQI-gated) are not a class prediction — exclude
    # them from the majority vote so a noisy recording can't mask a real class.
    mean_ns = _num(frame["p_nonstroke_smooth"].mean(), 0.0) or 0.0
    mean_is = _num(frame["p_ischemic_smooth"].mean(), 0.0) or 0.0
    overall_class: Optional[str] = "ischemic" if mean_is >= mean_ns else "non-stroke"
    latest_ns = _num(last.get("p_nonstroke_smooth"), 0.0) or 0.0
    latest_is = _num(last.get("p_ischemic_smooth"), 0.0) or 0.0
    latest_class = "ischemic" if latest_is >= latest_ns else "non-stroke"

    return ok(
        {
            "windows": len(frame),
            "model": model_path,
            "source": {
                "upload_id": body.upload_id,
                "case_id": body.case_id,
                "mode": "uploaded_file" if body.upload_id else "replay_case" if body.case_id else "development_path",
                "channels": list(channels),
                "channel_count": source_channel_count,
                "fs": source_fs,
                "sample_count": source_sample_count,
                "duration_sec": source_sample_count / source_fs if source_fs else None,
                "analysis_sample_count": analysis_sample_count,
                "analysis_duration_sec": analysis_sample_count / source_fs if source_fs else None,
                "preview_limited": analysis_sample_count < source_sample_count,
            },
            "overall": {
                "pred_class": overall_class,
                "p_nonstroke": mean_ns,
                "p_ischemic": mean_is,
                "sqi": _num(frame["sqi_total"].mean()),
            },
            "latest": {
                "t_end_sec": _num(last.get("t_end_sec"), 0.0),
                "pred_class": latest_class,
                "sqi": _num(last.get("sqi_total")),
                "p_nonstroke": latest_ns,
                "p_ischemic": latest_is,
            },
            "timeline": timeline,
        }
    )
