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
    assert data["available"] is True
    assert data["task"] == "binary"
    assert "conditions" in data
    assert "paired_comparisons" in data
    assert "dataset" in data
    assert "limitations" in data
    assert "exploratory_datasets" not in data
    assert "exploratory_results" not in data
    assert "qc" not in data
    limitations = " ".join(data["limitations"]).lower()
    assert "binary" in limitations
    assert "confound" in limitations
    assert "clinical performance" in limitations


def test_research_metrics_dataset_is_binary_ns_is() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/research/metrics", headers=headers)
    assert r.status_code == 200
    dataset = r.json()["data"]["dataset"]
    class_names = dataset.get("class_names", {})
    patient_counts = dataset.get("patient_label_counts", {})
    assert class_names.get("0") == "non-stroke"
    assert class_names.get("1") == "ischemic"
    assert "2" not in class_names
    assert set(patient_counts).issubset({"0", "1"})


def test_replay_cases_are_allow_listed_file_ids() -> None:
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.get("/api/replay/cases", headers=headers)
    assert r.status_code == 200
    cases = r.json()["data"]
    assert isinstance(cases, list)
    assert cases
    assert all("/" not in c["id"] and "\\" not in c["id"] for c in cases)
    assert {c.get("class_hint") for c in cases}.issubset(
        {"ischemic", "non-stroke", "demo"}
    )
    assert not any(c.get("class_hint") == "hemorrhagic" for c in cases)
