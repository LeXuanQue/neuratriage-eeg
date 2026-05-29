"""Tests for the in-memory rate limiter on auth and infer endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, password: str = "demo1234") -> dict:
    return client.post(
        "/api/auth/login",
        json={"email": "admin@neuratriage.com", "password": password},
    )


def test_login_rate_limit_blocks_after_threshold() -> None:
    """Sixth attempt from same IP within 60s must get 429."""
    with TestClient(app) as client:
        for _ in range(5):
            r = _login(client)
            assert r.status_code == 200

        r = _login(client)
        assert r.status_code == 429
        data = r.json()
        assert data["success"] is False
        assert data["error"]["code"] == "RATE_LIMITED"


def test_login_rate_limit_wrong_password_still_counts() -> None:
    """Failed login attempts count toward the rate limit bucket."""
    with TestClient(app) as client:
        for _ in range(5):
            _login(client, password="wrongpass")

        r = _login(client, password="wrongpass")
        assert r.status_code == 429


def test_infer_rate_limit_requires_auth_first() -> None:
    """POST /api/infer without token returns 401 — auth guard runs before limiter."""
    with TestClient(app) as client:
        r = client.post("/api/infer", json={"case_id": "test"})
        assert r.status_code == 401
