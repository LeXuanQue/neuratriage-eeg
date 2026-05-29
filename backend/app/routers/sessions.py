"""POST /api/sessions/start, POST /api/sessions/{id}/end, GET /api/sessions
(Master Prompt §6.4). Each /start persists an EEGSession row so the dashboard
and reporting subsystems can query historical sessions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from eeg_stroke_pipeline import DEFAULT_CHANNELS
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import DemoUser
from ..database import get_db
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..models import EEGSession
from ..services.channel_mapper import DEVICE_PRESETS
from ..services.model_manager import get_manager
from ..services.session_manager import get_session_manager


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionStart(BaseModel):
    device_type: str = Field(default="full_18ch")
    device_channels: Optional[List[str]] = None
    fs: float = 256.0
    patient_id: Optional[str] = None
    device_id: Optional[str] = None


def _resolve_device_channels(req: SessionStart) -> tuple[List[str], float]:
    if req.device_channels:
        return list(req.device_channels), float(req.fs)
    preset = DEVICE_PRESETS.get(req.device_type)
    if not preset:
        raise EnvelopeError(
            f"Unknown device_type '{req.device_type}'", "UNKNOWN_DEVICE", 400
        )
    channels = list(preset["channels"]) or list(DEFAULT_CHANNELS)
    fs = float(preset.get("fs", req.fs))
    return channels, fs


def _session_to_out(s: EEGSession) -> dict:
    return {
        "session_id": s.id,
        "ws_url": f"/ws/stream/{s.id}",
        "device_channels": s.device_channels or [],
        "mapped_channels": list(DEFAULT_CHANNELS),
        "fs": s.fs,
        "patient_id": s.patient_id,
        "device_id": s.device_id,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "duration_sec": s.duration_sec,
        "total_windows": s.total_windows,
        "valid_windows": s.valid_windows,
        "sqi_mean": s.sqi_mean,
        "alert_count": s.alert_count,
    }


@router.post("/start")
def start_session(
    body: SessionStart = Body(default_factory=SessionStart),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    if not get_manager().is_loaded:
        raise EnvelopeError(
            "Model not loaded — cannot start streaming session.",
            "MODEL_NOT_LOADED",
            503,
        )
    channels, fs = _resolve_device_channels(body)
    session_id = uuid.uuid4().hex

    row = EEGSession(
        id=session_id,
        patient_id=body.patient_id,
        device_id=body.device_id,
        device_channels=channels,
        fs=fs,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ok(_session_to_out(row), status_code=201)


@router.post("/{session_id}/end")
def end_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    closed = get_session_manager().close_session(session_id)
    row = db.execute(
        select(EEGSession).where(EEGSession.id == session_id)
    ).scalar_one_or_none()
    if row and row.ended_at is None:
        now = datetime.now(timezone.utc)
        row.ended_at = now
        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        row.duration_sec = (now - started).total_seconds()
        db.commit()
        db.refresh(row)
    return ok(
        {
            "session_id": session_id,
            "was_active": closed,
            "row": _session_to_out(row) if row else None,
        }
    )


@router.get("")
def list_sessions(
    only_active: bool = False,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    stmt = select(EEGSession).order_by(EEGSession.started_at.desc())
    if only_active:
        stmt = stmt.where(EEGSession.ended_at.is_(None))
    rows = db.execute(stmt).scalars().all()
    return ok(
        {
            "in_memory_active": get_session_manager().list_active_sessions(),
            "rows": [_session_to_out(r) for r in rows],
        }
    )
