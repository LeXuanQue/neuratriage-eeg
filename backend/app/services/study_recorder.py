"""Raw-signal recorder for Study 1 sessions, stored under an opaque id for blinded rating.

The primary outcome of Study 1 (time to usable signal) is rated by an EEG reader who must
not know the condition. So each WebSocket session in study mode is saved as
``<root>/raw/<random hex>.npz`` and the id -> (participant, condition, times) mapping goes to
a separate ``<root>/raw_key.jsonl``. Only ``raw/`` (or the rating folder built from it) may be
given to the rater: the participant event logs in ``<root>`` contain the condition.

Time alignment: the npz stores, for every chunk, its first sample index and the server
wall-clock arrival time (``chunk_start_sample``, ``chunk_unix_time``). BLE connection delays
and dropouts therefore do not shift the mapping from samples to the facilitator's markers.

Hardening (security review 2026-11-17): participant codes are ASCII ``P`` + 2-3 digits,
the trial must be a real int, channel count and sampling rate must be plausible, and the
in-memory buffer is capped in bytes. Implausible input disables the recorder once instead
of raising on every chunk. Free-text event payloads are the only place a person could type
identifying text; the recorder itself stores none.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional

import numpy as np

PARTICIPANT = re.compile(r"P[0-9]{2,3}")
DEFAULT_MAX_SEC = 900.0  # 15 min per session
MAX_CHANNELS = 64
MIN_FS, MAX_FS = 32.0, 4096.0
MAX_BYTES = 64 * 1024 * 1024  # per recorder, float32
_key_lock = threading.Lock()


def study_root() -> Path:
    """Configured study log directory (relative paths resolve against the repo root)."""
    from ..config import REPO_ROOT, get_settings

    path = Path(get_settings().study_log_dir)
    return path if path.is_absolute() else REPO_ROOT / path


def _utc(ts: Optional[float] = None) -> str:
    dt = datetime.fromtimestamp(time.time() if ts is None else ts, timezone.utc)
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def valid_study_block(study: Any) -> bool:
    if not isinstance(study, Mapping):
        return False
    participant, condition, trial = study.get("participant"), study.get("condition"), study.get("trial")
    return (
        isinstance(participant, str) and PARTICIPANT.fullmatch(participant) is not None
        and condition in ("B", "G")
        and type(trial) is int and 0 <= trial <= 99
    )


class StudyRecorder:
    def __init__(self, participant: str, condition: str, trial: int, root: Path, max_sec: float = DEFAULT_MAX_SEC):
        self.participant, self.condition, self.trial = participant, condition, trial
        self._root = Path(root)
        self._max_sec = float(max_sec)
        self._chunks: List[np.ndarray] = []
        self._chunk_start: List[int] = []
        self._chunk_time: List[float] = []
        self._channels: Optional[List[str]] = None
        self._fs: Optional[float] = None
        self._n = 0
        self._truncated = False
        self._closed = False
        self.failed = False
        self._started = _utc()

    @classmethod
    def from_init(cls, init_msg: Mapping[str, Any], root: Path, max_sec: float = DEFAULT_MAX_SEC) -> Optional["StudyRecorder"]:
        """A recorder when the init message carries a valid study block, else None."""
        study = init_msg.get("study")
        if not valid_study_block(study):
            return None
        return cls(study["participant"], study["condition"], study["trial"], root, max_sec)

    def _sample_cap(self) -> int:
        by_time = int(self._max_sec * self._fs)
        by_bytes = MAX_BYTES // (4 * len(self._channels))
        return min(by_time, by_bytes)

    def push(self, chunk: np.ndarray, channels: List[str], fs: float) -> None:
        if self._closed or self.failed:
            return
        arr = np.asarray(chunk, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] == 0:
            return
        if self._channels is None:
            if not (0 < len(channels) <= MAX_CHANNELS and arr.shape[0] == len(channels)
                    and MIN_FS <= float(fs) <= MAX_FS):
                self.failed = True
                return
            self._channels, self._fs = [str(c) for c in channels], float(fs)
        elif arr.shape[0] != len(self._channels):
            self.failed = True
            return
        room = self._sample_cap() - self._n
        if room <= 0:
            self._truncated = True
            return
        if arr.shape[1] > room:
            arr, self._truncated = arr[:, :room], True
        self._chunk_start.append(self._n)
        self._chunk_time.append(time.time())
        self._chunks.append(arr)
        self._n += arr.shape[1]

    def close(self) -> Optional[str]:
        """Write the raw file (atomically) and the key line once; returns the opaque id."""
        if self._closed:
            return None
        self._closed = True
        if not self._n:  # nothing valid was recorded (e.g. implausible first chunk)
            return None
        raw_id = secrets.token_hex(8)
        raw_dir = self._root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        final = raw_dir / f"{raw_id}.npz"
        tmp = raw_dir / f"{raw_id}.tmp.npz"
        np.savez_compressed(
            tmp,
            data=np.concatenate(self._chunks, axis=1),
            fs=np.float64(self._fs),
            channels=np.array(self._channels),
            chunk_start_sample=np.array(self._chunk_start, dtype=np.int64),
            chunk_unix_time=np.array(self._chunk_time, dtype=np.float64),
        )
        os.replace(tmp, final)
        record = {
            "raw_id": raw_id, "participant": self.participant, "condition": self.condition,
            "trial_at_start": self.trial, "fs": self._fs, "channels": self._channels,
            "n_samples": self._n, "started_utc": self._started,
            "first_sample_utc": _utc(self._chunk_time[0]), "closed_utc": _utc(),
            "truncated": self._truncated, "stopped_early": self.failed,
        }
        with _key_lock, open(self._root / "raw_key.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self._chunks = []
        return raw_id
