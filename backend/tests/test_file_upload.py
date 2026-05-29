from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import UPLOAD_DIR
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


def _cleanup_upload(upload_id: str) -> None:
    if not upload_id:
        return
    path = (UPLOAD_DIR / Path(upload_id).name).resolve()
    try:
        path.relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        return
    if path.is_file():
        path.unlink()


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("demo_signal.npz", "application/octet-stream"),
        ("demo_signal.npy", "application/octet-stream"),
    ],
)
def test_upload_accepts_inference_ready_files(
    client: TestClient,
    auth_headers: dict,
    filename: str,
    content_type: str,
) -> None:
    r = client.post(
        "/api/upload",
        files={"file": (filename, b"demo-bytes", content_type)},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()["data"]
    try:
        assert data["original_name"] == filename
        assert data["upload_id"].endswith(filename)
        assert data["size_bytes"] == len(b"demo-bytes")
    finally:
        _cleanup_upload(data.get("upload_id", ""))


@pytest.mark.parametrize("filename", ["raw.edf", "raw.bdf", "raw.fif"])
def test_upload_rejects_raw_eeg_formats_with_converter_message(
    client: TestClient,
    auth_headers: dict,
    filename: str,
) -> None:
    r = client.post(
        "/api/upload",
        files={"file": (filename, b"raw-eeg", "application/octet-stream")},
        headers=auth_headers,
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "RAW_EEG_REQUIRES_CONVERSION"
    assert "Convert it to .npz or .npy" in err["message"]


def test_upload_rejects_unknown_format(
    client: TestClient,
    auth_headers: dict,
) -> None:
    r = client.post(
        "/api/upload",
        files={"file": ("notes.txt", b"not eeg", "text/plain")},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "UNSUPPORTED_FORMAT"
