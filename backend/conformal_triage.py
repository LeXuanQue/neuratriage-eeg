"""R2: patient-level Mondrian conformal No-Decision with a false-alert guarantee.

The deployed No-Decision rule is a heuristic (SQI threshold + a band around p = 0.5). This
module replaces the band with class-conditional (Mondrian) split conformal prediction:

* nonconformity for "control" is p, for "stroke" is 1 - p;
* each class gets its own finite-sample quantile from calibration patients of that class;
* the prediction set is the classes not rejected. One class -> alert / clear; both or
  none -> No-Decision ("ambiguous" / "conflict"); too little usable signal -> "quality".

Guarantee (exchangeable patients): P(alert | control) <= alpha_far and
P(clear | stroke) <= alpha_miss, marginally over the calibration draw. Windows inside one
recording are not exchangeable (Chatterjee et al., AIME 2026), so the unit is the patient:
window probabilities are averaged per patient before calibration and decision. A per-window
alpha does not bound the share of control patients who ever see an alert.

The guarantee is conditional on the quality gate: calibrate and decide only on patients
that pass it, and report how many were withheld for quality.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

STATES = ("alert", "clear", "no_decision")


@dataclass(frozen=True)
class MondrianThresholds:
    q_control: float  # accept "control" iff p <= q_control
    q_stroke: float  # accept "stroke" iff 1 - p <= q_stroke
    alpha_far: float
    alpha_miss: float
    n_control: int
    n_stroke: int


@dataclass(frozen=True)
class Decision:
    state: str  # alert | clear | no_decision
    reason: str  # "" for alert/clear; ambiguous | conflict | quality for no_decision


@dataclass(frozen=True)
class PatientScores:
    pids: Tuple[str, ...]
    scores: np.ndarray  # mean valid-window probability, nan when too few valid windows
    n_valid: Tuple[int, ...]


def conformal_quantile(scores: np.ndarray, alpha: float) -> float:
    """Split-conformal threshold: the ceil((n+1)(1-alpha))-th smallest score, inf if > n."""
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    s = np.asarray(scores, dtype=float)
    s = np.sort(s[np.isfinite(s)])
    k = math.ceil((s.size + 1) * (1.0 - alpha))
    return float(s[k - 1]) if 1 <= k <= s.size else float("inf")


def aggregate_patients(
    pids: np.ndarray, probs: np.ndarray, valid: Optional[np.ndarray] = None, min_valid: int = 1
) -> PatientScores:
    """Mean probability over each patient's valid windows (order of first appearance)."""
    pids, probs = np.asarray(pids), np.asarray(probs, dtype=float)
    valid = np.ones(probs.shape, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    if not (pids.shape == probs.shape == valid.shape):
        raise ValueError(f"length mismatch: pids {pids.shape}, probs {probs.shape}, valid {valid.shape}")
    _, first = np.unique(pids, return_index=True)
    order = pids[np.sort(first)]
    scores, counts = [], []
    for pid in order:
        m = (pids == pid) & valid & np.isfinite(probs)
        counts.append(int(m.sum()))
        scores.append(float(probs[m].mean()) if m.sum() >= max(min_valid, 1) else float("nan"))
    return PatientScores(pids=tuple(str(p) for p in order), scores=np.array(scores), n_valid=tuple(counts))


def fit_thresholds(probs: np.ndarray, labels: np.ndarray, alpha_far: float, alpha_miss: float) -> MondrianThresholds:
    """Class-conditional thresholds from calibration units (patients) that passed the gate."""
    probs, labels = np.asarray(probs, dtype=float), np.asarray(labels)
    ok = np.isfinite(probs)
    p0, p1 = probs[ok & (labels == 0)], probs[ok & (labels == 1)]
    if p0.size == 0 or p1.size == 0:
        raise ValueError("calibration set needs both classes (control and stroke)")
    return MondrianThresholds(
        q_control=conformal_quantile(p0, alpha_far),
        q_stroke=conformal_quantile(1.0 - p1, alpha_miss),
        alpha_far=alpha_far,
        alpha_miss=alpha_miss,
        n_control=int(p0.size),
        n_stroke=int(p1.size),
    )


def stratified_half_split(labels: np.ndarray, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray]:
    """Random calibration/test index split, half of each class on each side."""
    labels = np.asarray(labels)
    cal, test = [], []
    for cls in np.unique(labels):
        idx = rng.permutation(np.flatnonzero(labels == cls))
        cut = idx.size // 2
        cal.append(idx[:cut])
        test.append(idx[cut:])
    return np.sort(np.concatenate(cal)), np.sort(np.concatenate(test))


def min_calibration_size(alpha: float) -> int:
    """Smallest per-class calibration size with a finite conformal threshold.

    With fewer patients of a class, ceil((n+1)(1-alpha)) > n and that class can never be
    rejected: e.g. at alpha = 0.1 the system cannot alert before 9 controls are calibrated.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    n = 1
    while math.ceil((n + 1) * (1.0 - alpha)) > n:
        n += 1
    return n


def sized_split(
    labels: np.ndarray, n_control: int, n_stroke: int, rng: np.random.Generator
) -> Tuple[np.ndarray, np.ndarray]:
    """Calibration set of exactly n_control / n_stroke patients; the rest is the test set."""
    labels = np.asarray(labels)
    cal = []
    for cls, n, name in ((0, n_control, "control"), (1, n_stroke, "stroke")):
        idx = np.flatnonzero(labels == cls)
        if not 0 < n < idx.size:
            raise ValueError(f"need 0 < n_{name} < {idx.size} {name} patients, got {n}")
        cal.append(rng.choice(idx, size=n, replace=False))
    cal_idx = np.sort(np.concatenate(cal))
    return cal_idx, np.setdiff1d(np.arange(labels.size), cal_idx)


def _share(mask: np.ndarray, of: np.ndarray) -> float:
    return float(mask[of].mean()) if of.any() else float("nan")


def decision_metrics(states: np.ndarray, labels: np.ndarray) -> dict:
    """Patient-level rates of a set of triage decisions (labels: 1 stroke, 0 control)."""
    states, labels = np.asarray(states), np.asarray(labels)
    ctrl, stroke = labels == 0, labels == 1
    decided = states != "no_decision"
    correct = ((states == "alert") & stroke) | ((states == "clear") & ctrl)
    return {
        "far": _share(states == "alert", ctrl),
        "miss": _share(states == "clear", stroke),
        "sensitivity": _share(states == "alert", stroke),
        "no_decision_control": _share(~decided, ctrl),
        "no_decision_stroke": _share(~decided, stroke),
        "accuracy_decided": float(correct[decided].mean()) if decided.any() else float("nan"),
    }


def decide(prob: float, thresholds: MondrianThresholds) -> Decision:
    """Alert only when 'control' is rejected and 'stroke' is not (and symmetrically for clear)."""
    if not np.isfinite(prob):
        return Decision("no_decision", "quality")
    accept_control = prob <= thresholds.q_control
    accept_stroke = (1.0 - prob) <= thresholds.q_stroke
    if accept_stroke and not accept_control:
        return Decision("alert", "")
    if accept_control and not accept_stroke:
        return Decision("clear", "")
    return Decision("no_decision", "ambiguous" if accept_control else "conflict")
