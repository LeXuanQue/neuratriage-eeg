"""POST /api/study/events: append-only JSONL event log for Study 1 (docs/user_study_protocol.md)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "study_log_dir", str(tmp_path))
    with TestClient(app) as c:
        yield c


def _auth(c: TestClient) -> dict:
    r = c.post("/api/auth/login", json={"email": "doctor@neuratriage.com", "password": "demo1234"})
    return {"Authorization": "Bearer " + r.json()["data"]["access_token"]}


def _event(**over) -> dict:
    ev = {
        "participant": "P07", "condition": "G", "trial": 1, "type": "quality",
        "client_ts": "2026-11-17T09:30:12.050Z",
        "payload": {"score": 0.62, "worst": "AF4", "reason": "flat"},
    }
    ev.update(over)
    return ev


def test_event_is_appended_as_one_json_line(client: TestClient, tmp_path: Path) -> None:
    h = _auth(client)
    assert client.post("/api/study/events", json=_event(), headers=h).status_code == 200
    assert client.post("/api/study/events", json=_event(type="trial_end", payload={}), headers=h).status_code == 200
    lines = (tmp_path / "P07.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["participant"] == "P07" and first["condition"] == "G" and first["type"] == "quality"
    assert first["payload"]["worst"] == "AF4"
    assert first["server_ts"].endswith("Z")


@pytest.mark.parametrize("participant", ["Nguyen Van A", "p07", "P7", "../P07", "P0712"])
def test_participant_must_be_a_pseudonymous_code(client: TestClient, participant: str) -> None:
    r = client.post("/api/study/events", json=_event(participant=participant), headers=_auth(client))
    assert r.status_code == 422


def test_unknown_event_type_and_condition_are_rejected(client: TestClient) -> None:
    h = _auth(client)
    assert client.post("/api/study/events", json=_event(type="anything"), headers=h).status_code == 422
    assert client.post("/api/study/events", json=_event(condition="X"), headers=h).status_code == 422


def test_oversized_payload_is_rejected(client: TestClient) -> None:
    big = {"note": "x" * 5000}
    r = client.post("/api/study/events", json=_event(type="note", payload=big), headers=_auth(client))
    assert r.status_code == 422


def test_requires_login(client: TestClient) -> None:
    assert client.post("/api/study/events", json=_event()).status_code == 401
