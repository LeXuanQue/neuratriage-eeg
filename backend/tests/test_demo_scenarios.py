from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.demo_scenarios import list_demo_scenarios
from app.services.replay_cases import resolve_replay_case


def _auth_headers(client: TestClient) -> dict:
    r = client.post(
        "/api/auth/login",
        json={"email": "doctor@neuratriage.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def test_demo_scenarios_endpoint_returns_runnable_scenarios() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/demo/scenarios", headers=headers)
    assert r.status_code == 200
    scenarios = r.json()["data"]
    assert isinstance(scenarios, list)
    assert scenarios, "demo mode needs at least one runnable scenario"
    ids = {s["id"] for s in scenarios}
    assert {"ischemic-alert", "healthy-monitor", "signal-artifact",
            "continuous-visual"} <= ids


def test_every_scenario_points_at_a_resolvable_replay_case() -> None:
    for scenario in list_demo_scenarios():
        case_id = scenario["replay_case"]
        assert "/" not in case_id and "\\" not in case_id
        assert resolve_replay_case(case_id) is not None, case_id


def test_scenarios_carry_bilingual_copy_and_expected_outcome() -> None:
    for scenario in list_demo_scenarios():
        for field in ("title", "summary", "expect"):
            assert set(scenario[field]) == {"vi", "en"}, (field, scenario["id"])
            assert all(str(v).strip() for v in scenario[field].values())
        assert scenario["expected_status"] in {"alert", "monitor", "no-decision", "mixed"}
        assert isinstance(scenario["artifact"], bool)
        assert isinstance(scenario["loop"], bool)
        assert isinstance(scenario["stitched"], bool)
        assert scenario["duration_sec"] > 0
        # "watch for it around here" hint — must land inside the recording.
        assert 0 < scenario["expect_at_sec"] < scenario["duration_sec"]


def test_artifact_scenario_requests_injection_and_alert_scenario_does_not() -> None:
    by_id = {s["id"]: s for s in list_demo_scenarios()}
    assert by_id["signal-artifact"]["artifact"] is True
    assert by_id["signal-artifact"]["expected_status"] == "no-decision"
    assert by_id["ischemic-alert"]["artifact"] is False
    assert by_id["ischemic-alert"]["expected_status"] == "alert"
    assert by_id["healthy-monitor"]["expected_status"] == "monitor"


def test_demo_scenarios_require_authentication() -> None:
    with TestClient(app) as client:
        r = client.get("/api/demo/scenarios")
    assert r.status_code == 401
