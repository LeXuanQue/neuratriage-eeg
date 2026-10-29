"""Tests for scripts/clinical_utility.py (operating-point and alarm metrics)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import clinical_utility as cu  # noqa: E402


def test_sensitivity_at_specificity_picks_best_threshold_meeting_target() -> None:
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.6, 0.5, 0.7, 0.8, 0.9])

    sens, spec, thr = cu.sensitivity_at_specificity(y, s, target_spec=0.75)

    assert spec >= 0.75
    assert sens == pytest.approx(1.0)                 # threshold 0.5 keeps all positives, 3/4 negatives below
    assert thr == pytest.approx(0.5)


def test_specificity_at_sensitivity_is_the_mirror_case() -> None:
    y = np.array([0, 0, 0, 0, 1, 1, 1, 1])
    s = np.array([0.1, 0.2, 0.3, 0.6, 0.5, 0.7, 0.8, 0.9])

    spec, sens, _ = cu.specificity_at_sensitivity(y, s, target_sens=1.0)

    assert sens == pytest.approx(1.0) and spec == pytest.approx(0.75)


def test_ppv_npv_follow_bayes_rule() -> None:
    ppv, npv = cu.ppv_npv(sens=0.9, spec=0.8, prevalence=0.5)

    assert ppv == pytest.approx(0.45 / (0.45 + 0.10))
    assert npv == pytest.approx(0.40 / (0.40 + 0.05))


def test_bootstrap_ci_brackets_the_point_estimate_and_resamples_patients() -> None:
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(40), np.ones(40)]
    s = np.r_[rng.normal(0, 1, 40), rng.normal(1.5, 1, 40)]
    from sklearn.metrics import roc_auc_score

    point = roc_auc_score(y, s)
    lo, hi = cu.bootstrap_ci(lambda yy, ss: roc_auc_score(yy, ss), y, s, n_boot=300, seed=1)

    assert lo < point < hi and 0 < hi - lo < 0.3


def test_alert_episodes_counts_entries_and_rate_uses_monitored_hours() -> None:
    statuses = ["monitor", "alert-enter", "alert-hold", "alert-exit", "monitor", "alert-enter", "alert-hold"]

    episodes = cu.count_alert_episodes(statuses)
    rate = cu.per_hour(episodes, n_events=len(statuses), hop_sec=0.5)

    assert episodes == 2
    assert rate == pytest.approx(2 / (7 * 0.5 / 3600))


def test_poisson_ci_for_zero_events_is_not_zero_width() -> None:
    lo, hi = cu.poisson_rate_ci(0, hours=1.0)

    assert lo == 0.0 and hi == pytest.approx(3.689, abs=0.01)   # exact 95% upper bound for 0 events
