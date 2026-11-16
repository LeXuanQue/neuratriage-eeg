"""ChannelQualityTracker: rolling SQI v2 on the raw device channels for the live UI.

Synthetic signals only. The tracker is what feeds condition G of Study 1
(docs/user_study_protocol.md): per-channel score, reasons and one operator tip.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app.services.channel_quality import ChannelQualityTracker, load_sqi_config

FS = 256.0
UV = 1e-6


def _clean(n_ch: int, seconds: float, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(FS * seconds)
    freqs = np.fft.rfftfreq(n, d=1 / FS)
    amp = np.maximum(freqs, 1.0) ** -0.75
    amp[0] = 0.0
    rows = []
    t = np.arange(n) / FS
    for _ in range(n_ch):
        x = np.fft.irfft(amp * np.exp(1j * rng.uniform(0, 2 * np.pi, freqs.size)), n=n)
        rows.append(20 * UV * x / np.std(x) + 12 * UV * np.sin(2 * np.pi * 10 * t))
    return np.stack(rows)


def _feed(tracker: ChannelQualityTracker, data: np.ndarray, chunk_sec: float = 0.5) -> list[dict]:
    step = int(FS * chunk_sec)
    out = []
    for k in range(0, data.shape[1], step):
        msg = tracker.push(data[:, k : k + step])
        if msg is not None:
            out.append(msg)
    return out


@pytest.mark.unit
def test_no_message_until_the_window_is_full() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS, window_sec=4.0, every_sec=1.0)
    assert _feed(tracker, _clean(2, 3.5)) == []


@pytest.mark.unit
def test_emits_about_once_per_interval_after_the_window_fills() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS, window_sec=4.0, every_sec=1.0)
    msgs = _feed(tracker, _clean(2, 10.0))
    assert 6 <= len(msgs) <= 7  # first at 4 s, then every 1 s up to 10 s
    times = [m["timestamp_sec"] for m in msgs]
    assert times == sorted(times)
    assert times[0] == pytest.approx(4.0)


@pytest.mark.unit
def test_message_shape_is_json_safe_and_names_channels() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS)
    msg = _feed(tracker, _clean(2, 5.0))[0]
    json.dumps(msg, allow_nan=False)  # raises on NaN / inf
    assert msg["type"] == "channel_quality"
    assert [c["name"] for c in msg["channels"]] == ["AF3", "AF4"]
    assert all(0.0 <= c["score"] <= 1.0 for c in msg["channels"])
    assert msg["guidance"] is None  # clean signal: nothing to fix


@pytest.mark.unit
def test_flat_channel_produces_guidance_for_that_channel() -> None:
    data = _clean(2, 5.0, seed=1)
    data[1] = 0.0
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS)
    msg = _feed(tracker, data)[-1]
    assert msg["worst_channel"] == "AF4"
    assert msg["guidance"]["channel"] == "AF4"
    assert msg["guidance"]["reason"] == "flat"
    assert msg["guidance"]["advice"]
    af4 = next(c for c in msg["channels"] if c["name"] == "AF4")
    assert "flat" in af4["reasons"]


@pytest.mark.unit
def test_missing_samples_do_not_produce_nan_in_the_message() -> None:
    data = _clean(2, 5.0, seed=2)
    data[0, 300:500] = np.nan
    msg = _feed(ChannelQualityTracker(["AF3", "AF4"], FS), data)[0]
    json.dumps(msg, allow_nan=False)
    assert all(math.isfinite(c["score"]) for c in msg["channels"])


@pytest.mark.unit
def test_buffer_stays_bounded() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS, window_sec=4.0)
    _feed(tracker, _clean(2, 30.0))
    assert tracker.buffered_samples <= int(4.0 * FS)


@pytest.mark.unit
def test_rejects_chunks_with_the_wrong_channel_count() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], FS)
    with pytest.raises(ValueError, match="channels"):
        tracker.push(np.zeros((3, 128)))


@pytest.mark.unit
def test_sampling_rate_too_low_disables_the_tracker() -> None:
    tracker = ChannelQualityTracker(["AF3", "AF4"], 64.0)
    assert tracker.available is False
    assert _feed(tracker, np.zeros((2, 64 * 10))) == []


@pytest.mark.unit
def test_load_sqi_config_uses_a_frozen_drift_ramp(tmp_path) -> None:
    path = tmp_path / "cal.json"
    path.write_text(json.dumps({"drift_ramp": [1.9, 2.7, 0.6], "fitted_on": "test"}), encoding="utf-8")
    cfg = load_sqi_config(line_freq=60.0, calibration_path=path)
    assert cfg.drift_ramp == (1.9, 2.7, 0.6)
    assert cfg.line_freq == 60.0


@pytest.mark.unit
def test_load_sqi_config_falls_back_to_defaults(tmp_path) -> None:
    import sqi_v2

    cfg = load_sqi_config(line_freq=50.0, calibration_path=tmp_path / "missing.json")
    assert cfg.drift_ramp == sqi_v2.SqiV2Config().drift_ramp
