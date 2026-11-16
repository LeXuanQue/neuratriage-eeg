"""StudyRecorder: raw signal of a study session under an opaque id, for blinded rating."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.services.study_recorder import StudyRecorder

INIT = {"type": "init", "study": {"participant": "P07", "trial": 1, "condition": "G"}}


@pytest.mark.unit
def test_close_writes_an_opaque_raw_file_and_a_key_line(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    assert rec is not None
    rng = np.random.default_rng(0)
    for _ in range(4):
        rec.push(rng.standard_normal((2, 128)), ["AF3", "AF4"], 256.0)
    raw_id = rec.close()

    raw = tmp_path / "raw" / f"{raw_id}.npz"
    assert raw.exists()
    assert "P07" not in raw.name and "G" not in raw.stem.upper().replace(raw_id.upper(), "")
    z = np.load(raw)
    assert z["data"].shape == (2, 512) and float(z["fs"]) == 256.0
    assert [str(c) for c in z["channels"]] == ["AF3", "AF4"]

    key = [json.loads(line) for line in (tmp_path / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()]
    assert key[-1]["raw_id"] == raw_id
    assert key[-1]["participant"] == "P07" and key[-1]["condition"] == "G"
    assert key[-1]["n_samples"] == 512 and key[-1]["started_utc"].endswith("Z")


@pytest.mark.unit
@pytest.mark.parametrize(
    "study",
    [None, {"participant": "Nguyen", "trial": 1, "condition": "G"},
     {"participant": "P07", "trial": 1, "condition": "X"}, {"participant": "P07", "trial": "x", "condition": "B"}],
)
def test_no_recorder_without_a_valid_study_block(tmp_path: Path, study) -> None:
    msg = {"type": "init"} if study is None else {"type": "init", "study": study}
    assert StudyRecorder.from_init(msg, tmp_path) is None


@pytest.mark.unit
def test_empty_session_writes_nothing(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    assert rec.close() is None
    assert not (tmp_path / "raw_key.jsonl").exists()


@pytest.mark.unit
def test_recording_is_capped_and_flagged(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path, max_sec=1.0)
    for _ in range(4):
        rec.push(np.zeros((2, 128)) + 1.0, ["AF3", "AF4"], 256.0)
    raw_id = rec.close()
    assert np.load(tmp_path / "raw" / f"{raw_id}.npz")["data"].shape == (2, 256)
    key = json.loads((tmp_path / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert key["truncated"] is True


@pytest.mark.unit
def test_channel_count_change_disables_the_recorder(tmp_path: Path) -> None:
    # Disabling once (instead of raising on every chunk) avoids a log storm (review 2026-11-17).
    rec = StudyRecorder.from_init(INIT, tmp_path)
    rec.push(np.ones((2, 128)), ["AF3", "AF4"], 256.0)
    rec.push(np.zeros((3, 128)), ["a", "b", "c"], 256.0)
    assert rec.failed is True
    raw_id = rec.close()  # the valid part recorded before the change is kept
    assert np.load(tmp_path / "raw" / f"{raw_id}.npz")["data"].shape == (2, 128)
    key = json.loads((tmp_path / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert key["stopped_early"] is True


@pytest.mark.unit
def test_close_is_idempotent(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    rec.push(np.ones((2, 128)), ["AF3", "AF4"], 256.0)
    first = rec.close()
    assert rec.close() is None and first is not None
    assert len((tmp_path / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()) == 1


# ------------------------------------------------------------------ security review 2026-11-17
@pytest.mark.unit
@pytest.mark.parametrize("participant", ["P٠٧", "P０７", "P07\n"])
def test_participant_code_must_be_ascii_digits_and_exact(tmp_path: Path, participant: str) -> None:
    msg = {"type": "init", "study": {"participant": participant, "trial": 1, "condition": "G"}}
    assert StudyRecorder.from_init(msg, tmp_path) is None


@pytest.mark.unit
def test_bool_trial_is_rejected(tmp_path: Path) -> None:
    msg = {"type": "init", "study": {"participant": "P07", "trial": True, "condition": "G"}}
    assert StudyRecorder.from_init(msg, tmp_path) is None


@pytest.mark.unit
@pytest.mark.parametrize("n_ch, fs", [(65, 256.0), (2, 1e9), (2, 0.0)])
def test_implausible_channel_count_or_rate_disables_the_recorder(tmp_path: Path, n_ch: int, fs: float) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    rec.push(np.zeros((n_ch, 8)), [f"c{i}" for i in range(n_ch)], fs)
    rec.push(np.zeros((n_ch, 8)), [f"c{i}" for i in range(n_ch)], fs)  # no exception storm
    assert rec.failed is True
    assert rec.close() is None


@pytest.mark.unit
def test_memory_is_capped_in_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.study_recorder as SR

    monkeypatch.setattr(SR, "MAX_BYTES", 2 * 4 * 300)  # 300 float32 samples of 2 channels
    rec = StudyRecorder.from_init(INIT, tmp_path)
    for _ in range(5):
        rec.push(np.ones((2, 128)), ["AF3", "AF4"], 256.0)
    raw_id = rec.close()
    assert np.load(tmp_path / "raw" / f"{raw_id}.npz")["data"].shape == (2, 300)


@pytest.mark.unit
def test_chunk_arrival_times_are_saved_for_time_alignment(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    for _ in range(3):
        rec.push(np.ones((2, 128)), ["AF3", "AF4"], 256.0)
    raw_id = rec.close()
    z = np.load(tmp_path / "raw" / f"{raw_id}.npz")
    assert z["chunk_start_sample"].tolist() == [0, 128, 256]
    t = z["chunk_unix_time"]
    assert t.shape == (3,) and np.all(np.diff(t) >= 0)
    key = json.loads((tmp_path / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert key["first_sample_utc"].endswith("Z")


@pytest.mark.unit
def test_raw_file_is_written_atomically(tmp_path: Path) -> None:
    rec = StudyRecorder.from_init(INIT, tmp_path)
    rec.push(np.ones((2, 128)), ["AF3", "AF4"], 256.0)
    rec.close()
    assert not list((tmp_path / "raw").glob("*.tmp*"))
