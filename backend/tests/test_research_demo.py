from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _auth_headers(client: TestClient) -> dict:
    r = client.post(
        "/api/auth/login",
        json={"email": "doctor@neuratriage.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def test_research_metrics_endpoint_uses_real_result_files() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/research/metrics", headers=headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert "conditions" in data
    assert "limitations" in data
    assert "exploratory_datasets" in data
    assert "exploratory_results" in data
    assert "qc" in data
    assert any("clinical" in item.lower() for item in data["limitations"])


def test_research_metrics_reports_exploratory_hemorrhagic_dataset() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/research/metrics", headers=headers)
    assert r.status_code == 200
    hs = r.json()["data"]["exploratory_datasets"]["hemorrhagic"]
    assert "available" in hs
    if hs["available"]:
        assert hs["n_patients"] >= 4
        assert hs["label_counts"].get("2", 0) >= 1
        assert hs["validated_for_3class_cv"] is False


def test_research_metrics_reports_3class_exploratory_result() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/research/metrics", headers=headers)
    assert r.status_code == 200
    three_class = r.json()["data"]["exploratory_results"]["three_class"]
    assert "available" in three_class
    if three_class["available"]:
        assert three_class["task"] == "multiclass"
        assert three_class["folds"] == 4
        assert three_class["fast"] is False
        assert three_class["claim_status"] == "exploratory_positive_trend"
        assert len(three_class["conditions"]) >= 2


def test_research_metrics_reports_hemorrhagic_qc() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/research/metrics", headers=headers)
    assert r.status_code == 200
    qc = r.json()["data"]["qc"]["hemorrhagic"]
    assert "available" in qc
    if qc["available"]:
        assert qc["n_patients"] >= 4
        assert qc["total_retained_windows"] >= 88
        assert isinstance(qc["rows"], list)
        assert qc["rows"]


def test_replay_cases_are_allow_listed_file_ids() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/replay/cases", headers=headers)
    assert r.status_code == 200
    cases = r.json()["data"]
    assert isinstance(cases, list)
    assert cases
    assert all("/" not in c["id"] and "\\" not in c["id"] for c in cases)
    assert any(c.get("class_hint") == "hemorrhagic" for c in cases)
