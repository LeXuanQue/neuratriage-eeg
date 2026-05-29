"""WebSocket /ws/stream/{session_id} — real-time EEG inference.

Protocol (Master Prompt §4):

  Client → Server:
    {"type": "init", "device_type": "...", "device_channels": [...], "fs": 256}
    {"type": "data", "chunk": [[...], [...], ...]}
    {"type": "close"}

  Server → Client:
    {"type": "ready", "session_id": "...", "mapped_channels": [...]}
    {"type": "event", "timestamp_sec": 1.5, "status": "monitor"|"alert-enter"|...,
     "predicted_class": "non-stroke"|"ischemic"|"hemorrhagic"|null,
     "probabilities_smooth": [p_ns, p_is, p_hs],
     "sqi_total": 0.82, "alert_class": "ischemic"|null}
    {"type": "error", "message": "..."}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from eeg_stroke_pipeline import DEFAULT_CHANNELS
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from ..database import SessionLocal
from ..models import Alert, EEGSession
from ..auth import decode_token, find_user_by_id
from ..services.channel_mapper import DEVICE_PRESETS, map_to_pipeline
from ..services.model_manager import get_manager
from ..services.replay_cases import resolve_replay_case
from ..services.session_manager import get_session_manager


logger = logging.getLogger("neuratriage.ws")

router = APIRouter()

ALERT_ENTRY_STATUSES = {"alert-enter", "alert-switch"}


def _ensure_session_row(
    session_id: str,
    device_channels: List[str],
    fs: float,
    patient_id: Optional[str] = None,
) -> None:
    """Create or refresh the EEGSession row when WS init lands.

    Without this, the dashboard wouldn't see an "active session" until the
    first alert. Idempotent — safe to call repeatedly with the same id.
    """
    try:
        with SessionLocal() as db:
            row = db.execute(
                select(EEGSession).where(EEGSession.id == session_id)
            ).scalar_one_or_none()
            if row is None:
                row = EEGSession(
                    id=session_id,
                    device_channels=list(device_channels),
                    fs=float(fs),
                    patient_id=patient_id,
                )
                db.add(row)
            else:
                row.device_channels = list(device_channels)
                row.fs = float(fs)
                row.ended_at = None
                if patient_id and not row.patient_id:
                    row.patient_id = patient_id
            db.commit()
    except Exception:
        logger.exception("Failed to upsert session row %s", session_id)


def _persist_alert(session_id: str, event: Dict[str, Any]) -> None:
    """Insert an Alert row for an alert-enter/alert-switch event.

    Best-effort: any DB error is logged and swallowed so the WS keeps streaming.
    """
    try:
        with SessionLocal() as db:
            sess_row = db.execute(
                select(EEGSession).where(EEGSession.id == session_id)
            ).scalar_one_or_none()
            if sess_row is None:
                sess_row = EEGSession(id=session_id)
                db.add(sess_row)
                db.flush()

            alert_class = (event.get("alert_class") or "").lower()
            alert = Alert(
                session_id=session_id,
                patient_id=sess_row.patient_id,
                timestamp_sec=float(event.get("timestamp_sec") or 0.0),
                alert_class=alert_class,
                status=str(event.get("status") or ""),
                probabilities_smooth=event.get("probabilities_smooth"),
                sqi_total=event.get("sqi_total"),
            )
            db.add(alert)
            sess_row.alert_count = (sess_row.alert_count or 0) + 1
            db.commit()
    except Exception:
        logger.exception("Failed to persist alert for session %s", session_id)


def _finalise_session_row(
    session_id: str,
    total_windows: int,
    valid_windows: int,
    sqi_sum: float,
) -> None:
    """On WS close, write aggregate counters back to the EEGSession row."""
    try:
        with SessionLocal() as db:
            row = db.execute(
                select(EEGSession).where(EEGSession.id == session_id)
            ).scalar_one_or_none()
            if row is None:
                return
            row.total_windows = (row.total_windows or 0) + total_windows
            row.valid_windows = (row.valid_windows or 0) + valid_windows
            if valid_windows > 0:
                row.sqi_mean = sqi_sum / valid_windows
            if row.ended_at is None:
                now = datetime.now(timezone.utc)
                row.ended_at = now
                started = row.started_at or now
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                row.duration_sec = (now - started).total_seconds()
            db.commit()
    except Exception:
        logger.exception("Failed to finalise session row %s", session_id)


def _authenticate_ws(ws: WebSocket) -> bool:
    token = ws.query_params.get("token", "")
    if not token:
        auth = ws.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return False
    try:
        payload = decode_token(token)
    except Exception:
        return False
    return find_user_by_id(str(payload.get("sub", ""))) is not None


def _load_replay_data(path: Path) -> tuple[np.ndarray, List[str], float]:
    """Load replay EEG exactly as recorded in the source file.

    The UI should show only channels that exist in the replay/device source.
    Mapping/imputation to the pipeline's standard layout happens later and is
    used only for detector input.
    """
    with np.load(str(path), allow_pickle=True) as npz:
        if "data" in npz.files:
            data = np.asarray(npz["data"], dtype=float)
        elif "eeg" in npz.files:
            data = np.asarray(npz["eeg"], dtype=float)
        else:
            data = np.asarray(npz[npz.files[0]], dtype=float)
        channels = (
            [str(c) for c in npz["channels"]] if "channels" in npz.files else list(DEFAULT_CHANNELS)
        )
        fs = float(npz["fs"]) if "fs" in npz.files else 256.0
    return data, channels, fs


async def _run_replay(
    ws: WebSocket,
    session_id: str,
    npz_path: Path,
    counters: Dict[str, float],
    chunk_seconds: float = 0.5,
    realtime: bool = True,
) -> None:
    """Server-driven replay: read a stored .npz and stream chunks through
    the detector at (optionally) real-time pace.

    Counters dict is updated in-place with total_windows/valid_windows/sqi_sum
    so the WS handler's `finally` block can persist final session stats.
    """
    sm = get_session_manager()
    detector = sm.get_session(session_id)
    if detector is None:
        await ws.send_json({"type": "error", "message": "Replay: session not initialised"})
        return

    try:
        data, replay_channels, fs = _load_replay_data(npz_path)
    except Exception as exc:
        await ws.send_json({"type": "error", "message": f"Replay load failed: {exc}"})
        return

    chunk_samples = max(1, int(round(chunk_seconds * fs)))
    n_total = data.shape[1]
    pos = 0
    while pos < n_total:
        chunk = data[:, pos : pos + chunk_samples]
        pos += chunk_samples
        try:
            await ws.send_json(
                {
                    "type": "raw_chunk",
                    "chunk": chunk.tolist(),
                    "device_channels": replay_channels,
                    "fs": fs,
                }
            )
        except Exception:
            return
        try:
            loop = asyncio.get_event_loop()
            mapped, _ = map_to_pipeline(chunk, replay_channels, fs=fs)
            events = await loop.run_in_executor(None, detector.update, mapped)
        except Exception as exc:
            logger.exception("Replay detector failed for %s", session_id)
            await ws.send_json({"type": "error", "message": str(exc)})
            return
        for event in events:
            counters["total_windows"] = counters.get("total_windows", 0) + 1
            sqi = event.get("sqi_total")
            if event.get("status") != "no-decision" and sqi is not None:
                counters["valid_windows"] = counters.get("valid_windows", 0) + 1
                counters["sqi_sum"] = counters.get("sqi_sum", 0.0) + float(sqi)
            if event.get("status") in ALERT_ENTRY_STATUSES:
                _persist_alert(session_id, event)
            try:
                await ws.send_json(_serializable_event(event))
            except Exception:
                return  # client disconnected
        if realtime:
            await asyncio.sleep(chunk_seconds)

    try:
        await ws.send_json({"type": "replay_done"})
    except Exception:
        pass


def _resolve_init_channels(init_msg: Dict[str, Any]) -> tuple[List[str], float]:
    explicit = init_msg.get("device_channels")
    fs = float(init_msg.get("fs", 256.0) or 256.0)
    if explicit:
        return list(explicit), fs
    device_type = str(init_msg.get("device_type", "full_18ch"))
    preset = DEVICE_PRESETS.get(device_type)
    if not preset:
        raise ValueError(f"Unknown device_type '{device_type}'")
    channels = list(preset["channels"]) or list(DEFAULT_CHANNELS)
    fs = float(preset.get("fs", fs))
    return channels, fs


def _serializable_event(event: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"type": "event"}
    for key in (
        "timestamp_sec",
        "sqi_total",
        "status",
        "predicted_class",
        "alert_class",
    ):
        out[key] = event.get(key)
    smooth = event.get("probabilities_smooth")
    if smooth is not None:
        out["probabilities_smooth"] = list(smooth)
    return out


@router.websocket("/ws/stream/{session_id}")
async def stream(ws: WebSocket, session_id: str) -> None:
    if not _authenticate_ws(ws):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing or invalid token")
        return

    if not get_manager().is_loaded:
        await ws.close(code=status.WS_1011_INTERNAL_ERROR, reason="Model not loaded")
        return

    await ws.accept()
    sm = get_session_manager()
    detector_channels: Optional[List[str]] = None

    counters: Dict[str, float] = {
        "total_windows": 0.0,
        "valid_windows": 0.0,
        "sqi_sum": 0.0,
    }
    replay_task: Optional[asyncio.Task] = None

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "init":
                try:
                    detector_channels, fs = _resolve_init_channels(msg)
                    overrides = msg.get("config_overrides") or {}
                    if not isinstance(overrides, dict):
                        overrides = {}
                    sm.create_session(
                        session_id,
                        detector_channels,
                        fs=fs,
                        config_overrides=overrides,
                    )
                except Exception as exc:
                    logger.exception("Init failed for session %s", session_id)
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue
                patient_id = msg.get("patient_id") or None
                _ensure_session_row(session_id, detector_channels, fs, patient_id=patient_id)
                replay_npz = msg.get("replay_npz") or msg.get("case_id")
                replay_path = resolve_replay_case(replay_npz) if replay_npz else None
                await ws.send_json(
                    {
                        "type": "ready",
                        "session_id": session_id,
                        "mapped_channels": list(DEFAULT_CHANNELS),
                        "device_channels": detector_channels,
                        "replay_npz": str(replay_path) if replay_path else None,
                    }
                )
                if replay_npz and not replay_path:
                    await ws.send_json(
                        {"type": "error", "message": f"Replay npz not found: {replay_npz}"}
                    )
                elif replay_path:
                    realtime = bool(msg.get("realtime", True))
                    if replay_task and not replay_task.done():
                        replay_task.cancel()
                    replay_task = asyncio.create_task(
                        _run_replay(ws, session_id, replay_path, counters, realtime=realtime)
                    )

            elif mtype == "data":
                detector = sm.get_session(session_id)
                if detector is None or detector_channels is None:
                    await ws.send_json(
                        {"type": "error", "message": "Send 'init' before 'data'"}
                    )
                    continue
                try:
                    arr = np.asarray(msg.get("chunk", []), dtype=float)
                    mapped, _ = map_to_pipeline(
                        arr, detector_channels, fs=detector.fs
                    )
                except ValueError as exc:
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue
                except Exception as exc:
                    logger.exception("Mapping error for session %s", session_id)
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue

                try:
                    loop = asyncio.get_event_loop()
                    events = await loop.run_in_executor(None, detector.update, mapped)
                except Exception as exc:
                    logger.exception("Detector failed for session %s", session_id)
                    await ws.send_json({"type": "error", "message": str(exc)})
                    continue

                for event in events:
                    counters["total_windows"] = counters.get("total_windows", 0) + 1
                    sqi = event.get("sqi_total")
                    if event.get("status") != "no-decision" and sqi is not None:
                        counters["valid_windows"] = counters.get("valid_windows", 0) + 1
                        counters["sqi_sum"] = counters.get("sqi_sum", 0.0) + float(sqi)
                    if event.get("status") in ALERT_ENTRY_STATUSES:
                        _persist_alert(session_id, event)
                    await ws.send_json(_serializable_event(event))

            elif mtype == "close":
                break

            else:
                await ws.send_json(
                    {"type": "error", "message": f"Unknown message type '{mtype}'"}
                )

    except WebSocketDisconnect:
        logger.info("Session %s disconnected", session_id)
    except Exception as exc:
        logger.exception("WebSocket loop crashed for %s", session_id)
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        if replay_task and not replay_task.done():
            replay_task.cancel()
            try:
                await replay_task
            except (asyncio.CancelledError, Exception):
                pass
        sm.close_session(session_id)
        _finalise_session_row(
            session_id,
            int(counters.get("total_windows", 0)),
            int(counters.get("valid_windows", 0)),
            float(counters.get("sqi_sum", 0.0)),
        )
        try:
            await ws.close()
        except Exception:
            pass
