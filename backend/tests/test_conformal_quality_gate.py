"""Pure helpers of scripts/conformal_quality_gate.py (E11: R2 behind the SQI v2 quality gate)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import conformal_quality_gate as G  # noqa: E402


@pytest.mark.unit
def test_mains_frequency_follows_the_recording_country() -> None:
    # PhysioNet eegmmidb was recorded in the US (60 Hz); the other cohorts in 50 Hz countries
    assert G.line_freq_for("physionet_eo") == 60.0
    assert G.line_freq_for("physionet") == 60.0
    assert G.line_freq_for("xuanwu") == 50.0
    assert G.line_freq_for("tianjin") == 50.0
    assert G.line_freq_for("oslo45") == 50.0


@pytest.mark.unit
def test_unknown_source_is_an_error_not_a_silent_default() -> None:
    with pytest.raises(KeyError):
        G.line_freq_for("somewhere")


@pytest.mark.unit
def test_flat_windows_are_not_usable() -> None:
    rng = np.random.default_rng(0)
    flat = np.zeros((2, 4, 1024))
    out = G.usable_windows(flat, fs=256.0, line_freq=50.0)
    assert out.dtype == bool and out.shape == (2,)
    assert not out.any()
    noisy = rng.normal(0, 20, size=(1, 4, 1024))
    assert G.usable_windows(noisy, fs=256.0, line_freq=50.0).shape == (1,)


def _toy(n_ctrl: int = 30, n_stroke: int = 30, per: int = 4, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_ctrl + n_stroke):
        y = int(i >= n_ctrl)
        for _ in range(per):
            rows.append({"pid": f"p{i:03d}", "y": y, "p": float(np.clip(rng.normal(0.3 + 0.4 * y, 0.15), 0, 1))})
    return pd.DataFrame(rows)


@pytest.mark.unit
def test_gated_run_reports_quality_withholding_per_class() -> None:
    win = _toy()
    usable = np.ones(len(win), dtype=bool)
    usable[win["pid"].isin(["p000", "p001", "p040"]).to_numpy()] = False  # 2 controls, 1 stroke fully gated
    out = G.run_gated_split(win, usable, n_rep=50, seed=0, alphas=(0.1,))
    assert out["n_patients_without_usable_window"] == {"control": 2, "stroke": 1}
    a = out["alphas"]["0.1"]
    assert {"far", "miss", "no_decision_control", "no_decision_stroke"} <= set(a["conformal"])
    # a fully gated patient is always No-Decision, so ND share >= its share of the test half
    assert a["conformal"]["no_decision_control"]["mean"] > 0


@pytest.mark.unit
def test_gated_patients_are_never_alerted_or_cleared() -> None:
    win = _toy(per=3)
    usable = np.ones(len(win), dtype=bool)
    gone = win["pid"].isin([f"p{i:03d}" for i in range(0, 60, 2)]).to_numpy()  # half the patients
    usable[gone] = False
    states, labels, gated = G.gated_states_once(win, usable, alpha=0.1, rng=np.random.default_rng(1))
    assert gated.any()
    assert set(states[gated]) == {"no_decision"}


@pytest.mark.unit
def test_all_usable_matches_the_ungated_rule() -> None:
    win = _toy()
    usable = np.ones(len(win), dtype=bool)
    gated = G.run_gated_split(win, usable, n_rep=30, seed=3, alphas=(0.1,))
    assert gated["n_patients_without_usable_window"] == {"control": 0, "stroke": 0}
    assert gated["usable_window_share"] == {"control": 1.0, "stroke": 1.0}


@pytest.mark.unit
def test_align_windows_matches_by_content_within_patient() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=(5, 2, 8)).astype(np.float32)
    cached_pids = np.array(["p1", "p1", "p1", "p2", "p2"])
    # rebuilt set lost p1's middle window and kept the rest in order
    rebuilt = a[[0, 2, 3, 4]] + 1e-7
    rebuilt_pids = cached_pids[[0, 2, 3, 4]]
    idx = G.align_windows(cached_pids, a, rebuilt_pids, rebuilt)
    assert idx.tolist() == [0, -1, 1, 2, 3]


@pytest.mark.unit
def test_align_windows_never_matches_across_patients() -> None:
    a = np.ones((2, 1, 4), dtype=np.float32)
    idx = G.align_windows(np.array(["p1", "p2"]), a, np.array(["p3", "p3"]), a)
    assert idx.tolist() == [-1, -1]
