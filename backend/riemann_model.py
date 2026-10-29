"""Riemannian tangent-space stroke classifier for the real-time path.

Each 4 s window becomes an 18x18 spatial covariance (OAS-shrunk, trace-normalised),
is mapped to the tangent space at the training-set Riemannian mean, and scored by a
logistic regression. Trace normalisation removes the device's overall gain (and the
V-vs-uV unit difference between sources and the uncalibrated headband) while keeping
relative channel power and inter-channel correlation.

In the leave-source-out study (scripts/leave_source_out.py) this family was the most
transferable to unseen devices once eye state was matched (patient AUC ~0.81-0.86),
where the entropy/MFDFA features fell to 0.57-0.73. Pure numpy + scikit-learn, so the
app venv needs no pyriemann; tests check equality with pyriemann where installed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
from sklearn.covariance import oas
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


def _eig_fn(c: np.ndarray, fn) -> np.ndarray:  # noqa: ANN001
    w, v = np.linalg.eigh(c)
    return (v * fn(w)[..., None, :]) @ np.swapaxes(v, -1, -2)


def oas_covariance(x: np.ndarray) -> np.ndarray:
    """OAS-shrunk covariance of one (channels, samples) window; always SPD."""
    return oas(np.asarray(x, dtype=float).T)[0]


def window_covariance(x: np.ndarray) -> np.ndarray:
    """OAS covariance scaled to trace == n_channels (gain/unit invariant)."""
    c = oas_covariance(x)
    return c * (c.shape[0] / np.trace(c))


def riemann_mean(covs: np.ndarray, tol: float = 1e-9, max_iter: int = 100) -> np.ndarray:
    """Affine-invariant (Karcher) mean by fixed-point iteration."""
    p = covs.mean(axis=0)
    for _ in range(max_iter):
        p_half = _eig_fn(p, np.sqrt)
        p_ihalf = _eig_fn(p, lambda w: 1.0 / np.sqrt(w))
        t = _eig_fn(p_ihalf @ covs @ p_ihalf, np.log).mean(axis=0)
        p = p_half @ _eig_fn(t, np.exp) @ p_half
        if np.linalg.norm(t) < tol:
            break
    return p


def tangent_vectors(covs: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """log(ref^-1/2 C ref^-1/2), upper triangle with sqrt(2) off-diagonal weights (pyriemann layout)."""
    r_ihalf = _eig_fn(ref, lambda w: 1.0 / np.sqrt(w))
    logs = _eig_fn(r_ihalf @ covs @ r_ihalf, np.log)
    n = ref.shape[0]
    iu = np.triu_indices(n)
    coeffs = (np.sqrt(2) * np.triu(np.ones((n, n)), 1) + np.eye(n))[iu]
    return logs[:, iu[0], iu[1]] * coeffs


@dataclass
class RiemannStrokeModel:
    reference: np.ndarray
    scaler: StandardScaler
    classifier: LogisticRegression
    channels: list[str]
    fs: float
    window_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def fit(cls, windows: np.ndarray, y: np.ndarray, channels: Sequence[str], fs: float,
            window_sec: float, c_reg: float = 0.1, metadata: dict[str, Any] | None = None) -> "RiemannStrokeModel":
        covs = np.stack([window_covariance(w) for w in windows])
        ref = riemann_mean(covs)
        feats = tangent_vectors(covs, ref)
        scaler = StandardScaler().fit(feats)
        clf = LogisticRegression(C=c_reg, class_weight="balanced", max_iter=5000)
        clf.fit(scaler.transform(feats), np.asarray(y, dtype=int))
        return cls(ref, scaler, clf, list(channels), float(fs), float(window_sec), dict(metadata or {}))

    def predict_proba_from_window(self, window: np.ndarray) -> np.ndarray:
        """[P(non-stroke), P(stroke)] for one preprocessed (channels, samples) window."""
        feats = tangent_vectors(window_covariance(window)[None], self.reference)
        return self.classifier.predict_proba(self.scaler.transform(feats))[0]

    def save(self, path: str | Path) -> None:
        joblib.dump(self, path)

    @staticmethod
    def load(path: str | Path) -> "RiemannStrokeModel":
        return joblib.load(path)
