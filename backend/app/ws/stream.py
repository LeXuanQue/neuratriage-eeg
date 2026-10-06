"""WebSocket /ws/stream/{session_id} — real-time EEG inference.

Protocol (Master Prompt §4):

  Client → Server:
    {"type": "init", "device_type": "...", "device_channels": [...], "fs": 256}
    {"type": "data", "chunk": [[...], [...], ...]}
    {"type": "close"}

  Server → Client:
    {"type": "ready", "session_id": "...", "mapped_channels": [...]}
    {"type": "event", "timestamp_sec": 1.5, "status": "monitor"|"alert-enter"|...,
     "predicted_class": "non-stroke"|"ischemic"|null,
     "probabilities_smooth": [p_ns, p_is, p_hs],
     "sqi_total": 0.82, "alert_class": "ischemic"|null}
    {"type": "replay_loop", "lap": 2}   # only when init asked for loop=true
    {"type": "device_status", "state": "searching"|"connected"|"error"|
     "blocked"|"stopped", "message": "...", "retry_in_sec": 2.0}
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
from ..services.artifact_inject import apply_synthetic_artifact
from ..services.channel_mapper import DEVICE_PRESETS, map_to_pipeline
from ..services.model_manager import get_manager
from ..services.replay_cases import resolve_stream_file
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
    loaded = np.load(str(path), allow_pickle=True)
    channels: Optional[List[str]] = None
    fs = 256.0
    try:
        if hasattr(loaded, "files"):  # .npz bundle
            if "data" in loaded.files:
                data = np.asarray(loaded["data"], dtype=float)
            elif "eeg" in loaded.files:
                data = np.asarray(loaded["eeg"], dtype=float)
            else:
                data = np.asarray(loaded[loaded.files[0]], dtype=float)
            if "channels" in loaded.files:
                channels = [str(c) for c in loaded["channels"]]
            if "fs" in loaded.files:
                fs = float(loaded["fs"])
        else:  # bare .npy array — no metadata to go with it
            data = np.asarray(loaded, dtype=float)
    finally:
        if hasattr(loaded, "close"):
            loaded.close()

    # An uploaded file is whatever the operator had lying around, so normalise
    # here rather than letting a bad shape reach the detector.
    if data.ndim == 1:
        data = data[np.newaxis, :]
    if data.ndim != 2:
        raise ValueError(
            f"Expected a (channels, samples) matrix, got array with shape {data.shape}"
        )
    if not data.size:
        raise ValueError("Recording is empty")
    if fs <= 0:
        fs = 256.0

    rows = int(data.shape[0])
    if channels is None or len(channels) != rows:
        channels = (
            list(DEFAULT_CHANNELS[:rows])
            if rows <= len(DEFAULT_CHANNELS)
            else [f"CH{i + 1}" for i in range(rows)]
        )
    return data, channels, fs


async def _run_replay(
    ws: WebSocket,
    session_id: str,
    npz_path: Path,
    counters: Dict[str, float],
    chunk_seconds: float = 0.5,
    realtime: bool = True,
    artifact_state: Optional[Dict[str, Any]] = None,
    loop: bool = False,
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
    lap = 0
    # Looping keeps a demo screen alive past the end of the recording. The
    # detector is deliberately NOT reset between laps: its EMA/hysteresis state
    # carries over, so playback stays continuous instead of restarting cold.
    while pos < n_total:
        chunk = data[:, pos : pos + chunk_samples]
        pos += chunk_samples
        # Demo control: when artifact injection is toggled on, corrupt the chunk
        # so SQI drops and the UI enters No-Decision. The corrupted chunk is what
        # gets both displayed (raw_chunk) and scored, so the waveform and the SQI
        # response stay consistent.
        if artifact_state and artifact_state.get("on"):
            chunk = apply_synthetic_artifact(
                chunk, fs, float(artifact_state.get("intensity", 1.0))
            )
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
            # NB: not named `loop` — that is this function's boolean parameter.
            event_loop = asyncio.get_running_loop()
            mapped, _ = map_to_pipeline(chunk, replay_channels, fs=fs)
            events = await event_loop.run_in_executor(None, detector.update, mapped)
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

        if pos >= n_total and loop:
            lap += 1
            pos = 0
            try:
                await ws.send_json({"type": "replay_loop", "lap": lap})
            except Exception:
                return

    try:
        await ws.send_json({"type": "replay_done"})
    except Exception:
        pass


async def _run_device(
    ws: WebSocket,
    session_id: str,
    address: str,
    counters: Dict[str, float],
) -> None:
    """Server-driven live device: stream BLE chunks through the detector.

    Mirrors `_run_replay` but the source is a real headset. Refuses to start
    until the device protocol is confirmed (`configured=True`), so an
    unconfigured BLE profile never feeds the detector. Exploratory: the Focus+
    delivers 2 differential channels mapped onto the 18-ch pipeline montage.
    """
    from ..services.device_source import BRAIN_LIFE_FOCUS_PLUS, BleDeviceSource
    from ..services.device_stream import (
        DeviceSqiMonitor,
        device_sqi_event,
        run_device_session,
    )

    sm = get_session_manager()
    detector = sm.get_session(session_id)
    if detector is None:
        await ws.send_json({"type": "error", "message": "Device: session not initialised"})
        return

    proto = BRAIN_LIFE_FOCUS_PLUS
    if not proto.configured:
        await ws.send_json(
            {
                "type": "error",
                "message": (
                    "Live device not configured yet — run scripts/ble_probe.py and set "
                    "configured=True in device_source.py before streaming."
                ),
            }
        )
        return

    # SQI is scored on the REAL device channels, not the zero-filled 18-ch map
    # (see DeviceSqiMonitor): the 2 differential channels don't alias onto the
    # monopolar montage, so scoring the mapped array would pin SQI at ~0 forever.
    # The live device path is quality-only — it drives SQI / No-Decision but never
    # a class; classification stays on the validated 18-ch replay path (Hybrid).
    monitor = DeviceSqiMonitor(len(proto.channel_labels), proto.fs, detector.config)
    gate = float(detector.config.sqi_threshold)
    elapsed = {"sec": 0.0}

    async def on_data(chunk: np.ndarray, labels: List[str]) -> None:
        arr = np.asarray(chunk, dtype=float)
        try:
            await ws.send_json(
                {
                    "type": "raw_chunk",
                    "chunk": arr.tolist(),
                    "device_channels": list(labels),
                    "fs": proto.fs,
                }
            )
        except Exception:
            return
        sqi = monitor.push(arr)
        if sqi is None:
            return
        if arr.ndim == 2 and arr.shape[1]:
            elapsed["sec"] += float(arr.shape[1]) / float(proto.fs)
        event = device_sqi_event(sqi, elapsed["sec"], gate)
        counters["total_windows"] = counters.get("total_windows", 0) + 1
        if event["status"] != "no-decision":
            counters["valid_windows"] = counters.get("valid_windows", 0) + 1
            counters["sqi_sum"] = counters.get("sqi_sum", 0.0) + event["sqi_total"]
        try:
            await ws.send_json(_serializable_event(event))
        except Exception:
            return

    async def on_status(payload: Dict[str, Any]) -> None:
        """Forward BLE link state so the client can tell "headset off" from "broken"."""
        try:
            await ws.send_json({"type": "device_status", **payload})
        except Exception:
            return

    await run_device_session(
        lambda on_chunk: BleDeviceSource(
            proto,
            on_chunk,
            address or proto.name_hint or proto.name,
            on_status=on_status,
        ),
        on_data,
    )


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
    device_task: Optional[asyncio.Task] = None
    # Demo-only artifact-injection toggle, shared with the replay task by reference.
    artifact_state: Dict[str, Any] = {"on": False, "intensity": 1.0}

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "init":
                source_kind = str(msg.get("source") or "").lower()
                try:
                    if source_kind == "device":
                        from ..services.device_source import BRAIN_LIFE_FOCUS_PLUS as _proto
                        detector_channels = list(_proto.channel_labels)
                        fs = float(_proto.fs)
                    else:
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
                replay_path = resolve_stream_file(replay_npz) if replay_npz else None
                await ws.send_json(
                    {
                        "type": "ready",
                        "session_id": session_id,
                        "mapped_channels": list(DEFAULT_CHANNELS),
                        "device_channels": detector_channels,
                        "replay_npz": str(replay_path) if replay_path else None,
                    }
                )
                if source_kind == "device":
                    if device_task and not device_task.done():
                        device_task.cancel()
                    device_task = asyncio.create_task(
                        _run_device(
                            ws, session_id, str(msg.get("device_address") or ""), counters
                        )
                    )
                elif replay_npz and not replay_path:
                    await ws.send_json(
                        {"type": "error", "message": f"Replay npz not found: {replay_npz}"}
                    )
                elif replay_path:
                    realtime = bool(msg.get("realtime", True))
                    loop_replay = bool(msg.get("loop", False))
                    if replay_task and not replay_task.done():
                        replay_task.cancel()
                    replay_task = asyncio.create_task(
                        _run_replay(
                            ws, session_id, replay_path, counters,
                            realtime=realtime, artifact_state=artifact_state,
                            loop=loop_replay,
                        )
                    )

            elif mtype == "artifact":
                # Demo control: toggle synthetic artifact injection on the stream.
                artifact_state["on"] = bool(msg.get("on", False))
                intensity = msg.get("intensity")
                if intensity is not None:
                    try:
                        artifact_state["intensity"] = max(0.0, float(intensity))
                    except (TypeError, ValueError):
                        pass
                await ws.send_json(
                    {
                        "type": "artifact_state",
                        "on": artifact_state["on"],
                        "intensity": artifact_state["intensity"],
                    }
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
                    if artifact_state.get("on") and arr.ndim == 2 and arr.size:
                        arr = apply_synthetic_artifact(
                            arr, detector.fs, float(artifact_state.get("intensity", 1.0))
                        )
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
                    loop = asyncio.get_running_loop()
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
        for _task in (replay_task, device_task):
            if _task and not _task.done():
                _task.cancel()
                try:
                    await _task
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
