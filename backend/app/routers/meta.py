"""GET /api/health, GET /api/disclaimer (port from api/index.py:148-161)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends

from ..config import REPO_ROOT, get_settings
from ..deps import get_current_user
from ..envelope import ok
from ..services.model_manager import ModelManager


router = APIRouter(prefix="/api", tags=["meta"])


def _eye_matched_aucs(meta: dict) -> list[float]:
    """Held-out patient AUCs where the control test set was eyes-OPEN (matched to the
    eyes-open stroke recordings) — the honest number after the eye-state control."""
    rows = (meta.get("heldout_patient_auc") or {}).get("eyes") or []
    return [float(r["patient_auc"]) for r in rows if "physionet_eo" in (r.get("test") or [])]


def _riemann_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"file": path.name, "available": False}
    try:
        meta: Optional[dict] = ModelManager.get().peek_window_model_metadata(path)
    except Exception as exc:  # unreadable file: report it, never break the page
        info["error"] = type(exc).__name__
        return info
    if meta is None:
        return info
    info.update(
        available=True,
        created=meta.get("created"),
        train_sources=meta.get("train_sources") or {},
        eye_matched_patient_auc=_eye_matched_aucs(meta),
        intended_use=meta.get("intended_use"),
        known_limits=list(meta.get("known_limits") or []),
    )
    return info


@router.get("/model/info")
def model_info(_=Depends(get_current_user)):
    """Which real-time scorer is active, and what is honestly known about it."""
    s = get_settings()
    mgr = ModelManager.get()
    feature_path = mgr.model_path
    feature: dict[str, Any] = {
        "loaded": mgr.is_loaded,
        "file": Path(feature_path).name if feature_path else None,
        "n_features": len(mgr.get_model().feature_names) if mgr.is_loaded else None,
    }
    return ok(
        {
            "realtime_model": s.realtime_model.strip().lower(),
            "feature_model": feature,
            "riemann": _riemann_info(REPO_ROOT / s.riemann_model_path),
            "clinical_use": False,
        }
    )


@router.get("/health")
def health():
    s = get_settings()
    return ok({"status": "ok", "app": s.app_name, "version": s.app_version})


@router.get("/disclaimer")
def disclaimer():
    return ok(
        {
            "text": (
                "For research use only. Not validated for clinical diagnosis. "
                "Always consult a qualified physician for any medical decisions."
            ),
            "version": "1.0",
        }
    )
