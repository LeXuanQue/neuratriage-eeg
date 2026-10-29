"""POST /api/upload (port from api/index.py:249-271)."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from ..auth import DemoUser
from ..config import UPLOAD_DIR
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok


router = APIRouter(prefix="/api", tags=["files"])

ALLOWED_EXTS = {".npz", ".npy"}
RAW_EEG_EXTS = {".edf", ".bdf", ".fif"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB cap to avoid filling disk
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "file"
    return cleaned[:128]


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    _: DemoUser = Depends(get_current_user),
):
    if not file.filename:
        raise EnvelopeError("Empty filename", "EMPTY_FILENAME")
    ext = Path(file.filename).suffix.lower()
    if ext in RAW_EEG_EXTS:
        raise EnvelopeError(
            (
                f"Raw EEG format '{ext}' is not inference-ready in this demo. "
                "Convert it to .npz or .npy first using the converter scripts."
            ),
            "RAW_EEG_REQUIRES_CONVERSION",
            422,
        )
    if ext not in ALLOWED_EXTS:
        raise EnvelopeError(
            f"Unsupported format '{ext}'. Accepted inference-ready formats: .npz .npy",
            "UNSUPPORTED_FORMAT",
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe = _safe_filename(file.filename)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe}"
    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise EnvelopeError(
                        f"File too large. Maximum allowed is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                        "FILE_TOO_LARGE",
                        413,
                    )
                out.write(chunk)
    except EnvelopeError:
        dest.unlink(missing_ok=True)
        raise
    return ok(
        {
            "upload_id": dest.name,
            "file_path": str(dest),
            "original_name": file.filename,
            "size_bytes": dest.stat().st_size,
        }
    )
