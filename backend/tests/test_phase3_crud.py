"""End-to-end CRUD + alerts tests over the FastAPI TestClient.

These tests share the dev SQLite database. We avoid the fact that there are
already pre-seed rows by using unique synthetic MRNs and cleaning up after.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def token(client: TestClient) -> str:
    r = client.post(
        "/api/auth/login",
        json={"email": "doctor@neuratriage.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


@pytest.fixture
def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Patients CRUD ────────────────────────────────────────────────────────


def test_patient_lifecycle_crud_with_contact(
    client: TestClient, auth_headers: dict
) -> None:
    mrn = f"MRN-TEST-{uuid.uuid4().hex[:8]}"
    body = {
        "full_name": "Pytest Patient",
        "mrn": mrn,
        "bed": "TEST-01",
        "gender": "M",
        "onset_minutes": 33,
    }

    r = client.post("/api/patients", json=body, headers=auth_headers)
    assert r.status_code == 201
    payload = r.json()
    assert payload["success"] is True
    pid = payload["data"]["id"]
    assert payload["data"]["full_name"] == "Pytest Patient"
    assert payload["data"]["mrn"] == mrn

    r = client.get(f"/api/patients/{pid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["data"]["bed"] == "TEST-01"

    r = client.put(
        f"/api/patients/{pid}",
        json={"bed": "TEST-02", "notes": "fixture"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["bed"] == "TEST-02"
    assert r.json()["data"]["notes"] == "fixture"

    contact_body = {
        "name": "Jane Doe",
        "relationship_label": "spouse",
        "email": "jane@example.com",
        "notify_on_alert": True,
    }
    r = client.post(
        f"/api/patients/{pid}/contacts", json=contact_body, headers=auth_headers
    )
    assert r.status_code == 201
    contact_id = r.json()["data"]["id"]
    assert r.json()["data"]["name"] == "Jane Doe"

    r = client.get(f"/api/patients/{pid}/contacts", headers=auth_headers)
    assert any(c["id"] == contact_id for c in r.json()["data"])

    # PUT updates only the supplied fields; others are preserved.
    r = client.put(
        f"/api/patients/{pid}/contacts/{contact_id}",
        json={"phone": "0900000000", "notify_weekly_report": False},
        headers=auth_headers,
    )
    assert r.status_code == 200
    updated = r.json()["data"]
    assert updated["phone"] == "0900000000"
    assert updated["notify_weekly_report"] is False
    assert updated["name"] == "Jane Doe"

    r = client.put(
        f"/api/patients/{pid}/contacts/does-not-exist",
        json={"phone": "x"},
        headers=auth_headers,
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "CONTACT_NOT_FOUND"

    r = client.delete(
        f"/api/patients/{pid}/contacts/{contact_id}", headers=auth_headers
    )
    assert r.status_code == 200

    r = client.delete(f"/api/patients/{pid}", headers=auth_headers)
    assert r.status_code == 200


def test_patient_duplicate_mrn_rejected(
    client: TestClient, auth_headers: dict
) -> None:
    mrn = f"MRN-DUP-{uuid.uuid4().hex[:8]}"
    body = {"full_name": "First", "mrn": mrn}
    r = client.post("/api/patients", json=body, headers=auth_headers)
    assert r.status_code == 201
    pid = r.json()["data"]["id"]

    r = client.post(
        "/api/patients",
        json={"full_name": "Second", "mrn": mrn},
        headers=auth_headers,
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "MRN_TAKEN"

    client.delete(f"/api/patients/{pid}", headers=auth_headers)


def test_get_unknown_patient_returns_404(
    client: TestClient, auth_headers: dict
) -> None:
    r = client.get("/api/patients/nonexistent_id", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "PATIENT_NOT_FOUND"


# ── Devices CRUD ─────────────────────────────────────────────────────────


def test_device_register_and_delete(
    client: TestClient, auth_headers: dict
) -> None:
    body = {
        "device_type": "test_preset",
        "device_name": f"Test {uuid.uuid4().hex[:6]}",
        "channels": ["AF3", "AF4", "T7", "T8"],
        "fs": 256,
    }
    r = client.post("/api/devices", json=body, headers=auth_headers)
    assert r.status_code == 201
    did = r.json()["data"]["id"]
    assert r.json()["data"]["device_type"] == "test_preset"

    r = client.get("/api/devices", headers=auth_headers)
    assert any(d["id"] == did for d in r.json()["data"])

    r = client.delete(f"/api/devices/{did}", headers=auth_headers)
    assert r.status_code == 200

    r = client.get(f"/api/devices/{did}", headers=auth_headers)
    assert r.status_code == 404


def test_device_register_rejects_empty_channels(
    client: TestClient, auth_headers: dict
) -> None:
    body = {
        "device_type": "broken",
        "device_name": "broken",
        "channels": [],
    }
    r = client.post("/api/devices", json=body, headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "NO_CHANNELS"


# ── Alerts list / ack / dismiss ──────────────────────────────────────────


def test_alerts_list_then_ack_and_dismiss(
    client: TestClient, auth_headers: dict
) -> None:
    """Manually insert an Alert via the SQLAlchemy session, exercise ack +
    dismiss, then clean up. Avoids needing a long-running WS stream."""
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import Alert, EEGSession

    sess_id = uuid.uuid4().hex
    alert_ids: list[str] = []
    with SessionLocal() as db:
        db.add(EEGSession(id=sess_id, fs=256.0))
        db.flush()
        alert = Alert(
            session_id=sess_id,
            timestamp_sec=4.5,
            alert_class="ischemic",
            status="alert-enter",
            probabilities_smooth=[0.1, 0.7, 0.2],
            sqi_total=0.91,
            created_at=datetime.now(timezone.utc),
        )
        db.add(alert)
        db.commit()
        alert_ids.append(alert.id)

    aid = alert_ids[0]
    try:
        r = client.get(
            "/api/alerts?since_hours=24&limit=200", headers=auth_headers
        )
        assert r.status_code == 200
        ids = {a["id"] for a in r.json()["data"]}
        assert aid in ids

        r = client.get(
            "/api/alerts?since_hours=24&alert_class=ischemic",
            headers=auth_headers,
        )
        assert all(a["alert_class"] == "ischemic" for a in r.json()["data"])

        r = client.post(f"/api/alerts/{aid}/ack", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["acknowledged"] is True
        assert r.json()["data"]["acknowledged_by"] == "2"

        r = client.post(f"/api/alerts/{aid}/dismiss", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["data"]["dismissed"] is True
    finally:
        with SessionLocal() as db:
            row = db.execute(select(Alert).where(Alert.id == aid)).scalar_one_or_none()
            if row:
                db.delete(row)
            sess = db.execute(
                select(EEGSession).where(EEGSession.id == sess_id)
            ).scalar_one_or_none()
            if sess:
                db.delete(sess)
            db.commit()


def test_assign_patient_to_unassigned_alert_session(
    client: TestClient, auth_headers: dict
) -> None:
    from datetime import datetime, timezone

    from sqlalchemy import select

    from app.database import SessionLocal
    from app.models import Alert, EEGSession, Patient

    sess_id = uuid.uuid4().hex
    patient_id = ""
    alert_ids: list[str] = []
    with SessionLocal() as db:
        patient = Patient(full_name="Assign Test", bed="ED-09")
        db.add(patient)
        db.flush()
        patient_id = patient.id
        db.add(EEGSession(id=sess_id, fs=256.0))
        db.flush()
        for ts in (4.5, 8.0):
            alert = Alert(
                session_id=sess_id,
                timestamp_sec=ts,
                alert_class="ischemic",
                status="alert-enter",
                probabilities_smooth=[0.1, 0.7, 0.2],
                sqi_total=0.91,
                created_at=datetime.now(timezone.utc),
            )
            db.add(alert)
            db.flush()
            alert_ids.append(alert.id)
        db.commit()

    try:
        r = client.post(
            f"/api/alerts/{alert_ids[0]}/assign-patient",
            json={"patient_id": patient_id, "scope": "session"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["updated_alerts"] == 2
        assert data["alert"]["patient_id"] == patient_id
        assert data["patient"]["bed"] == "ED-09"

        with SessionLocal() as db:
            session = db.execute(
                select(EEGSession).where(EEGSession.id == sess_id)
            ).scalar_one()
            alerts = (
                db.execute(select(Alert).where(Alert.session_id == sess_id))
                .scalars()
                .all()
            )
            assert session.patient_id == patient_id
            assert {a.patient_id for a in alerts} == {patient_id}
    finally:
        with SessionLocal() as db:
            for aid in alert_ids:
                row = db.execute(select(Alert).where(Alert.id == aid)).scalar_one_or_none()
                if row:
                    db.delete(row)
            sess = db.execute(
                select(EEGSession).where(EEGSession.id == sess_id)
            ).scalar_one_or_none()
            if sess:
                db.delete(sess)
            patient = db.execute(
                select(Patient).where(Patient.id == patient_id)
            ).scalar_one_or_none()
            if patient:
                db.delete(patient)
            db.commit()


def test_alert_not_found(client: TestClient, auth_headers: dict) -> None:
    r = client.post("/api/alerts/nonexistent/ack", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "ALERT_NOT_FOUND"


# ── Dashboard summary ────────────────────────────────────────────────────


def test_dashboard_summary_shape(client: TestClient, auth_headers: dict) -> None:
    r = client.get("/api/dashboard/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    for key in (
        "active_session_count",
        "alerts_today",
        "alerts_by_class",
        "open_alerts",
        "median_time_to_decision_sec",
        "beds",
    ):
        assert key in data
    assert isinstance(data["beds"], list)
    assert isinstance(data["alerts_by_class"], dict)
    # Field is null when no acked alerts exist, float otherwise
    assert data["median_time_to_decision_sec"] is None or isinstance(data["median_time_to_decision_sec"], float)


# ── Auth gating ──────────────────────────────────────────────────────────


def test_protected_endpoints_reject_missing_token(client: TestClient) -> None:
    for path in (
        "/api/patients",
        "/api/devices",
        "/api/alerts",
        "/api/dashboard/summary",
    ):
        r = client.get(path)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "MISSING_TOKEN"


def test_invalid_token_rejected(client: TestClient) -> None:
    r = client.get(
        "/api/patients", headers={"Authorization": "Bearer not.a.token"}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "INVALID_TOKEN"
