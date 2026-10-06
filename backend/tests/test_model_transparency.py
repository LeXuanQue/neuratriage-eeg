"""Model transparency + honest demo scenarios (2026-10-06).

- GET /api/model/info tells the UI which real-time scorer is active and, for the
  riemann model, the held-out numbers and limits stored in its metadata.
- EXTRA_REPLAY_DIR is an opt-in folder (outside the repo) for extra replay cases,
  used by the "unseen device -> false alert" failure-mode scenario.
- Every demo scenario says which model its expectation was measured with.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import demo_scenarios, replay_cases


def _headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"email": "doctor@neuratriage.com", "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _tiny_riemann(path: Path) -> Path:
    import riemann_model as rm
    rng = np.random.default_rng(0)
    meta = {
        "created": "2026-10-06",
        "train_sources": {"xuanwu": {"windows": 10, "patients": 2}},
        "intended_use": "research prototype for triage support; NOT a diagnostic device",
        "known_limits": ["cannot separate IS from HS"],
        "heldout_patient_auc": {"eyes": [
            {"train": ["xuanwu", "oslo45"], "test": ["tianjin", "physionet_eo"], "patient_auc": 0.816},
            {"train": ["xuanwu", "oslo45"], "test": ["tianjin", "physionet_ec"], "patient_auc": 0.963},
        ]},
    }
    rm.RiemannStrokeModel.fit(rng.standard_normal((20, 18, 256)), np.array([0, 1] * 10),
                              channels=[f"c{i}" for i in range(18)], fs=256.0, window_sec=1.0,
                              metadata=meta).save(path)
    return path


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch):
    s = get_settings()
    monkeypatch.setattr(s, "realtime_model", s.realtime_model)
    monkeypatch.setattr(s, "riemann_model_path", s.riemann_model_path)
    monkeypatch.setattr(s, "extra_replay_dir", s.extra_replay_dir)
    return s


def test_model_info_requires_auth() -> None:
    with TestClient(app) as client:
        assert client.get("/api/model/info").status_code in (401, 403)


def test_model_info_reports_feature_mode_without_leaking_paths(settings) -> None:
    settings.realtime_model = "features"
    with TestClient(app) as client:
        data = client.get("/api/model/info", headers=_headers(client)).json()["data"]

    assert data["realtime_model"] == "features"
    assert "file" in data["feature_model"] and "loaded" in data["feature_model"]
    assert ":" not in str(data["feature_model"].get("file") or "")      # file name only, no C:\...
    assert data["clinical_use"] is False


def test_model_info_exposes_riemann_heldout_numbers_and_limits(settings, tmp_path: Path) -> None:
    settings.realtime_model = "riemann"
    settings.riemann_model_path = str(_tiny_riemann(tmp_path / "r.joblib"))
    with TestClient(app) as client:
        data = client.get("/api/model/info", headers=_headers(client)).json()["data"]

    r = data["riemann"]
    assert data["realtime_model"] == "riemann" and r["available"] is True
    assert r["eye_matched_patient_auc"] == [0.816]                        # only tests vs eyes-open controls
    assert "cannot separate IS from HS" in r["known_limits"]
    assert r["train_sources"] == {"xuanwu": {"windows": 10, "patients": 2}}
    assert r["file"] == "r.joblib"


def test_model_info_reports_missing_riemann_file_instead_of_failing(settings, tmp_path: Path) -> None:
    settings.realtime_model = "riemann"
    settings.riemann_model_path = str(tmp_path / "absent.joblib")
    with TestClient(app) as client:
        r = client.get("/api/model/info", headers=_headers(client))

    assert r.status_code == 200
    assert r.json()["data"]["riemann"]["available"] is False


def test_extra_replay_dir_is_opt_in_and_confined(settings, tmp_path: Path) -> None:
    case = tmp_path / "os-999.npz"
    np.savez(case, data=np.zeros((18, 512), np.float32), fs=256.0)

    settings.extra_replay_dir = ""
    assert replay_cases.resolve_replay_case("os-999.npz") is None

    settings.extra_replay_dir = str(tmp_path)
    assert replay_cases.resolve_replay_case("os-999.npz") == case.resolve()
    assert replay_cases.resolve_replay_case("../os-999.npz") is None


def test_every_scenario_states_the_model_its_expectation_was_measured_with() -> None:
    for sc in demo_scenarios.list_demo_scenarios():
        assert set(sc["expect_models"]) <= {"features", "riemann"} and sc["expect_models"], sc["id"]
        assert isinstance(sc["failure_mode"], bool)
        assert isinstance(sc["in_riemann_training"], bool)


def test_failure_mode_scenario_appears_only_when_its_case_is_available(settings, tmp_path: Path) -> None:
    settings.extra_replay_dir = str(tmp_path)
    assert "unseen-device-false-alert" not in {s["id"] for s in demo_scenarios.list_demo_scenarios()}

    np.savez(tmp_path / "os-056.npz", data=np.zeros((18, 256 * 30), np.float32), fs=256.0)
    by_id = {s["id"]: s for s in demo_scenarios.list_demo_scenarios()}

    sc = by_id["unseen-device-false-alert"]
    assert sc["failure_mode"] is True and sc["class_hint"] == "non-stroke"
    assert sc["expect_models"] == ["riemann"]
