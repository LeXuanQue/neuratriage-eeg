"""The vectorized MFDFA must reproduce the original per-segment polyfit loop.

The deployed model was trained on features from the loop implementation, so the
speed-up is only acceptable if it changes no feature value beyond float noise.
`_reference_mfdfa_from_profile` is a frozen copy of the pre-optimisation code.
"""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
import pytest

import eeg_stroke_pipeline as P

Q = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)


def _reference_mfdfa_from_profile(
    profile: np.ndarray,
    q_values: Sequence[int],
    order: int = 1,
    scale_min: int = 16,
    scale_count: int = 8,
) -> Dict[str, np.ndarray]:
    profile = np.asarray(profile, dtype=float)
    n = profile.size
    scale_max = max(scale_min + 2, n // 10)
    scales = np.unique(np.floor(np.geomspace(scale_min, scale_max, num=scale_count)).astype(int))
    scales = scales[(scales > order + 2) & (scales < n // 2)]
    q_values = np.asarray(q_values, dtype=float)
    fluct, valid_scales = [], []
    for s in scales:
        ns = n // s
        if ns < 2:
            continue
        vars_ = []
        t = np.arange(s, dtype=float)
        for v in range(ns):
            seg = profile[v * s : (v + 1) * s]
            vars_.append(np.mean((seg - np.polyval(np.polyfit(t, seg, order), t)) ** 2))
        for v in range(ns):
            start = n - (v + 1) * s
            seg = profile[start : start + s]
            vars_.append(np.mean((seg - np.polyval(np.polyfit(t, seg, order), t)) ** 2))
        vars_ = np.maximum(np.asarray(vars_, dtype=float), P.EPS)
        fluct.append([(np.mean(vars_ ** (q / 2.0))) ** (1.0 / q) for q in q_values])
        valid_scales.append(s)
    fluct = np.asarray(fluct, dtype=float)
    valid_scales = np.asarray(valid_scales, dtype=float)
    log_s = np.log2(valid_scales)
    log_f = np.log2(np.maximum(fluct, P.EPS))
    hq = np.array([np.polyfit(log_s, log_f[:, i], 1)[0] for i in range(log_f.shape[1])])
    tau = q_values * hq - 1.0
    alpha = np.gradient(tau, q_values)
    return {"q": q_values, "scales": valid_scales, "hq": hq, "tau": tau,
            "alpha": alpha, "f_alpha": q_values * alpha - tau}


def _signals() -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    return {
        "white_1024": rng.standard_normal(1024),          # 4 s at 256 Hz (live buffer)
        "random_walk_1024": np.cumsum(rng.standard_normal(1024)),
        "white_odd_1000": rng.standard_normal(1000),      # n not divisible by most scales
        "eeg_like_1024": np.sin(np.arange(1024) * 2 * np.pi * 10 / 256)
        + 0.5 * rng.standard_normal(1024),
    }


@pytest.mark.parametrize("name", list(_signals()))
@pytest.mark.parametrize("order", [1, 2])
def test_vectorized_mfdfa_matches_reference_loop(name: str, order: int) -> None:
    profile = P.compute_profile(_signals()[name])

    expected = _reference_mfdfa_from_profile(profile, Q, order=order)
    actual = P._mfdfa_from_profile(profile, Q, order=order)

    for key in ("scales", "hq", "tau", "alpha", "f_alpha"):
        np.testing.assert_allclose(actual[key], expected[key], rtol=1e-9, atol=1e-10, err_msg=key)


def test_summary_features_unchanged_on_real_window() -> None:
    """End-to-end guard on the 10 summary features the classifier actually reads."""
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.standard_normal(1024)) * 0.1 + rng.standard_normal(1024)

    expected = P.summarize_mfdfa_spectrum(_reference_mfdfa_from_profile(P.compute_profile(x), Q))
    actual = P.mfdfa_features(x, q_values=Q, order=1, scale_min=16, scale_count=8)

    for key, value in expected.items():
        assert actual[key] == pytest.approx(value, rel=1e-9, abs=1e-10), key
