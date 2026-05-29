#!/usr/bin/env python3
"""Train the final ApFu+MFDFA+SQI model and save to backend/models/model.joblib.

Usage:
    python train_model.py [--trials N] [--binary]

Options:
    --trials N   Number of Optuna TPE trials (default: 40)
    --binary     Use binary NS/IS table instead of 3-class exploratory
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import eeg_stroke_pipeline as pipeline

BINARY_TABLE = ROOT / "dataset_real" / "feature_table_combined.csv"
THREE_CLASS_TABLE = ROOT / "dataset_real" / "feature_table_combined_3class_exploratory.csv"
OUT_PATH = ROOT / "backend" / "models" / "model.joblib"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--binary", action="store_true")
    args = parser.parse_args()

    table_path = BINARY_TABLE if args.binary else THREE_CLASS_TABLE
    if not table_path.is_file():
        print(f"[ERROR] Feature table not found: {table_path}")
        print("  Try --binary to use the binary NS/IS table instead.")
        sys.exit(1)

    print(f"[train] Loading feature table: {table_path.name}")
    df = pd.read_csv(table_path)
    n_win = len(df)
    n_pat = df["patient_id"].nunique()
    label_counts = df["label"].value_counts().to_dict()
    print(f"[train] {n_win} windows | {n_pat} patients | labels: {label_counts}")

    cfg = pipeline.PipelineConfig(n_trials=args.trials)
    print(f"[train] n_trials={cfg.n_trials} | features=ApFu+MFDFA+SQI ({len(pipeline.ALL_FEATURES)} total)")
    print("[train] Starting Optuna TPE search + final fit ...")

    trained, meta = pipeline.train_final_model(df, cfg)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    trained.save(str(OUT_PATH))

    print(f"\n[train] Done. Model saved -> {OUT_PATH}")
    print(f"[train] Optuna best value : {meta.get('optuna_best_value')}")
    print(f"[train] Best params       : {json.dumps(meta.get('best_params', {}), indent=2)}")
    print(f"[train] Feature count     : {meta.get('feature_count')}")
    print(f"[train] Windows trained   : {meta.get('n_windows')}")
    print(f"[train] Patients          : {meta.get('n_patients')}")


if __name__ == "__main__":
    main()
