"""Learned SQI v2 channel scorer: logistic regression over SQI v2 features, frozen to JSON.

On TUAR the hand-set SQI v2 weights detected annotated artifacts worse than v1, while a
logistic model over the same features beat v1 by 0.08 AUC (docs/paper_outline.md, section 6).
This module runs that model without sklearn or pickle: the fitted pipeline (median
imputation -> quantile transform to a normal -> logistic regression) is exported as plain
numbers by ``scripts/sqi_learned_scorer.py`` and replayed here with numpy.

The scorer only sets the channel *score*. Reasons and advice still come from the rules in
``sqi_v2``, so what the operator is told to fix stays interpretable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

import numpy as np
from scipy import stats

from sqi_v2 import CHANNEL_OK

# sklearn.preprocessing._data.BOUNDS_THRESHOLD: values this close to the fitted extremes map
# to the extremes, and the normal output is clipped just inside (0, 1) before the ppf.
_BOUNDS = 1e-7
_CLIP = (float(stats.norm.ppf(_BOUNDS - np.spacing(1))), float(stats.norm.ppf(1 - (_BOUNDS - np.spacing(1)))))


@dataclass(frozen=True)
class LearnedScorer:
    features: Tuple[str, ...]
    medians: Tuple[float, ...]
    quantiles: Tuple[Tuple[float, ...], ...]  # (n_quantiles, n_features)
    references: Tuple[float, ...]  # (n_quantiles,) uniform levels of the quantiles
    coef: Tuple[float, ...]
    intercept: float
    threshold: float  # P(artifact) above which a channel needs action

    def probability_matrix(self, x: np.ndarray) -> np.ndarray:
        """P(artifact) for each row of ``x`` (columns in ``self.features`` order)."""
        x = np.array(x, dtype=float, copy=True)
        med = np.asarray(self.medians, dtype=float)
        gaps = ~np.isfinite(x)
        x[gaps] = np.broadcast_to(med, x.shape)[gaps]
        q = np.asarray(self.quantiles, dtype=float)
        ref = np.asarray(self.references, dtype=float)
        z = np.empty_like(x)
        for j in range(x.shape[1]):
            z[:, j] = _to_normal(x[:, j], q[:, j], ref)
        logit = z @ np.asarray(self.coef, dtype=float) + float(self.intercept)
        return 1.0 / (1.0 + np.exp(-logit))

    def probability(self, features: Mapping[str, float]) -> float:
        row = [features.get(name, float("nan")) for name in self.features]
        return float(self.probability_matrix(np.asarray([row], dtype=float))[0])

    def channel_score(self, features: Mapping[str, float]) -> float:
        return score_from_probability(self.probability(features), self.threshold)


def _to_normal(col: np.ndarray, quantiles: np.ndarray, references: np.ndarray) -> np.ndarray:
    """Forward QuantileTransformer(output_distribution='normal') for one column, as sklearn does it."""
    lower = col - _BOUNDS < quantiles[0]
    upper = col + _BOUNDS > quantiles[-1]
    u = 0.5 * (np.interp(col, quantiles, references) - np.interp(-col, -quantiles[::-1], -references[::-1]))
    u[upper] = 1.0
    u[lower] = 0.0
    with np.errstate(divide="ignore"):
        return np.clip(stats.norm.ppf(u), *_CLIP)


def score_from_probability(p: float, threshold: float) -> float:
    """Map P(artifact) to a 0-1 channel score with ``threshold`` landing exactly on CHANNEL_OK.

    Piecewise linear and decreasing, so ``score >= CHANNEL_OK`` iff ``p <= threshold`` and
    everything downstream (window score, guidance, the No-Decision gate) keeps its meaning."""
    p = float(np.clip(p, 0.0, 1.0))
    t = float(np.clip(threshold, 1e-9, 1 - 1e-9))
    if p <= t:
        return 1.0 - (1.0 - CHANNEL_OK) * p / t
    return CHANNEL_OK * (1.0 - p) / (1.0 - t)


def learned_scorer_from_dict(d: Mapping[str, object]) -> LearnedScorer:
    def tup(v: Sequence) -> Tuple[float, ...]:
        return tuple(float(a) for a in v)

    scorer = LearnedScorer(
        features=tuple(str(f) for f in d["features"]),
        medians=tup(d["medians"]),
        quantiles=tuple(tup(row) for row in d["quantiles"]),
        references=tup(d["references"]),
        coef=tup(d["coef"]),
        intercept=float(d["intercept"]),
        threshold=float(d["threshold"]),
    )
    _check_shapes(scorer)
    return scorer


def _check_shapes(s: LearnedScorer) -> None:
    """Fail at load, not on the first live window, when a scorer file is inconsistent."""
    n = len(s.features)
    if n == 0 or len(s.medians) != n or len(s.coef) != n:
        raise ValueError("scorer features, medians and coef must have the same non-zero length")
    if len(s.quantiles) != len(s.references) or len(s.references) < 2:
        raise ValueError("scorer needs one reference level per quantile row (at least two)")
    if any(len(row) != n for row in s.quantiles):
        raise ValueError("every quantile row must have one value per feature")
    if not 0.0 < s.threshold < 1.0:
        raise ValueError("scorer threshold must be a probability strictly between 0 and 1")
