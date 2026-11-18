"""POST /api/study/events: append-only event log for Study 1 (docs/user_study_protocol.md).

One JSON line per event in ``<study_log_dir>/<participant>.jsonl``. Participants are
identified by a pseudonymous code (``P07``, ASCII digits only); the code pattern rejects
names. Event payloads are bounded but may contain free text (``note``), so facilitators must
not type identifying information there. The server adds its own UTC timestamp and the id of
the logged-in account that posted the event.

Hardening (security review 2026-11-17): a generous per-client rate limit, a free-disk check
before writing, and strict ASCII codes.
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import DemoUser
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..services.rate_limit import study_limiter
from ..services.study_recorder import study_root

router = APIRouter(prefix="/api/study", tags=["study"])

EventType = Literal[
    "trial_start", "trial_end", "operator_action", "fault_resolved", "quality", "guidance_shown", "note",
]
MAX_PAYLOAD_CHARS = 2000
MIN_FREE_BYTES = 500 * 1024 * 1024
_write_lock = threading.Lock()


class StudyEvent(BaseModel):
    participant: str = Field(pattern=r"^P[0-9]{2,3}$")
    condition: Literal["B", "G"]
    trial: int = Field(ge=0, le=99, strict=True)
    type: EventType
    client_ts: str = Field(max_length=40)
    payload: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _small_payload(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(json.dumps(value)) > MAX_PAYLOAD_CHARS:
            raise ValueError(f"payload larger than {MAX_PAYLOAD_CHARS} characters")
        return value


def _free_bytes(directory: Path) -> int:
    probe = directory
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return shutil.disk_usage(probe).free


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@router.post("/events")
def log_event(
    event: StudyEvent,
    user: DemoUser = Depends(get_current_user),
    _rl: None = Depends(study_limiter),
):
    directory = study_root()
    if _free_bytes(directory) < MIN_FREE_BYTES:
        raise EnvelopeError("Not enough free disk space to keep logging study data", "DISK_FULL", 507)
    directory.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        record = {"server_ts": _utc_now(), "logged_by": user.id, **event.model_dump()}
        with open(directory / f"{event.participant}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return ok({"logged": True, "server_ts": record["server_ts"]})
