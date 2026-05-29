from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


def unwrap(response):
    body = response.json()
    assert body["success"] is True
    return body["data"]


def test_health_uses_fastapi_contract():
    with TestClient(app) as client:
        data = unwrap(client.get("/api/health"))
    assert data["status"] == "ok"
    assert data["app"] == "NeuraTriage EEG"
    assert "version" in data


def test_live_uses_envelope_with_payload_data():
    with TestClient(app) as client:
        data = unwrap(client.get("/api/live?scenario=IS"))
    assert data["scenario"] == "IS"
    assert "probabilities" in data
    assert "history" in data
    assert "features" in data


def test_demo_login_returns_access_token():
    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"email": "doctor@neuratriage.com", "password": "demo1234"},
        )
        data = unwrap(response)
    assert data["access_token"]
    assert data["user"]["role"] == "clinician"
