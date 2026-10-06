"""Verify the demo artifact injector actually tanks SQI through the real path.

The injector must drive ``compute_sqi`` (evaluated on ``preprocess_eeg_for_sqi``
output, exactly as the online detector does) below the detector gate (0.55) and
the UI's No-Decision threshold (0.70), so toggling it on stage reliably produces
the No-Decision state.
"""
from __future__ import annotations

import numpy as np
import pytest

from eeg_stroke_pipeline import (
    DEFAULT_CHANNELS,
    PipelineConfig,
    compute_sqi,
    preprocess_eeg_for_sqi,
)
from app.services.artifact_inject import apply_synthetic_artifact

FS = 256.0


def _clean_window(n_ch: int = 18, seconds: float = 4.0, seed: int = 0) -> np.ndarray:
    """A smooth multi-sine window -> high baseline SQI."""
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    t = np.arange(n) / FS
    sig = np.zeros((n_ch, n))
    for f in (3.0, 7.0, 10.0):  # delta/theta/alpha, no line/HF content
        sig += np.sin(2 * np.pi * f * t)[None, :] * rng.uniform(0.5, 1.0, size=(n_ch, 1))
    return sig * 10.0  # ~tens of µV


def _sqi_total(window: np.ndarray) -> float:
    cfg = PipelineConfig()
    prepped = preprocess_eeg_for_sqi(window, FS, cfg)
    return compute_sqi(prepped, cfg.fs, cfg)["sqi_total"]


def test_artifact_drops_sqi_below_gate():
    clean = _clean_window()
    sqi_clean = _sqi_total(clean)
    corrupted = apply_synthetic_artifact(clean, FS, intensity=1.0, seed=1)
    sqi_art = _sqi_total(corrupted)

    assert sqi_clean > 0.70, f"baseline should be usable, got {sqi_clean:.3f}"
    assert sqi_art < 0.55, f"artifact must drop SQI below the gate, got {sqi_art:.3f}"
    assert sqi_art < sqi_clean


def test_artifact_works_on_two_channel_montage():
    clean = _clean_window(n_ch=2)
    corrupted = apply_synthetic_artifact(clean, FS, intensity=1.0, seed=2)
    assert _sqi_total(corrupted) < 0.70  # visible No-Decision on the 2-ch device


def test_zero_intensity_is_noop():
    clean = _clean_window()
    out = apply_synthetic_artifact(clean, FS, intensity=0.0)
    np.testing.assert_array_equal(out, clean)


def test_empty_and_1d_inputs_are_safe():
    assert apply_synthetic_artifact(np.zeros((0, 0)), FS).shape == (0, 0)
    one_d = np.arange(10, dtype=float)
    np.testing.assert_array_equal(apply_synthetic_artifact(one_d, FS), one_d)


def test_shape_preserved():
    clean = _clean_window()
    out = apply_synthetic_artifact(clean, FS, intensity=1.0, seed=3)
    assert out.shape == clean.shape
    assert len(DEFAULT_CHANNELS) == 18
