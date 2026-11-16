"""POST /api/study/events: append-only event log for Study 1 (docs/user_study_protocol.md).

One JSON line per event in ``<study_log_dir>/<participant>.jsonl``. Participants are
identified only by a pseudonymous code (``P07``); the pattern rejects names, so no
personal data can reach the log. The server adds its own UTC timestamp so client clock
drift does not distort time-to-usable-signal.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import DemoUser
from ..config import REPO_ROOT, get_settings
from ..deps import get_current_user
from ..envelope import ok

router = APIRouter(prefix="/api/study", tags=["study"])

EventType = Literal[
    "trial_start", "trial_end", "operator_action", "fault_resolved", "quality", "guidance_shown", "note",
]
MAX_PAYLOAD_CHARS = 2000
_write_lock = threading.Lock()


class StudyEvent(BaseModel):
    participant: str = Field(pattern=r"^P\d{2,3}$")
    condition: Literal["B", "G"]
    trial: int = Field(ge=0, le=99)
    type: EventType
    client_ts: str = Field(max_length=40)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _small_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(json.dumps(value)) > MAX_PAYLOAD_CHARS:
            raise ValueError(f"payload larger than {MAX_PAYLOAD_CHARS} characters")
        return value


def _log_dir() -> Path:
    path = Path(get_settings().study_log_dir)
    return path if path.is_absolute() else REPO_ROOT / path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@router.post("/events")
def log_event(event: StudyEvent, _user: DemoUser = Depends(get_current_user)):
    record = {"server_ts": _utc_now(), **event.model_dump()}
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _write_lock, open(directory / f"{event.participant}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(line)
    return ok({"logged": True, "server_ts": record["server_ts"]})
