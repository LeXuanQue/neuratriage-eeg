"""R2: patient-level Mondrian conformal No-Decision with a false-alert guarantee.

All data is synthetic and seeded. The guarantee tests are Monte Carlo checks of the
finite-sample bound P(alert | control) <= alpha_far for exchangeable patients.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import conformal_triage as C


# --------------------------------------------------------------------- quantile
@pytest.mark.unit
def test_conformal_quantile_uses_the_finite_sample_rank() -> None:
    scores = np.arange(1.0, 11.0)  # 1..10
    # ceil((10 + 1) * 0.8) = 9 -> 9th smallest
    assert C.conformal_quantile(scores, alpha=0.2) == 9.0


@pytest.mark.unit
def test_conformal_quantile_is_infinite_when_calibration_set_is_too_small() -> None:
    assert C.conformal_quantile(np.arange(5.0), alpha=0.1) == np.inf  # ceil(6 * 0.9) = 6 > 5
    assert C.conformal_quantile(np.array([]), alpha=0.5) == np.inf


@pytest.mark.unit
@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
def test_conformal_quantile_rejects_alpha_outside_unit_interval(alpha: float) -> None:
    with pytest.raises(ValueError, match="alpha"):
        C.conformal_quantile(np.arange(10.0), alpha=alpha)


@pytest.mark.unit
def test_conformal_quantile_ignores_nan_scores() -> None:
    scores = np.r_[np.arange(1.0, 11.0), np.nan, np.nan]
    assert C.conformal_quantile(scores, alpha=0.2) == 9.0


# --------------------------------------------------------------------- aggregation
@pytest.mark.unit
def test_aggregate_patients_means_valid_windows_only() -> None:
    pids = np.array(["a", "a", "a", "b", "b"])
    p = np.array([0.2, 0.4, 0.9, 0.7, 0.5])
    valid = np.array([True, True, False, True, True])
    agg = C.aggregate_patients(pids, p, valid=valid, min_valid=1)
    assert agg.pids == ("a", "b")
    np.testing.assert_allclose(agg.scores, [0.3, 0.6])
    assert agg.n_valid == (2, 2)


@pytest.mark.unit
def test_aggregate_patients_marks_too_few_valid_windows_as_nan() -> None:
    pids = np.array(["a", "a", "b"])
    p = np.array([0.2, 0.4, 0.9])
    agg = C.aggregate_patients(pids, p, valid=np.array([True, False, True]), min_valid=2)
    assert np.isnan(agg.scores[0]) and np.isnan(agg.scores[1])


@pytest.mark.unit
def test_aggregate_patients_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="length"):
        C.aggregate_patients(np.array(["a", "b"]), np.array([0.1]))


# --------------------------------------------------------------------- thresholds + decisions
@pytest.mark.unit
def test_fit_thresholds_needs_both_classes() -> None:
    with pytest.raises(ValueError, match="both classes"):
        C.fit_thresholds(np.array([0.1, 0.2]), np.array([0, 0]), alpha_far=0.1, alpha_miss=0.1)


@pytest.mark.unit
def test_thresholds_are_frozen() -> None:
    thr = C.fit_thresholds(np.linspace(0, 1, 40), np.tile([0, 1], 20), alpha_far=0.2, alpha_miss=0.2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        thr.q_control = 0.0  # type: ignore[misc]


@pytest.mark.unit
def test_decide_maps_prediction_sets_to_states() -> None:
    # control accepted when p <= 0.6; stroke accepted when 1 - p <= 0.6, i.e. p >= 0.4
    thr = C.MondrianThresholds(q_control=0.6, q_stroke=0.6, alpha_far=0.1, alpha_miss=0.1, n_control=50, n_stroke=50)
    assert C.decide(0.9, thr).state == "alert"
    assert C.decide(0.1, thr).state == "clear"
    mid = C.decide(0.5, thr)
    assert mid.state == "no_decision" and mid.reason == "ambiguous"


@pytest.mark.unit
def test_decide_reports_conflict_when_both_classes_are_rejected() -> None:
    thr = C.MondrianThresholds(q_control=0.3, q_stroke=0.3, alpha_far=0.1, alpha_miss=0.1, n_control=50, n_stroke=50)
    d = C.decide(0.5, thr)  # control needs p <= 0.3, stroke needs p >= 0.7
    assert d.state == "no_decision" and d.reason == "conflict"


@pytest.mark.unit
def test_decide_withholds_on_missing_quality() -> None:
    thr = C.MondrianThresholds(q_control=0.6, q_stroke=0.6, alpha_far=0.1, alpha_miss=0.1, n_control=50, n_stroke=50)
    d = C.decide(float("nan"), thr)
    assert d.state == "no_decision" and d.reason == "quality"


@pytest.mark.unit
def test_never_alerts_when_calibration_cannot_support_alpha() -> None:
    thr = C.fit_thresholds(np.array([0.1, 0.2, 0.9, 0.8]), np.array([0, 0, 1, 1]), alpha_far=0.05, alpha_miss=0.05)
    assert thr.q_control == np.inf
    assert C.decide(0.999, thr).state != "alert"


# --------------------------------------------------------------------- evaluation helpers
@pytest.mark.unit
def test_stratified_half_split_keeps_both_classes_on_both_sides() -> None:
    y = np.r_[np.zeros(50, int), np.ones(24, int)]
    cal, test = C.stratified_half_split(y, np.random.default_rng(0))
    assert set(cal) | set(test) == set(range(74)) and not set(cal) & set(test)
    assert y[cal].sum() == 12 and y[test].sum() == 12
    assert (y[cal] == 0).sum() == 25


@pytest.mark.unit
def test_decision_metrics() -> None:
    states = np.array(["alert", "clear", "no_decision", "alert", "clear", "no_decision"])
    y = np.array([0, 0, 0, 1, 1, 1])
    m = C.decision_metrics(states, y)
    assert m["far"] == pytest.approx(1 / 3)  # alerts among controls
    assert m["miss"] == pytest.approx(1 / 3)  # clears among strokes
    assert m["no_decision_control"] == pytest.approx(1 / 3)
    assert m["no_decision_stroke"] == pytest.approx(1 / 3)
    assert m["sensitivity"] == pytest.approx(1 / 3)
    assert m["accuracy_decided"] == pytest.approx(0.5)


@pytest.mark.unit
def test_decision_metrics_with_nothing_decided() -> None:
    m = C.decision_metrics(np.array(["no_decision"] * 4), np.array([0, 0, 1, 1]))
    assert m["far"] == 0.0 and np.isnan(m["accuracy_decided"])


# --------------------------------------------------------------------- E12: calibration size
@pytest.mark.unit
@pytest.mark.parametrize("alpha, n", [(0.2, 4), (0.1, 9), (0.05, 19)])
def test_min_calibration_size_is_the_smallest_n_with_a_finite_threshold(alpha: float, n: int) -> None:
    assert C.min_calibration_size(alpha) == n
    assert np.isfinite(C.conformal_quantile(np.arange(float(n)), alpha))
    assert not np.isfinite(C.conformal_quantile(np.arange(float(n - 1)), alpha))


@pytest.mark.unit
def test_sized_split_takes_exact_counts_per_class() -> None:
    y = np.r_[np.zeros(50, int), np.ones(24, int)]
    cal, test = C.sized_split(y, n_control=10, n_stroke=6, rng=np.random.default_rng(0))
    assert (y[cal] == 0).sum() == 10 and (y[cal] == 1).sum() == 6
    assert set(cal) | set(test) == set(range(74)) and not set(cal) & set(test)


@pytest.mark.unit
def test_sized_split_rejects_more_than_available() -> None:
    y = np.r_[np.zeros(5, int), np.ones(5, int)]
    with pytest.raises(ValueError, match="stroke"):
        C.sized_split(y, n_control=2, n_stroke=5, rng=np.random.default_rng(0))


# --------------------------------------------------------------------- guarantee (Monte Carlo)
def _draw(rng: np.random.Generator, n_control: int, n_stroke: int) -> tuple[np.ndarray, np.ndarray]:
    """Overlapping patient-level score distributions (AUC ~0.8), exchangeable patients."""
    s0 = 1 / (1 + np.exp(-(rng.normal(-0.6, 1.0, n_control))))
    s1 = 1 / (1 + np.exp(-(rng.normal(0.6, 1.0, n_stroke))))
    return np.r_[s0, s1], np.r_[np.zeros(n_control, int), np.ones(n_stroke, int)]


@pytest.mark.unit
@pytest.mark.parametrize("alpha", [0.1, 0.2])
def test_false_alert_rate_is_controlled_on_exchangeable_patients(alpha: float) -> None:
    rng = np.random.default_rng(0)
    alerts, controls, misses, strokes = 0, 0, 0, 0
    for _ in range(1500):
        p_cal, y_cal = _draw(rng, 25, 12)
        p_te, y_te = _draw(rng, 25, 12)
        thr = C.fit_thresholds(p_cal, y_cal, alpha_far=alpha, alpha_miss=alpha)
        states = np.array([C.decide(p, thr).state for p in p_te])
        alerts += int(np.sum((states == "alert") & (y_te == 0)))
        controls += int(np.sum(y_te == 0))
        misses += int(np.sum((states == "clear") & (y_te == 1)))
        strokes += int(np.sum(y_te == 1))
    far, miss = alerts / controls, misses / strokes
    assert far <= alpha + 0.01
    assert far >= alpha - 0.06  # valid but not vacuous
    assert miss <= alpha + 0.015


@pytest.mark.unit
def test_window_level_any_alert_breaks_the_patient_level_guarantee() -> None:
    """Why calibration must be patient-level: a per-window alpha does not bound
    the share of control patients who see at least one alert."""
    rng = np.random.default_rng(1)
    alpha, n_win = 0.1, 20
    alerted, total = 0, 0

    def windows(n: int, mu: float) -> np.ndarray:
        # patient random effect + window noise -> windows within a patient are correlated
        eff = rng.normal(mu, 0.8, n)[:, None]
        return 1 / (1 + np.exp(-(eff + rng.normal(0, 0.8, (n, n_win)))))

    for _ in range(300):
        cal0, cal1 = windows(25, -0.6), windows(12, 0.6)
        thr = C.fit_thresholds(
            np.r_[cal0.ravel(), cal1.ravel()], np.r_[np.zeros(cal0.size, int), np.ones(cal1.size, int)],
            alpha_far=alpha, alpha_miss=alpha,
        )
        te0 = windows(25, -0.6)
        any_alert = np.array([[C.decide(p, thr).state == "alert" for p in row] for row in te0]).any(axis=1)
        alerted += int(any_alert.sum())
        total += te0.shape[0]
    assert alerted / total > 2 * alpha
