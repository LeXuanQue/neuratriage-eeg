"""Allow-listed replay and upload file resolution for demo workflows."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import REPO_ROOT, UPLOAD_DIR


REPLAY_DIRS = ("dataset_real", "dataset_ischemic", "dataset_healthy", "dataset_hemorrhagic", "dataset_npz")
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
    if source == "dataset_hemorrhagic":
        return f"{stem} - hemorrhagic exploratory replay"
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
                        else "hemorrhagic"
                        if source == "dataset_hemorrhagic"
                        else "demo"
                    ),
                    "size_bytes": path.stat().st_size,
                }
            )
    return cases


def resolve_replay_case(case_id: str) -> Optional[Path]:
    file_id = _safe_file_id(case_id)
    if not file_id or Path(file_id).suffix.lower() != ".npz":
        return None
    for source in REPLAY_DIRS:
        folder = REPO_ROOT / source
        path = (folder / file_id).resolve()
        if path.is_file() and _inside(path, folder):
            return path
    return None


def resolve_uploaded_file(upload_id: str) -> Optional[Path]:
    file_id = _safe_file_id(upload_id)
    if not file_id or Path(file_id).suffix.lower() not in ALLOWED_INFER_EXTS:
        return None
    path = (UPLOAD_DIR / file_id).resolve()
    if path.is_file() and _inside(path, UPLOAD_DIR):
        return path
    return None
