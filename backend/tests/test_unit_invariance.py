"""Features and SQI must not depend on the unit a recording is stored in (V vs uV).

Regression for the 2026-10-06 finding: compute_sqi added EPS=1e-12 to band powers,
which is the same order as EEG power in V^2, so the same signal stored in volts or in
microvolts got different SQI values and the deployed model flipped P(stroke) 1.00 -> 0.06.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import eeg_stroke_pipeline as P

ROOT = Path(__file__).resolve().parents[2]
REAL_IS = ROOT / "dataset_ischemic" / "sub-01.npz"          # stored in volts


def _real_window() -> tuple[np.ndarray, np.ndarray]:
    if not REAL_IS.exists():
        pytest.skip("real EEG sample not available")
    x = np.load(REAL_IS)["data"].astype(float)[:, : 256 * 20]
    cfg = P.PipelineConfig()
    feat = P.preprocess_eeg(x, 256.0, cfg)
    sqi = P.preprocess_eeg_for_sqi(x, 256.0, cfg)
    return feat[:, -1024:], sqi[:, -256:]


def test_sqi_is_identical_in_volts_and_microvolts() -> None:
    _, sqi_v = _real_window()
    cfg = P.PipelineConfig()

    in_v = P.compute_sqi(sqi_v, 256.0, cfg)
    in_uv = P.compute_sqi(sqi_v * 1e6, 256.0, cfg)

    for key, value in in_v.items():
        assert in_uv[key] == pytest.approx(value, rel=1e-6, abs=1e-9), key


def test_every_model_feature_is_identical_in_volts_and_microvolts() -> None:
    feat_v, sqi_v = _real_window()
    cfg = P.PipelineConfig()

    def row(scale: float) -> dict:
        return P.build_feature_row_from_windows(
            entropy_window=feat_v[:, -256:] * scale, mfdfa_window=feat_v * scale,
            channels=list(cfg.channels), fs=256.0, config=cfg, sqi_window=sqi_v * scale)

    in_v, in_uv = row(1.0), row(1e6)
    bad = {k: (in_v[k], in_uv[k]) for k in P.ALL_FEATURES
           if not np.isclose(in_v[k], in_uv[k], rtol=1e-6, atol=1e-9, equal_nan=True)}
    assert not bad, bad


@pytest.mark.parametrize("scale", [1e-6, 1.0])            # volts, microvolts
def test_sqi_still_flags_a_dead_channel_and_line_noise(scale: float) -> None:
    rng = np.random.default_rng(0)
    t = np.arange(256) / 256.0
    x = 20.0 * rng.standard_normal((18, 256))
    x[0] = 0.0                                              # disconnected electrode
    noisy = x + 200.0 * np.sin(2 * np.pi * 50.0 * t)        # strong mains on every channel
    cfg = P.PipelineConfig()

    clean = P.compute_sqi(x * scale, 256.0, cfg)
    dirty = P.compute_sqi(noisy * scale, 256.0, cfg)

    assert clean["sqi_flatline"] == pytest.approx(1 / 18)
    assert dirty["sqi_line_ratio"] > 10 * clean["sqi_line_ratio"] and dirty["sqi_line_ratio"] > 0.5
