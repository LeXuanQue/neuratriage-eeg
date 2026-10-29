"""Allow-listed replay and upload file resolution for demo workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import REPO_ROOT, UPLOAD_DIR


REPLAY_DIRS = ("dataset_real", "dataset_ischemic", "dataset_healthy", "dataset_npz")
ALLOWED_INFER_EXTS = {".npz", ".npy"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_file_id(value: str) -> str:
    file_id = Path(value or "").name
    if not file_id or file_id != value.strip():
        return ""
    return file_id


def _label_for(path: Path, source: str) -> str:
    stem = path.stem
    if source in ("dataset_real", "dataset_ischemic"):
        return f"{stem} - ischemic replay"
    if source == "dataset_healthy":
        return f"{stem} - healthy replay"
    return f"{stem} - demo replay"


def list_replay_cases(limit_per_dir: int = 12) -> list[dict]:
    cases: list[dict] = []
    for source in REPLAY_DIRS:
        folder = REPO_ROOT / source
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.npz"))[:limit_per_dir]:
            if not _inside(path, folder):
                continue
            cases.append(
                {
                    "id": path.name,
                    "label": _label_for(path, source),
                    "source": source,
                    "class_hint": (
                        "ischemic"
                        if source in ("dataset_real", "dataset_ischemic")
                        else "non-stroke"
                        if source == "dataset_healthy"
                        else "demo"
                    ),
                    "size_bytes": path.stat().st_size,
                }
            )
    return cases


def _extra_replay_dir() -> Optional[Path]:
    """Opt-in EXTRA_REPLAY_DIR (setting), or None when unset / missing."""
    from ..config import get_settings

    raw = (get_settings().extra_replay_dir or "").strip()
    if not raw:
        return None
    folder = Path(raw)
    return folder if folder.is_dir() else None


def resolve_replay_case(case_id: str) -> Optional[Path]:
    file_id = _safe_file_id(case_id)
    if not file_id or Path(file_id).suffix.lower() != ".npz":
        return None
    folders = [REPO_ROOT / source for source in REPLAY_DIRS]
    extra = _extra_replay_dir()
    if extra is not None:
        folders.append(extra)
    for folder in folders:
        path = (folder / file_id).resolve()
        if path.is_file() and _inside(path, folder):
            return path
    return None


def resolve_stream_file(file_id: str) -> Optional[Path]:
    """Resolve a streamable EEG file: a curated dataset case OR a user upload.

    The WS replay path used to look only at the dataset directories, so a file
    the operator uploaded could be analysed offline but never watched as a live
    waveform. Both lookups stay inside their allow-listed root.
    """
    return resolve_replay_case(file_id) or resolve_uploaded_file(file_id)


def resolve_uploaded_file(upload_id: str) -> Optional[Path]:
    file_id = _safe_file_id(upload_id)
    if not file_id or Path(file_id).suffix.lower() not in ALLOWED_INFER_EXTS:
        return None
    path = (UPLOAD_DIR / file_id).resolve()
    if path.is_file() and _inside(path, UPLOAD_DIR):
        return path
    return None
