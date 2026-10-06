"""Unit tests for app.services.channel_mapper.map_to_pipeline.

Spec: NeuraTriage_Backend_Master_Prompt.md §3.2.
"""
from __future__ import annotations

import numpy as np
import pytest

from eeg_stroke_pipeline import DEFAULT_CHANNELS
from app.services.channel_mapper import DEVICE_PRESETS, map_to_pipeline


def test_brain_life_focus_plus_maps_to_18_channels() -> None:
    rng = np.random.default_rng(42)
    device_channels = DEVICE_PRESETS["brain_life_focus_plus"]["channels"]
    n_samples = 1280
    chunk = rng.normal(size=(len(device_channels), n_samples))

    mapped, target = map_to_pipeline(chunk, device_channels, fs=256.0)

    assert mapped.shape == (18, n_samples), "Output must have 18 rows"
    assert target == DEFAULT_CHANNELS

    # Device channels are the 2 BIPOLAR derivations "F3-T7"/"F4-T8", not raw
    # monopolar electrodes. A bipolar signal is not equivalent to either of its
    # monopolar electrodes under CAR reference, so neither name should alias
    # onto any DEFAULT_CHANNELS entry: all 18 rows come back NaN (honest
    # "no equivalent data"), not silently mislabeled as monopolar T3/T4.
    assert len(device_channels) == 2
    nan_rows = int(np.isnan(mapped).all(axis=1).sum())
    assert nan_rows == 18


def test_alias_t7_maps_to_t3_row() -> None:
    n_samples = 64
    sentinel_t7 = np.full(n_samples, 0.123)
    sentinel_t8 = np.full(n_samples, 0.456)
    chunk = np.vstack([sentinel_t7, sentinel_t8])

    mapped, target = map_to_pipeline(chunk, ["T7", "T8"], fs=256.0)

    t3_idx = target.index("T3")
    t4_idx = target.index("T4")
    np.testing.assert_array_equal(mapped[t3_idx], sentinel_t7)
    np.testing.assert_array_equal(mapped[t4_idx], sentinel_t8)


def test_full_18ch_passthrough_preserves_data() -> None:
    rng = np.random.default_rng(7)
    chunk = rng.normal(size=(18, 256))

    mapped, target = map_to_pipeline(chunk, list(DEFAULT_CHANNELS), fs=256.0)

    assert mapped.shape == (18, 256)
    assert target == DEFAULT_CHANNELS
    np.testing.assert_allclose(mapped, chunk)
    assert not np.isnan(mapped).any()


def test_channel_count_mismatch_raises() -> None:
    chunk = np.zeros((3, 100))
    with pytest.raises(ValueError, match="Channel count mismatch"):
        map_to_pipeline(chunk, ["AF3", "AF4", "T7", "T8"], fs=256.0)


def test_one_d_input_raises() -> None:
    chunk = np.zeros(100)
    with pytest.raises(ValueError, match="2-D"):
        map_to_pipeline(chunk, ["AF3"], fs=256.0)
