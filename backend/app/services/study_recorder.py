"""Raw-signal recorder for Study 1 sessions, stored under an opaque id for blinded rating.

The primary outcome of Study 1 (time to usable signal) is rated by an EEG reader who must
not know the condition. So each WebSocket session in study mode is saved as
``<root>/raw/<random hex>.npz`` and the id -> (participant, condition, start time) mapping
goes to a separate ``<root>/raw_key.jsonl`` that the rater never sees. The server start time
lets the analysis align the facilitator's event markers with sample indices.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Mapping, Optional

import numpy as np

PARTICIPANT = re.compile(r"^P\d{2,3}$")
DEFAULT_MAX_SEC = 900.0  # 15 min per session bounds memory
_key_lock = threading.Lock()


def study_root() -> Path:
    """Configured study log directory (relative paths resolve against the repo root)."""
    from ..config import REPO_ROOT, get_settings

    path = Path(get_settings().study_log_dir)
    return path if path.is_absolute() else REPO_ROOT / path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class StudyRecorder:
    def __init__(self, participant: str, condition: str, trial: int, root: Path, max_sec: float = DEFAULT_MAX_SEC):
        self.participant, self.condition, self.trial = participant, condition, trial
        self._root = Path(root)
        self._max_sec = float(max_sec)
        self._chunks: List[np.ndarray] = []
        self._channels: Optional[List[str]] = None
        self._fs: Optional[float] = None
        self._n = 0
        self._truncated = False
        self._closed = False
        self._started = _utc_now()

    @classmethod
    def from_init(cls, init_msg: Mapping[str, Any], root: Path, max_sec: float = DEFAULT_MAX_SEC) -> Optional["StudyRecorder"]:
        """A recorder when the init message carries a valid study block, else None."""
        study = init_msg.get("study")
        if not isinstance(study, Mapping):
            return None
        participant, condition, trial = study.get("participant"), study.get("condition"), study.get("trial")
        if not isinstance(participant, str) or not PARTICIPANT.match(participant):
            return None
        if condition not in ("B", "G") or not isinstance(trial, int) or not 0 <= trial <= 99:
            return None
        return cls(participant, condition, trial, root, max_sec)

    def push(self, chunk: np.ndarray, channels: List[str], fs: float) -> None:
        arr = np.asarray(chunk, dtype=np.float32)
        if arr.ndim != 2 or arr.shape[1] == 0 or self._closed:
            return
        if self._channels is None:
            self._channels, self._fs = [str(c) for c in channels], float(fs)
        elif arr.shape[0] != len(self._channels):
            raise ValueError(f"recorder expected {len(self._channels)} channels, got {arr.shape[0]}")
        room = int(self._max_sec * self._fs) - self._n
        if room <= 0:
            self._truncated = True
            return
        if arr.shape[1] > room:
            arr, self._truncated = arr[:, :room], True
        self._chunks.append(arr)
        self._n += arr.shape[1]

    def close(self) -> Optional[str]:
        """Write the raw file and key line once; returns the opaque id (None if empty)."""
        if self._closed:
            return None
        self._closed = True
        if not self._n:
            return None
        raw_id = secrets.token_hex(8)
        raw_dir = self._root / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            raw_dir / f"{raw_id}.npz",
            data=np.concatenate(self._chunks, axis=1),
            fs=np.float64(self._fs),
            channels=np.array(self._channels),
        )
        record = {
            "raw_id": raw_id, "participant": self.participant, "condition": self.condition,
            "trial_at_start": self.trial, "fs": self._fs, "channels": self._channels,
            "n_samples": self._n, "started_utc": self._started, "closed_utc": _utc_now(),
            "truncated": self._truncated,
        }
        with _key_lock, open(self._root / "raw_key.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        self._chunks = []
        return raw_id
