"""Tests for /api/devices/* — detection-first channel selection."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient) -> str:
    r = client.post(
        "/api/auth/login",
        json={"email": "admin@neuratriage.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


def test_probe_with_alias_channels_canonicalises_them() -> None:
    with TestClient(app) as client:
        token = _login(client)
        r = client.post(
            "/api/devices/probe",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "channels": ["AF3", "AF4"],
                "fs": 256,
                "device_id": "BLE-AA:BB:CC:DD:EE:FF",
                "device_name": "Brain-Life Focus+ (mock)",
                "device_type": "brain_life_focus_plus",
            },
        )
        assert r.status_code == 200
        data = r.json()["data"]

    # The device streams AF3/AF4 (recovered from the vendor app). They are not
    # in DEFAULT_CHANNELS and must not be aliased onto FP1/FP2, so the probe
    # reports zero coverage instead of pretending the 18-ch model applies.
    assert data["device_channels"] == ["AF3", "AF4"]
    assert data["matched"] == []
    assert set(data["unrecognised"]) == {"AF3", "AF4"}
    assert data["coverage_ratio"] == pytest.approx(0.0)
    assert data["preset_hint"]["channels"] == ["AF3", "AF4"]


def test_probe_full_18ch_has_full_coverage() -> None:
    from eeg_stroke_pipeline import DEFAULT_CHANNELS

    with TestClient(app) as client:
        token = _login(client)
        r = client.post(
            "/api/devices/probe",
            headers={"Authorization": f"Bearer {token}"},
            json={"channels": list(DEFAULT_CHANNELS), "fs": 256},
        )
        data = r.json()["data"]

    assert data["coverage_ratio"] == 1.0
    assert data["unrecognised"] == []
    assert data["missing_target_channels"] == []


def test_probe_empty_channels_is_rejected() -> None:
    with TestClient(app) as client:
        token = _login(client)
        r = client.post(
            "/api/devices/probe",
            headers={"Authorization": f"Bearer {token}"},
            json={"channels": [], "fs": 256},
        )

    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NO_CHANNELS"


def test_presets_endpoint_returns_known_templates() -> None:
    with TestClient(app) as client:
        token = _login(client)
        r = client.get(
            "/api/devices/presets",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = r.json()["data"]

    assert "brain_life_focus_plus" in data
    assert "full_18ch" in data
    assert data["brain_life_focus_plus"]["channels"] == ["AF3", "AF4"]
