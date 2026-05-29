"""Integration test for /ws/stream/{session_id}.

Pushes synthetic Brain-Life Focus+ EEG (4 channels @ 256 Hz, 8 seconds) through
the WebSocket and asserts at least one `event` message comes back.
"""
from __future__ import annotations

import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.model_manager import get_manager


def _token(client: TestClient) -> str:
    r = client.post(
        "/api/auth/login",
        json={"email": "doctor@neuratriage.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


@pytest.fixture(scope="module", autouse=True)
def _ensure_model_loaded():
    mgr = get_manager()
    if not mgr.is_loaded:
        loaded = mgr.auto_load(get_settings().candidate_model_paths())
        if not loaded:
            pytest.skip("No model available — train one or place under models_store/")


def test_ws_stream_emits_events_for_brain_life_focus_plus() -> None:
    rng = np.random.default_rng(0)
    fs = 256
    # mfdfa_window_sec defaults to 4s and entropy_step_sec to 0.5s, so the
    # first window emits at t≈4s. Push 6s of data to guarantee multiple events.
    seconds = 6
    chunk_samples = fs
    session_id = uuid.uuid4().hex
    device_channels = ["AF3", "AF4", "T7", "T8"]

    events: list[dict] = []
    errors: list[dict] = []

    with TestClient(app) as client:
        token = _token(client)
        with client.websocket_connect(f"/ws/stream/{session_id}?token={token}") as ws:
            ws.send_json(
                {
                    "type": "init",
                    "device_channels": device_channels,
                    "fs": fs,
                }
            )
            ready = ws.receive_json()
            assert ready["type"] == "ready"
            assert ready["session_id"] == session_id
            assert ready["mapped_channels"][:3] == ["C3", "C4", "CZ"]

            # Push every chunk first; only then drain. Each detector.update may
            # produce 0..N events, so we collect whatever arrives.
            for _ in range(seconds):
                chunk = rng.normal(size=(len(device_channels), chunk_samples)).tolist()
                ws.send_json({"type": "data", "chunk": chunk})

            ws.send_json({"type": "close"})

            # The server processes each data message synchronously and queues
            # any events for delivery before reading the next message. After
            # sending `close` the handler exits and the connection closes —
            # receive_json then raises WebSocketDisconnect.
            while True:
                try:
                    msg = ws.receive_json()
                except Exception:
                    break
                if msg.get("type") == "event":
                    events.append(msg)
                elif msg.get("type") == "error":
                    errors.append(msg)

    assert errors == [], f"Server reported errors: {errors}"
    assert events, "Expected at least one inference event"
    first = events[0]
    assert "status" in first
    assert "sqi_total" in first
    assert "timestamp_sec" in first


def test_ws_stream_rejects_data_before_init() -> None:
    session_id = uuid.uuid4().hex
    with TestClient(app) as client:
        token = _token(client)
        with client.websocket_connect(f"/ws/stream/{session_id}?token={token}") as ws:
            ws.send_json({"type": "data", "chunk": [[0.0]]})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "init" in msg["message"].lower()
            ws.send_json({"type": "close"})


@pytest.mark.timeout(300)
def test_ws_stream_replay_emits_events() -> None:
    """Server-driven replay with a real .npz file emits at least one event."""
    import numpy as np
    from app.services.replay_cases import list_replay_cases

    cases = list_replay_cases()
    if not cases:
        pytest.skip("No replay .npz cases available")
    # Pick the smallest available case to keep test runtime short.
    case = min(cases, key=lambda c: c.get("size_bytes", 0))
    case_id = case["id"]

    session_id = uuid.uuid4().hex
    events: list[dict] = []

    with TestClient(app) as client:
        token = _token(client)
        with client.websocket_connect(f"/ws/stream/{session_id}?token={token}") as ws:
            ws.send_json(
                {
                    "type": "init",
                    "device_channels": ["AF3", "AF4", "T7", "T8"],
                    "fs": 256,
                    "replay_npz": case_id,
                    "realtime": False,
                }
            )
            ready = ws.receive_json()
            if ready.get("type") == "error":
                pytest.skip(f"Replay init error: {ready['message']}")
            assert ready["type"] == "ready"
            assert ready.get("replay_npz") is not None

            while True:
                try:
                    msg = ws.receive_json()
                except Exception:
                    break
                if msg.get("type") == "event":
                    events.append(msg)
                elif msg.get("type") == "replay_done":
                    break

    assert events, f"Expected at least one event from replay of {case_id}"
    first = events[0]
    assert "status" in first
    assert "probabilities_smooth" in first
    assert len(first["probabilities_smooth"]) == 3


def test_ws_stream_reports_channel_count_mismatch() -> None:
    session_id = uuid.uuid4().hex
    with TestClient(app) as client:
        token = _token(client)
        with client.websocket_connect(f"/ws/stream/{session_id}?token={token}") as ws:
            ws.send_json(
                {
                    "type": "init",
                    "device_channels": ["AF3", "AF4", "T7", "T8"],
                    "fs": 256,
                }
            )
            ready = ws.receive_json()
            assert ready["type"] == "ready"

            ws.send_json({"type": "data", "chunk": [[0.1] * 256] * 3})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "channel count" in msg["message"].lower()
            ws.send_json({"type": "close"})
