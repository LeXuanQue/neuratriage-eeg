"""Live-device status reporting — hardware-free.

Without these, a headset that is simply switched off looks identical to a broken
app: the backend retries in a loop and the client is told nothing.

Run: .venv/Scripts/python.exe -m pytest backend/tests/test_device_status.py -q
"""
import asyncio

import pytest

from app.services.device_source import BRAIN_LIFE_FOCUS_PLUS, BleDeviceSource


def _source(on_status=None):
    return BleDeviceSource(
        BRAIN_LIFE_FOCUS_PLUS,
        lambda chunk, labels: None,
        "focus",
        on_status=on_status,
    )


@pytest.mark.unit
def test_emit_status_forwards_state_and_message():
    # Arrange
    seen = []

    async def on_status(payload):
        seen.append(payload)

    src = _source(on_status)

    # Act
    asyncio.run(src._emit_status("searching", "scanning for Brain-Life Focus+"))

    # Assert
    assert seen == [{"state": "searching", "message": "scanning for Brain-Life Focus+"}]


@pytest.mark.unit
def test_emit_status_passes_extra_fields():
    seen = []

    async def on_status(payload):
        seen.append(payload)

    asyncio.run(_source(on_status)._emit_status("error", "not found", retry_in_sec=2.0))

    assert seen[0]["state"] == "error"
    assert seen[0]["retry_in_sec"] == 2.0


@pytest.mark.unit
def test_emit_status_is_a_noop_without_a_callback():
    # Must not raise — the callback is optional.
    asyncio.run(_source()._emit_status("searching", "x"))


@pytest.mark.unit
def test_emit_status_swallows_callback_errors():
    """A broken status consumer must never kill the BLE reconnect loop."""

    async def on_status(payload):
        raise RuntimeError("consumer exploded")

    asyncio.run(_source(on_status)._emit_status("connected", "x"))


@pytest.mark.unit
def test_run_reports_blocked_status_when_protocol_unconfigured():
    """An unconfigured profile must say so on the wire, not only in the logs."""
    from dataclasses import replace

    seen = []

    async def on_status(payload):
        seen.append(payload)

    src = BleDeviceSource(
        replace(BRAIN_LIFE_FOCUS_PLUS, configured=False),
        lambda chunk, labels: None,
        "focus",
        on_status=on_status,
    )

    with pytest.raises(RuntimeError):
        asyncio.run(src.run(asyncio.Event()))

    assert any(s["state"] == "blocked" for s in seen), seen
