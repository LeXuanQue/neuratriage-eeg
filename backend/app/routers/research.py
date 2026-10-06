"""Research evidence endpoints used by the binary NS/IS demo screens."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from ..config import REPO_ROOT
from ..deps import get_current_user
from ..envelope import ok
from ..services.replay_cases import list_replay_cases


router = APIRouter(prefix="/api", tags=["research"])

RESULTS_DIR = REPO_ROOT / "results"
MFDFA_RESULTS = RESULTS_DIR / "mfdfa_ablation_results.json"
CV_SUMMARY = RESULTS_DIR / "cv_summary.txt"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_text_lossy(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _round(value: Any, digits: int = 4) -> Any:
    return round(float(value), digits) if isinstance(value, (int, float)) else value


def _condition_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, row in raw.get("results", {}).items():
        rows.append(
            {
                "key": key,
                "label": row.get("label", key),
                "n_features": row.get("n_features"),
                "macro_f1": _round(row.get("macro_f1")),
                "std_macro_f1": _round(row.get("std_macro_f1")),
                "patient_macro_f1": _round(row.get("pt_macro_f1")),
                "auc": _round(row.get("auc")),
                "ece": _round(row.get("ece")),
            }
        )
    return rows


def _comparison_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in raw.get("paired_comparisons", []):
        rows.append(
            {
                "label": row.get("label")
                or f"{row.get('left', '')} - {row.get('right', '')}",
                "left": row.get("left"),
                "right": row.get("right"),
                "mean_delta": _round(row.get("mean_delta"), 6),
                "p_value": _round(row.get("paired_ttest_p"), 5),
                "verdict": row.get("verdict"),
            }
        )
    return rows


@router.get("/research/metrics")
def research_metrics(_=Depends(get_current_user)):
    raw = _read_json(MFDFA_RESULTS)
    if not raw:
        return ok(
            {
                "available": False,
                "message": "No MFDFA ablation results found.",
                "conditions": [],
                "paired_comparisons": [],
                "limitations": [],
            }
        )

    metadata = raw.get("metadata", {})
    conditions = _condition_rows(raw)
    comparisons = _comparison_rows(raw)

    summary_text = _read_text_lossy(CV_SUMMARY)
    return ok(
        {
            "available": True,
            "task": metadata.get("task", "binary"),
            "dataset": metadata.get("dataset", {}),
            "conditions": conditions,
            "paired_comparisons": comparisons,
            "cv_summary": summary_text,
            "limitations": [
                "Current validated result is binary ischemic-vs-non-stroke.",
                "The primary IS/NS cohorts differ by acquisition source, so headline performance must be read with cross-cohort confound risk.",
                "Metrics are research evidence and not a clinical performance claim.",
            ],
        }
    )


@router.get("/replay/cases")
def replay_cases(_=Depends(get_current_user)):
    return ok(list_replay_cases())
