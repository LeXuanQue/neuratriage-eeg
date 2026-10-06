"""Phase-2 device wiring tests — hardware-free.

Verifies the live-device path (source -> queue -> on_data, and map+detector step)
without bleak or a real headband, using a fake chunk source and fake detector.

Run: .venv/Scripts/python.exe -m pytest backend/tests/test_device_stream.py -q
"""
import asyncio

import numpy as np
import pytest

from app.services.device_stream import (
    DeviceSqiMonitor,
    device_readiness,
    device_sqi_event,
    process_chunk,
    run_device_session,
)
from app.services.device_source import BRAIN_LIFE_FOCUS_PLUS
from app.services.artifact_inject import apply_synthetic_artifact
from eeg_stroke_pipeline import PipelineConfig


class _FakeSource:
    """Emits `n` synthetic chunks then signals stop — mimics BleDeviceSource."""

    def __init__(self, on_chunk, n=3, labels=("C3", "C4")):
        self._on_chunk = on_chunk
        self._n = n
        self._labels = list(labels)

    async def run(self, stop):
        for _ in range(self._n):
            self._on_chunk(np.zeros((2, 128)), self._labels)
            await asyncio.sleep(0)
        stop.set()


class _FakeDetector:
    fs = 256.0

    def __init__(self):
        self.calls = 0
        self.last_shape = None

    def update(self, mapped):
        self.calls += 1
        self.last_shape = np.asarray(mapped).shape
        return [{"status": "monitor", "timestamp_sec": float(self.calls), "sqi_total": 0.9}]


@pytest.mark.unit
def test_process_chunk_maps_to_18ch_and_runs_detector():
    # Arrange
    det = _FakeDetector()
    # Act
    events = process_chunk(det, np.zeros((2, 128)), ["C3", "C4"])
    # Assert: 2 device channels were mapped to the 18-channel pipeline montage
    assert det.calls == 1
    assert det.last_shape[0] == 18
    assert events[0]["status"] == "monitor"


@pytest.mark.unit
def test_run_device_session_pipes_every_chunk_to_handler():
    received = []

    async def on_data(chunk, labels):
        received.append((np.asarray(chunk).shape, list(labels)))

    async def go():
        await run_device_session(lambda cb: _FakeSource(cb, n=3), on_data)

    asyncio.run(asyncio.wait_for(go(), timeout=5))
    assert len(received) == 3
    assert received[0] == ((2, 128), ["C3", "C4"])


@pytest.mark.unit
def test_run_device_session_swallows_handler_errors():
    seen = []

    async def bad_on_data(chunk, labels):
        seen.append(1)
        raise RuntimeError("boom")  # must not crash the session

    async def go():
        await run_device_session(lambda cb: _FakeSource(cb, n=2), bad_on_data)

    asyncio.run(asyncio.wait_for(go(), timeout=5))
    assert len(seen) == 2  # both chunks were delivered despite handler raising


@pytest.mark.unit
def test_device_readiness_reports_configured_focus_plus():
    # Protocol recovered + live-verified from the vendor app; now streamable.
    r = device_readiness(BRAIN_LIFE_FOCUS_PLUS)
    assert r["configured"] is True
    assert r["ready"] is True
    assert r["blocking_reason"] is None
    assert r["channels"] == ["AF3", "AF4"]


@pytest.mark.unit
def test_device_readiness_reports_unconfigured_protocol():
    import dataclasses

    unconfigured = dataclasses.replace(BRAIN_LIFE_FOCUS_PLUS, configured=False)
    r = device_readiness(unconfigured)
    assert r["configured"] is False
    assert r["ready"] is False
    assert r["blocking_reason"] and "configured" in r["blocking_reason"]


def _clean_2ch(seconds=2.0, fs=256.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * fs)
    t = np.arange(n) / fs
    sig = np.zeros((2, n))
    for f in (3.0, 7.0, 10.0):
        sig += np.sin(2 * np.pi * f * t)[None, :] * rng.uniform(0.5, 1.0, size=(2, 1))
    return sig * 10.0


@pytest.mark.unit
def test_device_sqi_monitor_scores_real_channels_not_zeros():
    """SQI must reflect the real 2-channel signal: high when clean, low when
    corrupted — proving it is NOT scored on the zero-filled 18-ch map."""
    cfg = PipelineConfig()
    fs = 256.0
    clean = _clean_2ch(fs=fs)

    mon = DeviceSqiMonitor(2, fs, cfg)
    out = None
    for start in range(0, clean.shape[1], int(fs // 4)):  # push 0.25 s chunks
        out = mon.push(clean[:, start:start + int(fs // 4)])
    assert out is not None, "monitor should return SQI once a full window is buffered"
    assert out["sqi_total"] > 0.70, f"clean 2-ch SQI should be high, got {out['sqi_total']:.3f}"

    mon2 = DeviceSqiMonitor(2, fs, cfg)
    corrupt = apply_synthetic_artifact(clean, fs, intensity=1.0, seed=1)
    out2 = None
    for start in range(0, corrupt.shape[1], int(fs // 4)):
        out2 = mon2.push(corrupt[:, start:start + int(fs // 4)])
    assert out2 is not None
    assert out2["sqi_total"] < 0.55, f"corrupted 2-ch SQI should crater, got {out2['sqi_total']:.3f}"


@pytest.mark.unit
def test_device_sqi_event_is_quality_only():
    below = device_sqi_event({"sqi_total": 0.30}, timestamp_sec=1.0, gate=0.55)
    above = device_sqi_event({"sqi_total": 0.90}, timestamp_sec=2.0, gate=0.55)
    assert below["status"] == "no-decision"
    assert above["status"] == "monitor"
    # Never a class from the 2-channel device (Hybrid: classification is replay-only).
    for ev in (below, above):
        assert ev["predicted_class"] is None
        assert ev["probabilities_smooth"] is None
        assert ev["alert_class"] is None
