"""Tests for scripts/device_invariance_probe.py (device-confound harness + DAFE)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import device_invariance_probe as dip  # noqa: E402


def _frame(n_pat: int, n_win: int, label: int, prefix: str, rng: np.random.Generator,
           leak: float, signal: float) -> pd.DataFrame:
    """f_leak shifts with `leak` (device), f_path shifts with label (pathology)."""
    rows = []
    for p in range(n_pat):
        for w in range(n_win):
            rows.append({
                "patient_id": f"{prefix}{p}", "label": label, "t_end_sec": float(w),
                "f_leak": leak + rng.normal(0, 0.3),
                "f_path": signal * label + rng.normal(0, 0.3),
                "f_noise": rng.normal(0, 1),
            })
    return pd.DataFrame(rows)


def _tables(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    cross = pd.concat([_frame(10, 20, 0, "ns-", rng, 0.0, 2.0), _frame(10, 20, 1, "sub-", rng, 0.0, 2.0)])
    tuh = pd.concat([_frame(10, 20, 0, "tuh_a", rng, 3.0, 2.0), _frame(10, 20, 1, "tuh_b", rng, 3.0, 2.0)])
    return cross.reset_index(drop=True), tuh.reset_index(drop=True)


def test_probe_frames_hold_pathology_label_constant() -> None:
    cross, tuh = _tables()
    probes = dip.build_probe_frames(cross, tuh)

    for name in ("device_normal", "device_patho"):
        df = probes[name]
        assert set(df["label"]) == {0, 1}                      # label column now = site
        assert set(df["orig_label"]) == ({0} if name == "device_normal" else {1})
        assert df.loc[df["label"] == 1, "patient_id"].str.startswith("tuh").all()
    assert probes["patho_samerig"]["patient_id"].str.startswith("tuh").all()
    assert set(probes["crosscohort"]["label"]) == {0, 1}


def test_cap_windows_per_patient_is_deterministic_and_bounded() -> None:
    cross, _ = _tables()
    a = dip.cap_windows_per_patient(cross, cap=5, seed=1)
    b = dip.cap_windows_per_patient(cross, cap=5, seed=1)

    assert a.groupby("patient_id").size().max() == 5
    pd.testing.assert_frame_equal(a, b)


def test_dafe_removes_device_feature_and_keeps_pathology_feature() -> None:
    cross, tuh = _tables()
    probes = dip.build_probe_frames(cross, tuh)
    feats = ["f_leak", "f_path", "f_noise"]

    result = dip.device_adversarial_elimination(
        probes["device_normal"], feats, target_auc=0.65, drop_per_step=1, folds=5, fast=True)

    assert "f_leak" not in result["kept"]
    assert "f_path" in result["kept"]
    assert result["history"][0]["device_auc"] > 0.9            # leaky before
    assert result["history"][-1]["device_auc"] <= 0.65         # invariant after


def test_split_patients_is_disjoint_and_keeps_both_sites() -> None:
    cross, tuh = _tables()
    device = dip.build_probe_frames(cross, tuh)["device_normal"]

    sel, held = dip.split_patients(device, frac=0.5, seed=0)

    assert set(sel["patient_id"]).isdisjoint(held["patient_id"])
    assert len(sel) + len(held) == len(device)
    assert set(sel["label"]) == {0, 1} and set(held["label"]) == {0, 1}


def test_dafe_calls_on_step_for_every_recorded_step() -> None:
    cross, tuh = _tables()
    device = dip.build_probe_frames(cross, tuh)["device_normal"]
    seen: list[int] = []

    result = dip.device_adversarial_elimination(
        device, ["f_leak", "f_path", "f_noise"], target_auc=0.65, drop_per_step=1, folds=5,
        fast=True, on_step=lambda kept: seen.append(len(kept)) or {"n": len(kept)})

    assert seen == [h["n_features"] for h in result["history"]]
    assert all("eval" in h for h in result["history"])


def test_evaluate_candidate_reports_both_axes() -> None:
    cross, tuh = _tables()
    probes = dip.build_probe_frames(cross, tuh)

    leaky = dip.evaluate_candidate(probes, ["f_leak"], folds=5, fast=True)
    clean = dip.evaluate_candidate(probes, ["f_path"], folds=5, fast=True)

    assert leaky["device_auc_normal"] > 0.9 and clean["device_auc_normal"] < 0.7
    assert clean["patho_auc_samerig"] > 0.9
