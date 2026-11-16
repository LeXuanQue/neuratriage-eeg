"""Unit tests for the pure helpers in ``scripts/tuar_sqi_eval.py`` (SQI v1 vs v2 on TUAR).

The annotation and montage formats follow the TUH v3 conventions (csv_v1.0.0 with ``#``
header lines; ``montage = i, A-B: EEG A-REF -- EEG B-REF``). They are re-checked against
the real files once TUAR is downloaded.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import tuar_sqi_eval as E  # noqa: E402

CSV = """# version = csv_v1.0.0
# bname = aaaaaaju_s005_t000
# duration = 1750.00 secs
# montage_file = nedc_eas_default_montage.txt
#
channel,start_time,stop_time,label,confidence
FP1-F7,0.0000,36.8868,eyem,1.0000
fp2-f8,10.5000,12.0000,MUSC,1.0000
T3-C3,100.0000,104.0000,elpp,1.0000
"""

MONTAGE = """# TCP AR montage
montage =  0, FP1-F7: EEG FP1-REF  --  EEG F7-REF
montage =  1, F7-T3 : EEG F7-REF   --  EEG T3-REF

montage = 2, A1-T3: EEG A1-REF -- EEG T3-REF
"""


# --------------------------------------------------------------------- parsing
@pytest.mark.unit
def test_parse_csv_skips_comments_and_normalises_case() -> None:
    events = E.parse_tuar_csv(CSV)
    assert events == (
        E.ArtifactEvent("FP1-F7", 0.0, 36.8868, "eyem"),
        E.ArtifactEvent("FP2-F8", 10.5, 12.0, "musc"),
        E.ArtifactEvent("T3-C3", 100.0, 104.0, "elpp"),
    )


@pytest.mark.unit
def test_parse_csv_drops_background_rows() -> None:
    text = CSV + "C3-CZ,0.0,10.0,bckg,1.0\n"
    assert all(e.label != "bckg" for e in E.parse_tuar_csv(text))


@pytest.mark.unit
def test_parse_csv_rejects_missing_header() -> None:
    with pytest.raises(ValueError, match="header"):
        E.parse_tuar_csv("# only comments\nFP1-F7,0,1,eyem,1\n")


@pytest.mark.unit
def test_parse_montage() -> None:
    m = E.parse_montage(MONTAGE)
    assert m == (
        ("FP1-F7", "EEG FP1-REF", "EEG F7-REF"),
        ("F7-T3", "EEG F7-REF", "EEG T3-REF"),
        ("A1-T3", "EEG A1-REF", "EEG T3-REF"),
    )


@pytest.mark.unit
def test_patient_id_is_the_subject_prefix() -> None:
    assert E.patient_id("aaaaaaju_s005_t000") == "aaaaaaju"
    assert E.patient_id("aaaaaaju_s005_t000.edf") == "aaaaaaju"


# --------------------------------------------------------------------- bipolar
@pytest.mark.unit
def test_bipolar_derivation_subtracts_reference_channels() -> None:
    data = np.array([[1.0, 2.0], [0.5, 0.5], [3.0, 3.0]])
    names = ["EEG FP1-REF", "EEG F7-REF", "EEG T3-REF"]
    montage = (("FP1-F7", "EEG FP1-REF", "EEG F7-REF"), ("F7-T3", "EEG F7-REF", "EEG T3-REF"))
    out, labels = E.bipolar(data, names, montage)
    assert labels == ("FP1-F7", "F7-T3")
    np.testing.assert_allclose(out, [[0.5, 1.5], [-2.5, -2.5]])


@pytest.mark.unit
def test_bipolar_skips_pairs_with_missing_channels() -> None:
    data = np.zeros((2, 4))
    montage = (("FP1-F7", "EEG FP1-REF", "EEG F7-REF"), ("A1-T3", "EEG A1-REF", "EEG T3-REF"))
    _, labels = E.bipolar(data, ["EEG FP1-REF", "EEG F7-REF"], montage)
    assert labels == ("FP1-F7",)


# --------------------------------------------------------------------- window labels
@pytest.mark.unit
def test_window_labels_artifact_clean_and_ambiguous() -> None:
    events = (E.ArtifactEvent("FP1-F7", 4.0, 8.0, "eyem"), E.ArtifactEvent("FP1-F7", 13.0, 13.5, "musc"))
    # windows: [0,4) [4,8) [8,12) [12,16)
    labels, kinds = E.window_labels(events, "FP1-F7", n_windows=4, win_sec=4.0, step_sec=4.0)
    assert labels.tolist() == [0, 1, 0, -1]  # last window: 0.5 s overlap -> ambiguous
    assert kinds == ("", "eyem", "", "")


@pytest.mark.unit
def test_window_labels_only_use_the_requested_channel() -> None:
    events = (E.ArtifactEvent("FP2-F8", 0.0, 100.0, "musc"),)
    labels, _ = E.window_labels(events, "FP1-F7", n_windows=3, win_sec=4.0, step_sec=4.0)
    assert labels.tolist() == [0, 0, 0]


@pytest.mark.unit
def test_window_labels_pick_the_dominant_artifact_type() -> None:
    events = (E.ArtifactEvent("C3-CZ", 0.0, 1.0, "eyem"), E.ArtifactEvent("C3-CZ", 1.0, 4.0, "chew"))
    labels, kinds = E.window_labels(events, "C3-CZ", n_windows=1, win_sec=4.0, step_sec=4.0)
    assert labels.tolist() == [1]
    assert kinds == ("chew",)


@pytest.mark.unit
def test_window_labels_use_the_union_of_overlapping_events() -> None:
    """Review finding: overlapping eyem+musc rows must not be summed into a fake 60 %."""
    events = (E.ArtifactEvent("FP1-F7", 0.0, 1.2, "musc"), E.ArtifactEvent("FP1-F7", 0.0, 1.2, "eyem"))
    labels, _ = E.window_labels(events, "FP1-F7", n_windows=1, win_sec=4.0, step_sec=4.0)
    assert labels.tolist() == [-1]  # union covers 30 % -> ambiguous, not artifact


@pytest.mark.unit
def test_union_of_partly_overlapping_events() -> None:
    events = (E.ArtifactEvent("C3-CZ", 0.0, 1.5, "musc"), E.ArtifactEvent("C3-CZ", 1.0, 2.5, "chew"))
    labels, kinds = E.window_labels(events, "C3-CZ", n_windows=1, win_sec=4.0, step_sec=4.0)
    assert labels.tolist() == [1]  # union 2.5 s >= 2.0 s
    assert kinds[0] in {"musc", "chew"}


@pytest.mark.unit
def test_unmatched_event_channels_are_counted() -> None:
    events = (
        E.ArtifactEvent("FP1-F7", 0.0, 1.0, "eyem"),
        E.ArtifactEvent("FP1-REF", 0.0, 1.0, "eyem"),
        E.ArtifactEvent("7", 0.0, 1.0, "musc"),
    )
    assert E.unmatched_events(events, ("FP1-F7", "F7-T3")) == 2


@pytest.mark.unit
def test_safe_extract_reports_errors_instead_of_raising(tmp_path: Path) -> None:
    out = E.safe_extract((str(tmp_path / "missing.edf"), str(tmp_path), 0.25, 0))
    assert out["rows"] == []
    assert out["error"]


# --------------------------------------------------------------------- calibration
@pytest.mark.unit
def test_split_patients_is_deterministic_disjoint_and_complete() -> None:
    pids = [f"aaaa{i:04d}" for i in range(200)]
    calib, test = E.split_patients(pids)
    assert calib == E.split_patients(list(reversed(pids)))[0]  # order does not matter
    assert not calib & test
    assert calib | test == set(pids)
    assert 70 <= len(calib) <= 130


@pytest.mark.unit
def test_calibrate_drift_uses_the_clean_quantile_only() -> None:
    import pandas as pd

    clean = pd.DataFrame({"label": 0, "v2_flat": 0, "drift_excess": np.linspace(-1.0, 1.0, 101)})
    art = pd.DataFrame({"label": 1, "v2_flat": 0, "drift_excess": np.full(50, 9.0)})
    flat = pd.DataFrame({"label": 0, "v2_flat": 1, "drift_excess": np.full(50, np.nan)})
    ramp = E.calibrate_drift_ramp(pd.concat([clean, art, flat]), quantile=0.95)
    assert ramp[0] == pytest.approx(0.9)
    assert ramp[1] == pytest.approx(0.9 + E.DRIFT_RAMP_WIDTH)
    assert ramp[2] == E.DRIFT_WEIGHT


@pytest.mark.unit
def test_rescore_applies_a_calibrated_config() -> None:
    import pandas as pd
    import sqi_v2

    row = {k: 0.0 for k in E.V2_SIGNAL_FEATURES}
    row.update({"aperiodic_exponent": 1.5, "aperiodic_r2": 0.95, "drift_excess": 1.0, "v2_flat": 0})
    df = pd.DataFrame([row, {**row, "v2_flat": 1}])
    loose = E.rescore(df, sqi_v2.config_from_dict({"drift_ramp": [0.4, 1.2, 0.6]}))
    strict = E.rescore(df, sqi_v2.config_from_dict({"drift_ramp": [2.0, 3.0, 0.6]}))
    assert loose[0] < strict[0] == pytest.approx(1.0)
    assert loose[1] == strict[1] == 0.0  # flat stays flat


# --------------------------------------------------------------------- E7/E8: reasons and localization
@pytest.mark.unit
def test_select_channels_keeps_every_channel_when_a_window_has_an_artifact() -> None:
    labels = np.array([0, 1, 0, -1, 0])
    idx, full = E.select_channels(labels, keep_clean=0.01, rng=np.random.default_rng(0))
    assert full is True
    assert idx.tolist() == [0, 1, 2, 4]  # ambiguous channel never kept


@pytest.mark.unit
def test_select_channels_subsamples_clean_only_windows() -> None:
    labels = np.zeros(200, dtype=int)
    idx, full = E.select_channels(labels, keep_clean=0.25, rng=np.random.default_rng(1))
    assert full is False
    assert 25 <= idx.size <= 75


@pytest.mark.unit
def test_select_channels_keep_all_when_keep_clean_is_zero() -> None:
    idx, full = E.select_channels(np.zeros(5, dtype=int), keep_clean=0.0, rng=np.random.default_rng(2))
    assert full is True and idx.size == 5


@pytest.mark.unit
@pytest.mark.parametrize(
    "kind, expected",
    [
        ("musc", {"muscle"}),
        ("chew", {"muscle"}),
        ("eyem", {"transient", "drift"}),
        ("eyem_musc", {"transient", "drift", "muscle"}),
        ("elec", {"flat", "drift", "transient", "clipping", "missing"}),
    ],
)
def test_expected_reasons_for_tuar_kinds(kind: str, expected: set) -> None:
    assert E.expected_reasons(kind) == frozenset(expected)


@pytest.mark.unit
def test_reason_accuracy_counts_flags_and_matches() -> None:
    kinds = np.array(["musc", "musc", "eyem", "elec"])
    reasons = np.array(["muscle", "", "muscle", "flat"])
    r = E.reason_accuracy(kinds, reasons)
    assert r["flagged_share"] == pytest.approx(0.75)
    assert r["correct_among_flagged"] == pytest.approx(2 / 3)
    assert r["confusion"]["eyem"]["muscle"] == 1


@pytest.mark.unit
def test_localization_hits_when_lowest_score_is_an_artifact_channel() -> None:
    import pandas as pd

    df = pd.DataFrame({
        "rec": ["r1"] * 4 + ["r2"] * 4,
        "pid": ["p1"] * 4 + ["p2"] * 4,
        "window": [0] * 4 + [0] * 4,
        "full_window": 1,
        "label": [0, 1, 0, 0, 1, 0, 0, 0],
        "score": [0.9, 0.2, 0.8, 0.95, 0.9, 0.1, 0.8, 0.7],  # r1 hit, r2 miss
    })
    loc = E.localization(df, "score")
    assert loc["n_windows"] == 2
    assert loc["hit_rate"] == pytest.approx(0.5)
    assert loc["chance"] == pytest.approx(0.25)


@pytest.mark.unit
def test_localization_skips_partial_and_single_label_windows() -> None:
    import pandas as pd

    df = pd.DataFrame({
        "rec": ["r1", "r1", "r2", "r2"], "pid": ["p1", "p1", "p2", "p2"], "window": [0, 0, 0, 0],
        "full_window": [0, 0, 1, 1], "label": [0, 1, 1, 1], "score": [0.1, 0.9, 0.2, 0.3],
    })
    assert E.localization(df, "score")["n_windows"] == 0


@pytest.mark.unit
def test_rescore_with_reasons_returns_first_reason() -> None:
    import pandas as pd
    import sqi_v2

    row = {k: 0.0 for k in E.V2_SIGNAL_FEATURES}
    row.update({"aperiodic_exponent": 1.5, "aperiodic_r2": 0.95, "drift_excess": 3.0, "v2_flat": 0})
    df = pd.DataFrame([row, {**row, "drift_excess": 0.0}, {**row, "v2_flat": 1}])
    scores, reasons = E.rescore_with_reasons(df, sqi_v2.SqiV2Config())
    assert reasons.tolist() == ["drift", "", "flat"]
    assert scores[2] == 0.0


# --------------------------------------------------------------------- statistics
@pytest.mark.unit
def test_grouped_cv_handles_fewer_patients_than_folds() -> None:
    rng = np.random.default_rng(5)
    pids = np.repeat(np.arange(3), 40)
    y = np.tile([0, 1], pids.size // 2)
    x = (y[:, None] + rng.standard_normal((y.size, 2))).astype(float)
    scores, folds = E.grouped_cv_scores(x, y, pids, n_folds=5, seed=0)
    assert len(folds) == 3
    assert not np.isnan(scores).any()


@pytest.mark.unit
def test_logistic_handles_heavy_tailed_and_missing_features() -> None:
    rng = np.random.default_rng(6)
    y = np.tile([0, 1], 200)
    x = np.c_[y + rng.standard_normal(y.size), np.exp(8 * rng.standard_normal(y.size))]
    x[::7, 0] = np.nan
    p = E.fit_logistic(x, y).predict_proba(x)[:, 1]
    assert np.isfinite(p).all()
    assert E._auc(y, p) > 0.7
@pytest.mark.unit
def test_paired_bootstrap_detects_a_better_score() -> None:
    rng = np.random.default_rng(0)
    pids = np.repeat(np.arange(30), 20)
    y = rng.integers(0, 2, size=pids.size)
    good = y + 0.3 * rng.standard_normal(y.size)
    bad = y + 3.0 * rng.standard_normal(y.size)
    res = E.paired_patient_bootstrap(pids, y, bad, good, n_boot=300, seed=1)
    assert res.auc_b > res.auc_a
    assert res.diff_ci[0] > 0  # whole CI above zero


@pytest.mark.unit
def test_paired_bootstrap_ci_covers_zero_for_identical_scores() -> None:
    rng = np.random.default_rng(2)
    pids = np.repeat(np.arange(20), 10)
    y = rng.integers(0, 2, size=pids.size)
    s = y + rng.standard_normal(y.size)
    res = E.paired_patient_bootstrap(pids, y, s, s, n_boot=200, seed=3)
    assert res.diff == pytest.approx(0.0)
    assert res.diff_ci[0] <= 0.0 <= res.diff_ci[1]


@pytest.mark.unit
def test_grouped_cv_scores_never_train_on_the_test_patient() -> None:
    rng = np.random.default_rng(4)
    pids = np.repeat(np.arange(10), 30)
    y = np.tile([0, 1], pids.size // 2)
    x = (y[:, None] + rng.standard_normal((y.size, 3))).astype(float)
    seen = []

    def spy_fit(x_tr: np.ndarray, y_tr: np.ndarray):
        seen.append(None)
        return E.fit_logistic(x_tr, y_tr)

    scores, folds = E.grouped_cv_scores(x, y, pids, n_folds=5, seed=0, fit=spy_fit)
    assert scores.shape == y.shape
    assert len(seen) == len(folds) == 5
    for train_idx, test_idx in folds:
        assert not set(pids[train_idx]) & set(pids[test_idx])
