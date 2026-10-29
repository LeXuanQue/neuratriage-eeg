"""Tests for scripts/leave_source_out.py (source-swap evaluation + alignment + EEGNet)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import leave_source_out as lso  # noqa: E402


def test_source_swap_never_reuses_a_training_source_at_test_time() -> None:
    splits = lso.source_swap_splits(stroke=["xuanwu", "tianjin"], control=["physionet", "oslo"])

    assert len(splits) == 4
    for train, test in splits:
        assert len(train) == 2 and len(test) == 2
        assert set(train).isdisjoint(test)
        assert {"xuanwu", "tianjin"} & set(test) and {"physionet", "oslo"} & set(test)


def test_patient_level_auc_averages_windows_per_patient() -> None:
    pids = np.array(["a", "a", "b", "b", "c", "c"])
    y = np.array([1, 1, 0, 0, 1, 1])
    prob = np.array([0.9, 0.1, 0.4, 0.4, 0.8, 0.8])          # patient a mean = 0.5 > b's 0.4

    assert lso.patient_level_auc(pids, y, prob) == pytest.approx(1.0)


def test_euclidean_alignment_whitens_each_subjects_mean_covariance() -> None:
    rng = np.random.default_rng(0)
    mix = rng.standard_normal((4, 4))
    x = np.einsum("ij,wjt->wit", mix, rng.standard_normal((30, 4, 256)))   # 30 windows, 4 ch
    groups = np.array(["s1"] * 15 + ["s2"] * 15)

    aligned = lso.euclidean_align(x, groups)

    for g in ("s1", "s2"):
        xs = aligned[groups == g]
        mean_cov = np.mean([w @ w.T / w.shape[1] for w in xs], axis=0)
        np.testing.assert_allclose(mean_cov, np.eye(4), atol=1e-6)


def test_to_microvolts_rescales_volt_recordings_and_leaves_uv_alone() -> None:
    rng = np.random.default_rng(0)
    eeg_uv = 20.0 * rng.standard_normal((18, 2560))         # typical scalp EEG, ~20 uV

    np.testing.assert_allclose(lso.to_microvolts(eeg_uv * 1e-6), eeg_uv)
    np.testing.assert_allclose(lso.to_microvolts(eeg_uv), eeg_uv)


def test_slice_fraction_splits_a_recording_into_eyes_open_and_closed_halves() -> None:
    # PhysioNet npz = run 1 (eyes open) followed by run 2 (eyes closed), equal length.
    x = np.arange(20)[None, :].repeat(3, axis=0)

    eo = lso.slice_fraction(x, (0.0, 0.5))
    ec = lso.slice_fraction(x, (0.5, 1.0))

    assert eo[0].tolist() == list(range(10)) and ec[0].tolist() == list(range(10, 20))


def test_filter_min_age_keeps_only_old_enough_subjects() -> None:
    import pandas as pd
    manifest = pd.DataFrame({"patient_id": ["os-001", "os-003", "os-011"], "label": ["non-stroke"] * 3,
                             "path": ["a", "b", "c"], "fs": [256.0] * 3})
    participants = pd.DataFrame({"participant_id": ["sub-001", "sub-003", "sub-011"], "age": [29, 62, 45]})

    kept = lso.filter_min_age(manifest, participants, min_age=45)

    assert kept["patient_id"].tolist() == ["os-003", "os-011"]


def test_eegnet_outputs_one_logit_per_window() -> None:
    torch = pytest.importorskip("torch")
    net = lso.EEGNet(n_channels=18, n_samples=512)

    out = net(torch.zeros(5, 1, 18, 512))

    assert tuple(out.shape) == (5,)
