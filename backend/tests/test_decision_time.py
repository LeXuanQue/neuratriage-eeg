"""Pure helpers of scripts/decision_time.py (E13: how long to record before deciding)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import decision_time as D  # noqa: E402


@pytest.mark.unit
def test_score_up_to_means_scored_events_within_the_horizon() -> None:
    times = np.array([4.0, 4.5, 5.0, 10.0, 20.0])
    probs = np.array([0.2, np.nan, 0.4, 0.9, 0.9])  # nan = no-decision event
    assert D.score_up_to(times, probs, horizon=10.0) == pytest.approx((0.2 + 0.4 + 0.9) / 3)


@pytest.mark.unit
def test_score_up_to_is_nan_when_nothing_was_scored_yet() -> None:
    times = np.array([4.0, 4.5])
    probs = np.array([np.nan, np.nan])
    assert np.isnan(D.score_up_to(times, probs, horizon=30.0))
    assert np.isnan(D.score_up_to(np.array([12.0]), np.array([0.5]), horizon=8.0))


@pytest.mark.unit
def test_patient_scores_at_horizon_keeps_patient_order() -> None:
    traces = {
        "a": (np.array([4.0, 8.0]), np.array([0.1, 0.3])),
        "b": (np.array([4.0, 8.0]), np.array([np.nan, 0.8])),
    }
    scores = D.patient_scores_at(traces, ["b", "a"], horizon=4.0)
    assert np.isnan(scores[0]) and scores[1] == pytest.approx(0.1)
