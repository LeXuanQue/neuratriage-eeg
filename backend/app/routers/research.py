"""Research evidence endpoints used by the UIST demo screens."""
from __future__ import annotations

import json
import csv
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
MFDFA_3CLASS_EXPLORATORY = (
    RESULTS_DIR / "mfdfa_ablation_3class_4hs_results.json"
)
CV_SUMMARY = RESULTS_DIR / "cv_summary.txt"
HEMORRHAGIC_FEATURE_TABLE = (
    REPO_ROOT / "dataset_hemorrhagic" / "feature_table_hemorrhagic.csv"
)
HEMORRHAGIC_QC = REPO_ROOT / "dataset_hemorrhagic" / "qc_summary.json"


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


def _summarize_feature_table(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"available": False, "path": str(path)}

    windows = 0
    patients: set[str] = set()
    labels: dict[str, int] = {}
    sqi_values: list[float] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            windows += 1
            patient_id = row.get("patient_id")
            if patient_id:
                patients.add(patient_id)
            label = str(row.get("label", "")).strip()
            labels[label] = labels.get(label, 0) + 1
            try:
                sqi_values.append(float(row.get("sqi_total", "")))
            except ValueError:
                pass

    return {
        "available": True,
        "path": str(path),
        "n_windows": windows,
        "n_patients": len(patients),
        "label_counts": labels,
        "sqi_mean": _round(sum(sqi_values) / len(sqi_values)) if sqi_values else None,
        "validated_for_3class_cv": len(patients) >= 5,
    }


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


def _summarize_exploratory_results(path: Path) -> dict[str, Any]:
    raw = _read_json(path)
    if not raw:
        return {"available": False, "path": str(path)}
    metadata = raw.get("metadata", {})
    return {
        "available": True,
        "path": str(path),
        "task": metadata.get("task"),
        "folds": metadata.get("folds"),
        "fast": bool(metadata.get("fast")),
        "dataset": metadata.get("dataset", {}),
        "conditions": _condition_rows(raw),
        "paired_comparisons": _comparison_rows(raw),
        "claim_status": "exploratory_positive_trend",
    }


def _summarize_qc(path: Path) -> dict[str, Any]:
    rows = _read_json(path)
    if not isinstance(rows, list):
        return {"available": False, "path": str(path), "rows": []}
    warning_count = sum(1 for row in rows if row.get("high_amplitude_warning"))
    retained = [int(row.get("retained_windows") or 0) for row in rows]
    sqi = [
        float(row["sqi_mean"])
        for row in rows
        if isinstance(row.get("sqi_mean"), (int, float))
    ]
    return {
        "available": True,
        "path": str(path),
        "n_patients": len(rows),
        "total_retained_windows": sum(retained),
        "high_amplitude_warning_count": warning_count,
        "sqi_mean": _round(sum(sqi) / len(sqi)) if sqi else None,
        "rows": rows,
    }


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
                "exploratory_datasets": {
                    "hemorrhagic": _summarize_feature_table(HEMORRHAGIC_FEATURE_TABLE)
                },
                "qc": {"hemorrhagic": _summarize_qc(HEMORRHAGIC_QC)},
                "exploratory_results": {
                    "three_class": _summarize_exploratory_results(MFDFA_3CLASS_EXPLORATORY)
                },
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
            "exploratory_datasets": {
                "hemorrhagic": _summarize_feature_table(HEMORRHAGIC_FEATURE_TABLE)
            },
            "qc": {"hemorrhagic": _summarize_qc(HEMORRHAGIC_QC)},
            "exploratory_results": {
                "three_class": _summarize_exploratory_results(MFDFA_3CLASS_EXPLORATORY)
            },
            "limitations": [
                "Current validated result is binary ischemic-vs-non-stroke.",
                "Four UCLH ICH hemorrhagic patients have been integrated as exploratory evidence, but HS is not yet validated for the planned 5-fold 3-class CV.",
                "Metrics are research evidence and not a clinical performance claim.",
            ],
        }
    )


@router.get("/replay/cases")
def replay_cases(_=Depends(get_current_user)):
    return ok(list_replay_cases())
