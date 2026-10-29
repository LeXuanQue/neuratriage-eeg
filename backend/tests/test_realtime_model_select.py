"""REALTIME_MODEL setting: 'features' (deployed LightGBM) or 'riemann' (window model)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import riemann_model as rm
from app.services.model_manager import ModelManager


def _tiny_riemann_model(path: Path) -> Path:
    rng = np.random.default_rng(0)
    x = rng.standard_normal((40, 18, 256))
    y = np.array([0, 1] * 20)
    rm.RiemannStrokeModel.fit(x, y, channels=[f"c{i}" for i in range(18)], fs=256.0, window_sec=1.0).save(path)
    return path


def test_features_mode_returns_no_window_model(tmp_path: Path) -> None:
    mgr = ModelManager()

    assert mgr.get_window_model("features", tmp_path / "absent.joblib") is None


def test_riemann_mode_loads_and_caches_the_window_model(tmp_path: Path) -> None:
    path = _tiny_riemann_model(tmp_path / "riemann.joblib")
    mgr = ModelManager()

    first = mgr.get_window_model("riemann", path)
    second = mgr.get_window_model("riemann", path)

    assert isinstance(first, rm.RiemannStrokeModel) and first is second


def test_riemann_mode_without_a_model_file_fails_loudly(tmp_path: Path) -> None:
    # Silently falling back to the feature model would mislabel what the clinician sees.
    with pytest.raises(RuntimeError, match="riemann"):
        ModelManager().get_window_model("riemann", tmp_path / "absent.joblib")


def test_unknown_mode_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ModelManager().get_window_model("eegnet", tmp_path / "x.joblib")
