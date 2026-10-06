"""Streaming an UPLOADED file, not just the curated dataset cases.

`/api/upload` accepts .npz/.npy and offline `/api/infer` can read them, but the
WebSocket replay path only resolved dataset directories — so a file the user
uploaded could be analysed yet never watched as a live waveform.

Run: .venv/Scripts/python.exe -m pytest backend/tests/test_upload_stream.py -q
"""
import numpy as np
import pytest

from app.services import replay_cases
from app.ws.stream import _load_replay_data


def _write_npz(path, data, channels=None, fs=None):
    payload = {"data": data}
    if channels is not None:
        payload["channels"] = np.array(channels)
    if fs is not None:
        payload["fs"] = np.float32(fs)
    np.savez(path, **payload)
    return path


@pytest.mark.unit
def test_loads_npz_exactly_as_recorded(tmp_path):
    # Arrange
    data = np.random.randn(2, 512).astype(np.float32)
    path = _write_npz(tmp_path / "mine.npz", data, ["AF3", "AF4"], 256.0)

    # Act
    got, channels, fs = _load_replay_data(path)

    # Assert
    assert got.shape == (2, 512)
    assert channels == ["AF3", "AF4"]
    assert fs == 256.0


@pytest.mark.unit
def test_loads_plain_npy_with_sensible_defaults(tmp_path):
    """A bare .npy has no channels/fs — it must still stream, not crash."""
    path = tmp_path / "raw.npy"
    np.save(path, np.random.randn(4, 300).astype(np.float32))

    data, channels, fs = _load_replay_data(path)

    assert data.shape == (4, 300)
    assert len(channels) == 4
    assert fs == 256.0


@pytest.mark.unit
def test_single_channel_recording_is_promoted_to_one_row(tmp_path):
    path = tmp_path / "one.npy"
    np.save(path, np.random.randn(600).astype(np.float32))

    data, channels, fs = _load_replay_data(path)

    assert data.shape == (1, 600)
    assert len(channels) == 1


@pytest.mark.unit
def test_channel_labels_are_regenerated_when_they_do_not_match_the_rows(tmp_path):
    data = np.random.randn(3, 256).astype(np.float32)
    path = _write_npz(tmp_path / "mismatch.npz", data, ["AF3", "AF4"], 256.0)

    _, channels, _ = _load_replay_data(path)

    assert len(channels) == 3


@pytest.mark.unit
def test_rejects_arrays_that_are_not_a_channels_by_samples_matrix(tmp_path):
    path = tmp_path / "cube.npy"
    np.save(path, np.zeros((2, 3, 4), dtype=np.float32))

    with pytest.raises(ValueError):
        _load_replay_data(path)


@pytest.mark.unit
def test_resolve_stream_file_finds_dataset_cases_and_uploads(tmp_path, monkeypatch):
    # Arrange: an uploaded file that is not in any dataset directory
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    _write_npz(upload_dir / "abc123_mine.npz", np.zeros((2, 10), dtype=np.float32))
    monkeypatch.setattr(replay_cases, "UPLOAD_DIR", upload_dir)

    # Act / Assert
    assert replay_cases.resolve_stream_file("abc123_mine.npz") is not None
    assert replay_cases.resolve_stream_file("sub-01.npz") is not None  # dataset case
    assert replay_cases.resolve_stream_file("../../etc/passwd") is None
    assert replay_cases.resolve_stream_file("nope.npz") is None


@pytest.mark.unit
def test_resolve_stream_file_accepts_npy_uploads(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    np.save(upload_dir / "def456_raw.npy", np.zeros((2, 10), dtype=np.float32))
    monkeypatch.setattr(replay_cases, "UPLOAD_DIR", upload_dir)

    assert replay_cases.resolve_stream_file("def456_raw.npy") is not None
