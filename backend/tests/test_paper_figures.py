"""Data-extraction helpers of scripts/paper_figures.py (the plots read these, so test them)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import paper_figures as F  # noqa: E402

LSO = {
    "in_source_cv": {"riemann_app": {"patient_auc": 0.99}},
    "source_swap": [
        {"model": "riemann_app", "train": ["a"], "test": ["b", "physionet_eo"],
         "patient_auc": 0.82, "patient_auc_ci95": [0.71, 0.90]},
        {"model": "riemann_app", "train": ["a"], "test": ["b", "physionet_ec"],
         "patient_auc": 0.96, "patient_auc_ci95": [0.92, 0.99]},
        {"model": "feat_lgbm", "train": ["a"], "test": ["b", "physionet_eo"],
         "patient_auc": 0.57, "patient_auc_ci95": [0.46, 0.68]},
    ],
}


@pytest.mark.unit
def test_cascade_points_filters_by_model_and_test_source() -> None:
    pts = F.cascade_points(LSO, "riemann_app", test_must_include="physionet_eo")
    assert pts == [(0.82, 0.71, 0.90)]
    assert F.cascade_points(LSO, "riemann_app") == [(0.82, 0.71, 0.90), (0.96, 0.92, 0.99)]


@pytest.mark.unit
def test_far_curve_reads_mean_and_band_per_alpha() -> None:
    report = {"splits": {"S1": {"alphas": {
        "0.1": {"conformal": {"far": {"mean": 0.08, "p05": 0.0, "p95": 0.2}}},
        "0.05": {"conformal": {"far": {"mean": 0.04, "p05": 0.0, "p95": 0.1}}},
    }}}}
    alphas, mean, lo, hi = F.far_curve(report, "S1", "conformal")
    assert alphas == [0.05, 0.1] and mean == [0.04, 0.08] and hi == [0.1, 0.2] and lo == [0.0, 0.0]


@pytest.mark.unit
def test_window_level_far_is_read_from_its_own_key() -> None:
    report = {"splits": {"S1": {"alphas": {"0.1": {"window_level_any_alert_far": {"mean": 0.3, "p05": 0.1, "p95": 0.5}}}}}}
    assert F.far_curve(report, "S1", "window_level_any_alert_far")[1] == [0.3]
