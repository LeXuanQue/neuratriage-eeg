"""Tests for scripts/device_recalibration.py (offline alert simulation + per-device threshold)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import device_recalibration as dr  # noqa: E402

import eeg_stroke_pipeline as P  # noqa: E402


class _Seq:
    """Window model that replays a fixed sequence of P(stroke)."""

    def __init__(self, probs):
        self.probs, self.i = list(probs), 0

    def predict_proba_from_window(self, window):
        p = self.probs[self.i]
        self.i += 1
        return np.array([1.0 - p, p])


def _detector_statuses(probs):
    det = P.RealTimeStrokeDetector(None, config=P.PipelineConfig(), window_model=_Seq(probs))
    rng = np.random.default_rng(0)
    events = []
    n_chunks = len(probs) + 7                         # first event needs the 4 s buffer (8 chunks)
    for _ in range(n_chunks):
        events += det.update(20.0 * rng.standard_normal((18, 128)))
    return [e["status"] for e in events][: len(probs)]


def test_simulator_reproduces_the_real_detector_exactly() -> None:
    # high stretch -> alert; low stretch -> exit; high again inside the 15 s cooldown; then after it
    probs = [0.2] * 5 + [0.95] * 10 + [0.1] * 10 + [0.95] * 10 + [0.3] * 25 + [0.97] * 12
    real = _detector_statuses(probs)
    assert "alert-enter" in real and "alert-exit" in real          # the scenario exercises the logic

    sim = dr.simulate_alerts(probs, cfg=P.PipelineConfig())

    assert sim == real


def test_no_decision_hops_do_not_update_the_smoother() -> None:
    probs = [0.95, None, None, 0.95, 0.95]
    sim = dr.simulate_alerts(probs, cfg=P.PipelineConfig())

    assert sim[1] == sim[2] == "no-decision"
    assert sim[3] == "alert-enter"                    # 2 consecutive scored hops above 0.80


def test_higher_threshold_never_raises_more_alerts() -> None:
    rng = np.random.default_rng(1)
    probs = list(np.clip(rng.normal(0.85, 0.1, 400), 0, 1))
    counts = [dr.simulate_alerts(probs, cfg=P.PipelineConfig(theta_high=t)).count("alert-enter")
              for t in (0.8, 0.9, 0.95, 0.99)]

    assert counts == sorted(counts, reverse=True)


def test_specificity_rule_leaves_the_target_share_of_healthy_recordings_unalerted() -> None:
    # 10 healthy recordings whose smoothed peak is 0.81, 0.82, ..., 0.90
    healthy = [[0.81 + 0.01 * i] * 6 for i in range(10)]
    cfg = P.PipelineConfig()

    theta = dr.calibrate_threshold(healthy, cfg, rule="spec", target_spec=0.8, margin=0.0)

    alerted = [dr.simulate_alerts(s, cfg=P.PipelineConfig(theta_high=theta)).count("alert-enter") > 0 for s in healthy]
    assert 1 - np.mean(alerted) >= 0.8                 # at least 80% of calibration recordings stay silent
    assert np.mean(alerted) > 0                        # but not "above everyone": that would be rule="max"


def test_calibrated_threshold_sits_just_above_healthy_smoothed_maximum() -> None:
    healthy = [[0.3, 0.6, 0.7], [0.5, 0.9, 0.4]]       # raw P(stroke) per calibration recording

    theta = dr.calibrate_threshold(healthy, cfg=P.PipelineConfig(), rule="max", margin=0.01)

    smoothed_max = max(dr.smoothed(seq, P.PipelineConfig().ema_beta).max() for seq in healthy)
    assert theta == pytest.approx(min(0.999, max(0.80, smoothed_max + 0.01)))
    assert all(dr.simulate_alerts(seq, cfg=P.PipelineConfig(theta_high=theta)).count("alert-enter") == 0
               for seq in healthy)
