"""Device endpoints (Master Prompt §6.2).

Channel selection is detection-first, not preset-first:

* `GET /api/devices/presets` returns DEVICE_PRESETS purely as *template
  hints* the frontend can show in a dropdown (e.g. Focus+ electrode labels).
  They are NOT authoritative — different units of the
  same headset can ship with different montages.
* `POST /api/devices/probe` is the source of truth. After the frontend opens a
  BLE / serial / SDK link to the real headset, it reads the live channel list
  off the device descriptor and POSTs it here. The backend canonicalises the
  channel names (e.g. T7→T3 alias), maps them onto the 18-channel pipeline
  layout, and returns the resulting device profile. The frontend then passes
  `device_channels` (from this response) into `POST /api/sessions/start` and
  the WebSocket `init` message.

CRUD endpoints (`GET/POST /api/devices`, `GET/DELETE /api/devices/{id}`)
persist registered devices in SQLite so the dashboard's "Available devices"
list survives a server restart.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from eeg_stroke_pipeline import DEFAULT_CHANNELS, canonicalize_channel_name
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import DemoUser
from ..database import get_db
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..models import Device
from ..services.channel_mapper import DEVICE_PRESETS


router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceProbeRequest(BaseModel):
    """Channels read off the real headset at connection time."""

    channels: List[str] = Field(
        ..., description="Channel labels reported by the device descriptor"
    )
    fs: float = Field(256.0, gt=0, description="Sample rate in Hz")
    device_id: Optional[str] = Field(
        None, description="Stable device identifier (BLE MAC, serial, etc.)"
    )
    device_name: Optional[str] = Field(
        None, description="Human-readable name reported by the device"
    )
    device_type: Optional[str] = Field(
        None,
        description=(
            "Optional preset key for matching against DEVICE_PRESETS. "
            "Used only to enrich the response with a description; it does not "
            "override the channel list."
        ),
    )


@router.get("/presets")
def list_presets(_: DemoUser = Depends(get_current_user)):
    return ok(DEVICE_PRESETS)


@router.get("/live-status")
def live_device_status(_: DemoUser = Depends(get_current_user)):
    """Readiness of the built-in BLE device profile (Brain-Life Focus+).

    Lets the UI show whether a live session can start. Until `scripts/ble_probe.py`
    confirms the real GATT UUIDs and flips `configured=True`, `ready` is False and
    the WebSocket refuses a `source:"device"` init.
    """
    from ..services.device_source import BRAIN_LIFE_FOCUS_PLUS
    from ..services.device_stream import device_readiness

    return ok(device_readiness(BRAIN_LIFE_FOCUS_PLUS))


@router.post("/probe")
def probe_device(
    body: DeviceProbeRequest = Body(...),
    _: DemoUser = Depends(get_current_user),
):
    """Normalise a freshly-detected device channel list against the 18-ch layout."""

    raw_channels = [c for c in (body.channels or []) if c and c.strip()]
    if not raw_channels:
        raise EnvelopeError(
            "channels[] cannot be empty — read them off the device descriptor first.",
            "NO_CHANNELS",
            400,
        )

    canonical = [canonicalize_channel_name(ch) for ch in raw_channels]
    target = list(DEFAULT_CHANNELS)
    target_set = set(target)

    matched: list[dict] = []
    unrecognised: list[str] = []
    for raw, canon in zip(raw_channels, canonical):
        if canon in target_set:
            matched.append(
                {"device_label": raw, "canonical": canon, "aliased": raw != canon}
            )
        else:
            unrecognised.append(raw)

    canon_set = {m["canonical"] for m in matched}
    missing = [ch for ch in target if ch not in canon_set]

    preset_hint = None
    if body.device_type and body.device_type in DEVICE_PRESETS:
        preset_hint = DEVICE_PRESETS[body.device_type]

    return ok(
        {
            "device_id": body.device_id,
            "device_name": body.device_name,
            "device_type": body.device_type,
            "fs": body.fs,
            "device_channels": raw_channels,
            "canonical_channels": canonical,
            "mapped_channels": target,
            "matched": matched,
            "unrecognised": unrecognised,
            "missing_target_channels": missing,
            "coverage_ratio": (len(target) - len(missing)) / len(target),
            "preset_hint": preset_hint,
        }
    )


# ── CRUD ─────────────────────────────────────────────────────────────────


class DeviceIn(BaseModel):
    device_type: str
    device_name: str
    channels: List[str]
    fs: float = 256.0
    mac_address: Optional[str] = None
    serial_number: Optional[str] = None
    is_active: bool = True
    patient_id: Optional[str] = None


def _device_to_out(d: Device) -> dict:
    return {
        "id": d.id,
        "device_type": d.device_type,
        "device_name": d.device_name,
        "mac_address": d.mac_address,
        "serial_number": d.serial_number,
        "channels": d.channels,
        "fs": d.fs,
        "is_active": d.is_active,
        "patient_id": d.patient_id,
        "last_connected_at": d.last_connected_at,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


@router.get("")
def list_devices(
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    rows = (
        db.execute(select(Device).order_by(Device.updated_at.desc()))
        .scalars()
        .all()
    )
    return ok([_device_to_out(d) for d in rows])


@router.post("")
def register_device(
    body: DeviceIn = Body(...),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    if not body.channels:
        raise EnvelopeError("channels[] required", "NO_CHANNELS")
    device = Device(
        device_type=body.device_type,
        device_name=body.device_name,
        channels=list(body.channels),
        fs=body.fs,
        mac_address=body.mac_address,
        serial_number=body.serial_number,
        is_active=body.is_active,
        patient_id=body.patient_id,
        last_connected_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return ok(_device_to_out(device), status_code=201)


@router.get("/{device_id}")
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    device = db.execute(
        select(Device).where(Device.id == device_id)
    ).scalar_one_or_none()
    if not device:
        raise EnvelopeError(f"Device {device_id} not found", "DEVICE_NOT_FOUND", 404)
    return ok(_device_to_out(device))


@router.delete("/{device_id}")
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    device = db.execute(
        select(Device).where(Device.id == device_id)
    ).scalar_one_or_none()
    if not device:
        raise EnvelopeError(f"Device {device_id} not found", "DEVICE_NOT_FOUND", 404)
    db.delete(device)
    db.commit()
    return ok({"deleted": device_id})
