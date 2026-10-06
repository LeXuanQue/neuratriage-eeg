"""Tests for backend/riemann_model.py (real-time Riemannian tangent-space classifier)."""
from __future__ import annotations

import numpy as np
import pytest

import riemann_model as rm


def _spd(rng: np.random.Generator, n: int = 4) -> np.ndarray:
    a = rng.standard_normal((n, n))
    return a @ a.T + n * np.eye(n)


def test_oas_covariance_is_spd_and_matches_sklearn() -> None:
    from sklearn.covariance import oas
    x = np.random.default_rng(0).standard_normal((6, 512))

    c = rm.oas_covariance(x)

    np.testing.assert_allclose(c, oas(x.T)[0], rtol=1e-10)
    assert np.all(np.linalg.eigvalsh(c) > 0)


def test_trace_normalisation_removes_overall_gain() -> None:
    x = np.random.default_rng(1).standard_normal((6, 512))

    np.testing.assert_allclose(rm.window_covariance(x * 1e-6), rm.window_covariance(x), rtol=1e-8)
    assert np.trace(rm.window_covariance(x)) == pytest.approx(6.0)


def test_riemann_mean_of_commuting_matrices_is_their_geometric_mean() -> None:
    d = np.array([[1.0, 4.0, 9.0], [4.0, 1.0, 1.0]])
    covs = np.stack([np.diag(r) for r in d])

    mean = rm.riemann_mean(covs)

    np.testing.assert_allclose(mean, np.diag(np.sqrt(d[0] * d[1])), atol=1e-9)


def test_tangent_vectors_match_pyriemann() -> None:
    ts = pytest.importorskip("pyriemann.utils.tangentspace")
    mean = pytest.importorskip("pyriemann.utils.mean")
    rng = np.random.default_rng(2)
    covs = np.stack([_spd(rng) for _ in range(8)])
    ref = rm.riemann_mean(covs)

    np.testing.assert_allclose(ref, mean.mean_riemann(covs), atol=1e-7)
    np.testing.assert_allclose(rm.tangent_vectors(covs, ref),
                               ts.tangent_space(covs, ref, metric="riemann"), atol=1e-8)


def _two_class_windows(rng: np.random.Generator, n: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Class 1 has stronger correlation between channels 0 and 1 (a spatial pattern)."""
    xs, ys = [], []
    for label in (0, 1):
        mix = np.eye(4)
        mix[1, 0] = 0.9 if label else 0.0
        for _ in range(n):
            xs.append(mix @ rng.standard_normal((4, 256)))
            ys.append(label)
    return np.stack(xs), np.array(ys)


def test_model_learns_a_spatial_pattern_and_round_trips(tmp_path) -> None:
    rng = np.random.default_rng(3)
    x, y = _two_class_windows(rng)
    model = rm.RiemannStrokeModel.fit(x, y, channels=["A", "B", "C", "D"], fs=256.0, window_sec=1.0)

    probs = np.array([model.predict_proba_from_window(w)[1] for w in x])
    assert probs[y == 1].mean() > 0.8 and probs[y == 0].mean() < 0.2

    path = tmp_path / "riemann.joblib"
    model.save(path)
    again = rm.RiemannStrokeModel.load(path)
    np.testing.assert_allclose(again.predict_proba_from_window(x[0]), model.predict_proba_from_window(x[0]))


def test_prediction_ignores_recording_units() -> None:
    rng = np.random.default_rng(4)
    x, y = _two_class_windows(rng)
    model = rm.RiemannStrokeModel.fit(x, y, channels=["A", "B", "C", "D"], fs=256.0, window_sec=1.0)

    np.testing.assert_allclose(model.predict_proba_from_window(x[5] * 1e-6),
                               model.predict_proba_from_window(x[5]), atol=1e-9)


def test_detector_uses_window_model_and_skips_handcrafted_features(monkeypatch) -> None:
    import eeg_stroke_pipeline as P

    class FixedModel:
        def predict_proba_from_window(self, window: np.ndarray) -> np.ndarray:
            assert window.shape == (18, 1024)                 # the 4 s buffer
            return np.array([0.1, 0.9])

    def _boom(**_: object) -> None:
        raise AssertionError("entropy/MFDFA must not run when a window model is set")

    monkeypatch.setattr(P, "build_feature_row_from_windows", _boom)
    det = P.RealTimeStrokeDetector(None, config=P.PipelineConfig(), window_model=FixedModel())
    rng = np.random.default_rng(5)

    events = []
    for _ in range(16):                                       # 8 s of 18-ch noise in 0.5 s chunks
        events += det.update(20.0 * rng.standard_normal((18, 128)))

    scored = [e for e in events if e["probabilities_raw"] is not None]
    assert scored and all(e["probabilities_raw"] == [0.1, 0.9] for e in scored)
