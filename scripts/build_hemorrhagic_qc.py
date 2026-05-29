"""Build QC summary for the exploratory UCLH hemorrhagic cohort.

Outputs:
  dataset_hemorrhagic/qc_summary.csv
  dataset_hemorrhagic/qc_summary.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT / "dataset_hemorrhagic" / "manifest_hemorrhagic.csv"
DEFAULT_FEATURE_TABLE = ROOT / "dataset_hemorrhagic" / "feature_table_hemorrhagic.csv"
DEFAULT_OUT_CSV = ROOT / "dataset_hemorrhagic" / "qc_summary.csv"
DEFAULT_OUT_JSON = ROOT / "dataset_hemorrhagic" / "qc_summary.json"

INJECTION_RE = re.compile(r"^\s*(?P<t>[0-9]+(?:\.[0-9]+)?)s\s+Starting Injection", re.I)


def _parse_injection_start(source_path: Path) -> float | None:
    log_path = source_path.with_name(source_path.stem + "_log.txt")
    if not log_path.is_file():
        return None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = INJECTION_RE.search(line)
        if match:
            return float(match.group("t"))
    return None


def _load_npz_stats(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        data = np.asarray(z["data"], dtype=float)
        source = Path(str(z["source"])) if "source" in z else None
        duration = float(z["duration_sec"]) if "duration_sec" in z else data.shape[1] / float(z["fs"])
    return {
        "source": str(source) if source else "",
        "duration_sec": duration,
        "finite_fraction": float(np.isfinite(data).mean()),
        "nan_count": int(np.isnan(data).sum()),
        "p99_5_abs_uv": float(np.nanpercentile(np.abs(data), 99.5) * 1e6),
        "injection_start_sec": _parse_injection_start(source) if source else None,
    }


def build_qc(manifest_path: Path, feature_table_path: Path) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    features = pd.read_csv(feature_table_path)

    rows = []
    for _, row in manifest.iterrows():
        patient_id = str(row["patient_id"])
        npz_path = Path(str(row["path"]))
        stats = _load_npz_stats(npz_path)
        patient_features = features[features["patient_id"].astype(str) == patient_id]
        sqi = patient_features["sqi_total"] if "sqi_total" in patient_features else pd.Series(dtype=float)
        rows.append(
            {
                "patient_id": patient_id,
                "label": row["label"],
                "npz_path": str(npz_path),
                "source_bdf": stats["source"],
                "injection_start_sec": stats["injection_start_sec"],
                "crop_duration_sec": stats["duration_sec"],
                "retained_windows": int(len(patient_features)),
                "sqi_mean": float(sqi.mean()) if len(sqi) else None,
                "sqi_min": float(sqi.min()) if len(sqi) else None,
                "sqi_max": float(sqi.max()) if len(sqi) else None,
                "finite_fraction": stats["finite_fraction"],
                "nan_count": stats["nan_count"],
                "p99_5_abs_uv": stats["p99_5_abs_uv"],
                "high_amplitude_warning": bool(stats["p99_5_abs_uv"] > 5000),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--feature-table", default=str(DEFAULT_FEATURE_TABLE))
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    args = parser.parse_args()

    qc = build_qc(Path(args.manifest), Path(args.feature_table))
    out_csv = Path(args.out_csv)
    out_json = Path(args.out_json)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    qc.to_csv(out_csv, index=False)
    out_json.write_text(json.dumps(qc.to_dict(orient="records"), indent=2), encoding="utf-8")

    print(qc.to_string(index=False))
    print(f"\nSaved -> {out_csv}")
    print(f"Saved -> {out_json}")


if __name__ == "__main__":
    main()
