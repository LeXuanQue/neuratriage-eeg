"""Unit tests for the response envelope helpers.

Frontend (frontend/lib/api.js + frontend/shared/live-data.js) requires the
exact `{success, data}` / `{success, error:{code, message}}` shape.
"""
from __future__ import annotations

import json

from app.envelope import EnvelopeError, err, ok


def _decode(response) -> dict:
    return json.loads(bytes(response.body).decode("utf-8"))


def test_ok_wraps_payload_with_success_true() -> None:
    response = ok({"hello": "world"})
    body = _decode(response)
    assert body == {"success": True, "data": {"hello": "world"}}
    assert response.status_code == 200


def test_ok_handles_none_data() -> None:
    response = ok()
    body = _decode(response)
    assert body == {"success": True, "data": None}


def test_err_wraps_message_and_code() -> None:
    response = err("Bad input", "BAD_INPUT", 422)
    body = _decode(response)
    assert body == {
        "success": False,
        "error": {"message": "Bad input", "code": "BAD_INPUT"},
    }
    assert response.status_code == 422


def test_envelope_error_carries_code_and_status() -> None:
    exc = EnvelopeError("Token expired", "TOKEN_EXPIRED", 401)
    assert exc.message == "Token expired"
    assert exc.code == "TOKEN_EXPIRED"
    assert exc.status_code == 401
    assert isinstance(exc, Exception)
