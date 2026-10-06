"""Low-channel simulated montage CV from an existing feature table.

This is a quick feasibility check for a portable EEG montage before hardware is
available. It does not rebuild preprocessing from raw signals; it selects only
features attributable to the requested channels from the existing 18-channel
feature table. Treat results as a screening sanity check, not final validation.

Example:
  .venv\\Scripts\\python.exe scripts\\run_low_channel_ablation.py ^
      --channels T3,T4,O1,O2 --fast
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from eeg_stroke_pipeline import HOMOLOGOUS_PAIRS, MFDFA_SUMMARY_FEATURES, REGION_MAP


LABEL_MAP = {
    0: 0,
    1: 1,
    "0": 0,
    "1": 1,
    "non-stroke": 0,
    "nonstroke": 0,
    "normal": 0,
    "healthy": 0,
    "ischemic": 1,
    "is": 1,
}


def parse_channels(raw: str) -> list[str]:
    channels = [c.strip().upper() for c in raw.split(",") if c.strip()]
    if not channels:
        raise ValueError("--channels cannot be empty")
    return channels


def low_channel_features(
    frame: pd.DataFrame, channels: list[str], include_sqi: bool = True
) -> list[str]:
    chosen: list[str] = []
    channel_set = set(channels)

    for ch in channels:
        chosen.extend([f"apen_{ch}", f"fuen_{ch}"])

    for left, right in HOMOLOGOUS_PAIRS:
        if left in channel_set and right in channel_set:
            chosen.extend(
                [
                    f"apen_asym_{left}_{right}",
                    f"fuen_asym_{left}_{right}",
                    f"apfu_absdiff_{left}_{right}",
                ]
            )

    for region, region_channels in REGION_MAP.items():
        if any(ch in channel_set for ch in region_channels):
            chosen.extend(f"{region}_{feat}" for feat in MFDFA_SUMMARY_FEATURES)

    if include_sqi:
        # SQI is retained as a quality family. In this quick mode it comes from
        # the existing table, so interpret it as approximate for the low-channel
        # montage.
        chosen.extend(
            [
                "sqi_total",
                "sqi_flatline",
                "sqi_clip",
                "sqi_line_ratio",
                "sqi_hf_ratio",
            ]
        )

    return [c for c in dict.fromkeys(chosen) if c in frame.columns]


def binary_ece(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (probs >= lo) & (probs < hi) if hi < 1 else (probs >= lo) & (probs <= hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y_true[mask].mean() - probs[mask].mean())
    return float(ece)


def run_cv(ft: pd.DataFrame, features: list[str], folds: int, fast: bool) -> dict:
    X_raw = ft[features].astype(float).to_numpy()
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].astype(str).to_numpy()
    splitter = GroupKFold(n_splits=folds)
    fold_rows = []
    t0 = time.time()

    for fold, (tr, te) in enumerate(splitter.split(X_raw, y, groups), start=1):
        imputer = SimpleImputer(strategy="median")
        X_train = imputer.fit_transform(X_raw[tr])
        X_test = imputer.transform(X_raw[te])
        params = {
            "objective": "binary",
            "boosting_type": "gbdt",
            "is_unbalance": True,
            "random_state": 42,
            "n_jobs": -1,
            "verbosity": -1,
        }
        if fast:
            params.update({"n_estimators": 120, "num_leaves": 31})
        clf = lgb.LGBMClassifier(**params)
        clf.fit(X_train, y[tr])
        probs = clf.predict_proba(X_test)[:, 1]
        pred = (probs >= 0.5).astype(int)

        pt = (
            pd.DataFrame({"pid": groups[te], "y": y[te], "p": probs})
            .groupby("pid")
            .agg(y=("y", "first"), p=("p", "mean"))
        )
        pt_pred = (pt["p"].to_numpy() >= 0.5).astype(int)
        row = {
            "fold": fold,
            "macro_f1": float(f1_score(y[te], pred, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(y[te], pred)),
            "auc": float(roc_auc_score(y[te], probs)),
            "ece": binary_ece(y[te], probs),
            "pt_macro_f1": float(
                f1_score(pt["y"].to_numpy(), pt_pred, average="macro", zero_division=0)
            ),
            "pt_auc": float(roc_auc_score(pt["y"].to_numpy(), pt["p"].to_numpy())),
            "n_test_windows": int(len(te)),
            "n_test_patients": int(len(pt)),
        }
        fold_rows.append(row)
        print(
            f"fold {fold}/{folds}: F1={row['macro_f1']:.4f} "
            f"AUC={row['auc']:.4f} ptF1={row['pt_macro_f1']:.4f}"
        )

    df = pd.DataFrame(fold_rows)
    return {
        "macro_f1": float(df["macro_f1"].mean()),
        "std_macro_f1": float(df["macro_f1"].std()),
        "balanced_accuracy": float(df["balanced_accuracy"].mean()),
        "auc": float(df["auc"].mean()),
        "ece": float(df["ece"].mean()),
        "pt_macro_f1": float(df["pt_macro_f1"].mean()),
        "std_pt_macro_f1": float(df["pt_macro_f1"].std()),
        "pt_auc": float(df["pt_auc"].mean()),
        "fold_results": fold_rows,
        "elapsed_min": float((time.time() - t0) / 60.0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--combined-csv",
        default=str(ROOT / "dataset_ischemic" / "feature_table_combined.csv"),
    )
    parser.add_argument("--channels", default="T3,T4,O1,O2")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--no-sqi", action="store_true")
    parser.add_argument(
        "--out-prefix",
        default=str(ROOT / "results" / "low_channel_T3_T4_O1_O2"),
    )
    args = parser.parse_args()

    channels = parse_channels(args.channels)
    ft = pd.read_csv(args.combined_csv)
    ft["patient_id"] = ft["patient_id"].astype(str)
    ft["label"] = ft["label"].map(lambda x: LABEL_MAP.get(x, LABEL_MAP.get(str(x).lower())))
    ft = ft.dropna(subset=["label"]).copy()
    ft["label"] = ft["label"].astype(int)
    ft = ft[ft["label"].isin([0, 1])].copy()

    features = low_channel_features(ft, channels, include_sqi=not args.no_sqi)
    if not features:
        raise RuntimeError(f"No feature columns found for channels={channels}")

    print(f"Input     : {args.combined_csv}")
    print(f"Channels  : {', '.join(channels)}")
    print(f"Features  : {len(features)}")
    print(f"SQI       : {'excluded' if args.no_sqi else 'included'}")
    print(f"Windows   : {len(ft):,}")
    print(f"Patients  : {ft['patient_id'].nunique()}")
    print(f"Labels    : {dict(ft['label'].value_counts().sort_index())}")
    print("Mode      : quick existing-feature subset")
    print()

    result = run_cv(ft, features, args.folds, args.fast)
    result.update(
        {
            "channels": channels,
            "features": features,
            "feature_count": len(features),
            "include_sqi": not args.no_sqi,
            "input_csv": str(Path(args.combined_csv).resolve()),
            "mode": "quick_existing_feature_subset",
            "limitations": (
                "Uses features precomputed from the 18-channel table. Rebuild from "
                "raw NPZ using only the selected channels before making final claims."
            ),
        }
    )

    out_prefix = Path(args.out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_prefix.with_suffix(".json")
    txt_path = out_prefix.with_suffix(".txt")
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    txt_path.write_text(
        "\n".join(
            [
                "Low-channel quick CV: ischemic vs non-stroke",
                f"Channels: {', '.join(channels)}",
                f"Features: {len(features)}",
                f"SQI: {'excluded' if args.no_sqi else 'included'}",
                "Mode: quick existing-feature subset",
                "",
                f"Macro-F1: {result['macro_f1']:.4f} +/- {result['std_macro_f1']:.4f}",
                f"Patient Macro-F1: {result['pt_macro_f1']:.4f} +/- {result['std_pt_macro_f1']:.4f}",
                f"AUC: {result['auc']:.4f}",
                f"Patient AUC: {result['pt_auc']:.4f}",
                f"ECE: {result['ece']:.4f}",
                "",
                "Limitation: quick subset from precomputed 18-channel features; rebuild raw low-channel table for final evidence.",
            ]
        ),
        encoding="utf-8",
    )
    print()
    print(f"Macro-F1        : {result['macro_f1']:.4f} +/- {result['std_macro_f1']:.4f}")
    print(f"Patient Macro-F1: {result['pt_macro_f1']:.4f} +/- {result['std_pt_macro_f1']:.4f}")
    print(f"AUC             : {result['auc']:.4f}")
    print(f"Patient AUC     : {result['pt_auc']:.4f}")
    print(f"ECE             : {result['ece']:.4f}")
    print(f"Saved JSON      : {json_path}")
    print(f"Saved summary   : {txt_path}")


if __name__ == "__main__":
    main()
