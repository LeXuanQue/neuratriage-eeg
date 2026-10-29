"""
5-fold patient-wise group CV + ablation: ApFu-only vs ApFu+MFDFA
Binary classification: ischemic (label=1) vs non-stroke (label=0).

Reads:
  dataset_real/feature_table_combined.csv

Writes:
  results/cv_results.json
  results/cv_summary.txt

Usage:
  .venv/Scripts/python.exe run_cv_ablation.py
  .venv/Scripts/python.exe run_cv_ablation.py --n-trials 20 --folds 5
  .venv/Scripts/python.exe run_cv_ablation.py --fast   (skip Optuna, sanity check)
"""
import argparse
import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

import lightgbm as lgb
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

from eeg_stroke_pipeline import ENTROPY_FEATURES, MFDFA_FEATURES, SQI_FEATURES

RESULTS_DIR = ROOT / "results"


def binary_ece(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error (10-bin)."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y_true[mask].mean() - probs[mask].mean())
    return float(ece)


def _tpe_objective(trial, X_tr, y_tr, X_va, y_va) -> float:
    params = {
        "objective": "binary",
        "metric": "binary_logloss",
        "boosting_type": "gbdt",
        "learning_rate": trial.suggest_float("lr", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_est", 200, 1500),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 5.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 5.0, log=True),
        "is_unbalance": True,
        "random_state": 42,
        "n_jobs": -1,
        "verbosity": -1,
    }
    clf = lgb.LGBMClassifier(**params)
    clf.fit(
        X_tr, y_tr,
        eval_set=[(X_va, y_va)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(40, verbose=False)],
    )
    pred = clf.predict(X_va)
    return float(f1_score(y_va, pred, average="macro", zero_division=0))


def optimize_binary(X_tr, y_tr, X_va, y_va, n_trials: int) -> dict:
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42, multivariate=True),
    )
    study.optimize(
        lambda t: _tpe_objective(t, X_tr, y_tr, X_va, y_va),
        n_trials=n_trials,
        show_progress_bar=False,
    )
    return study.best_params


def run_one_fold(X_train, y_train, g_train, X_test, y_test, g_test,
                 n_trials: int, fast: bool) -> dict:
    # Hold out 15 % of train patients for Optuna inner validation
    val_pats = np.unique(g_train)
    rng = np.random.default_rng(42)
    val_pats = rng.choice(val_pats, size=max(1, int(len(val_pats) * 0.15)), replace=False)
    va_mask = np.isin(g_train, val_pats)

    best_raw = {} if (fast or n_trials <= 0) else optimize_binary(
        X_train[~va_mask], y_train[~va_mask],
        X_train[va_mask],  y_train[va_mask],
        n_trials,
    )

    params = {
        "objective": "binary",
        "boosting_type": "gbdt",
        "is_unbalance": True,
        "random_state": 42,
        "n_jobs": -1,
        "verbosity": -1,
        **best_raw,
    }
    clf = lgb.LGBMClassifier(**params)
    clf.fit(X_train, y_train)

    probs = clf.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)

    macro_f1 = float(f1_score(y_test, preds, average="macro", zero_division=0))
    bal_acc  = float(balanced_accuracy_score(y_test, preds))
    auc      = float(roc_auc_score(y_test, probs)) if len(np.unique(y_test)) > 1 else float("nan")
    ece      = binary_ece(y_test, probs)

    # Patient-level: mean prob per patient, majority true label
    df_pt = (
        pd.DataFrame({"pid": g_test, "y": y_test, "p": probs})
        .groupby("pid")
        .agg(y=("y", "first"), p=("p", "mean"))
    )
    pt_preds = (df_pt["p"].to_numpy() >= 0.5).astype(int)
    pt_f1  = float(f1_score(df_pt["y"], pt_preds, average="macro", zero_division=0))
    pt_auc = (float(roc_auc_score(df_pt["y"], df_pt["p"]))
               if df_pt["y"].nunique() > 1 else float("nan"))

    return {
        "macro_f1": macro_f1, "bal_acc": bal_acc, "auc": auc, "ece": ece,
        "pt_macro_f1": pt_f1, "pt_auc": pt_auc,
        "n_test_windows": int(len(y_test)),
        "n_test_patients": int(len(df_pt)),
    }


def run_cv(ft: pd.DataFrame, feature_cols: list, label: str,
           n_folds: int, n_trials: int, fast: bool) -> dict:
    X = ft[feature_cols].astype(float).to_numpy()
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()

    kf = GroupKFold(n_splits=n_folds)
    fold_results = []
    t0 = time.time()

    for fold_id, (tr_idx, te_idx) in enumerate(kf.split(X, y, groups), start=1):
        print(f"    fold {fold_id}/{n_folds}", end="", flush=True)
        res = run_one_fold(
            X[tr_idx], y[tr_idx], groups[tr_idx],
            X[te_idx], y[te_idx], groups[te_idx],
            n_trials=n_trials, fast=fast,
        )
        res["fold"] = fold_id
        fold_results.append(res)
        print(f"  F1={res['macro_f1']:.3f}  AUC={res['auc']:.3f}"
              f"  ptF1={res['pt_macro_f1']:.3f}  ECE={res['ece']:.4f}")

    mdf = pd.DataFrame(fold_results)
    summary = mdf.mean(numeric_only=True).to_dict()
    summary["std_macro_f1"]    = float(mdf["macro_f1"].std())
    summary["std_pt_macro_f1"] = float(mdf["pt_macro_f1"].std())
    summary["label"]           = label
    summary["n_features"]      = len(feature_cols)
    summary["fold_results"]    = fold_results
    summary["elapsed_min"]     = (time.time() - t0) / 60
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined-csv",
                        default=str(ROOT / "dataset_real" / "feature_table_combined.csv"))
    parser.add_argument("--folds",    type=int, default=5)
    parser.add_argument("--n-trials", type=int, default=30,
                        help="Optuna TPE trials per fold (0 = LightGBM defaults)")
    parser.add_argument("--fast", action="store_true",
                        help="Skip Optuna (fast sanity check)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.combined_csv)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found. Run combine_manifests.py first.")
        sys.exit(1)

    print(f"Loading {csv_path} ...")
    ft = pd.read_csv(csv_path)
    label_map = {0: 0, 1: 1, "non-stroke": 0, "nonstroke": 0,
                 "normal": 0, "ischemic": 1, "is": 1}
    ft["label"] = ft["label"].map(label_map).astype(int)
    ft = ft[ft["label"].isin([0, 1])].copy()

    print(f"Windows : {len(ft):,}   Patients : {ft['patient_id'].nunique()}")
    print(f"Labels  : {dict(ft['label'].value_counts().sort_index())}\n")

    APFU_FEATS = list(ENTROPY_FEATURES) + list(SQI_FEATURES)
    FULL_FEATS = list(ENTROPY_FEATURES) + list(MFDFA_FEATURES) + list(SQI_FEATURES)

    all_results = {}
    for name, feats in [("ApFu-only", APFU_FEATS), ("ApFu+MFDFA", FULL_FEATS)]:
        print(f"=== {name}  ({len(feats)} features) ===")
        all_results[name] = run_cv(ft, feats, name,
                                   n_folds=args.folds,
                                   n_trials=args.n_trials,
                                   fast=args.fast)
        print()

    # Summary table
    print("=" * 68)
    print(f"{'Condition':20s}  {'MacroF1':>7}  {'±':>5}  "
          f"{'ptF1':>7}  {'AUC':>7}  {'ECE':>7}")
    print("-" * 68)
    for name, res in all_results.items():
        print(f"{name:20s}  {res['macro_f1']:7.3f}  {res['std_macro_f1']:5.3f}  "
              f"{res['pt_macro_f1']:7.3f}  {res['auc']:7.3f}  {res['ece']:7.4f}")
    print("=" * 68)
    print("(ptF1 = patient-level macro F1 via mean-probability aggregation)\n")

    json_path = RESULTS_DIR / "cv_results.json"
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    txt_path = RESULTS_DIR / "cv_summary.txt"
    with open(txt_path, "w") as f:
        f.write("Binary CV: ischemic vs non-stroke\n")
        f.write(f"Folds={args.folds}  Optuna-trials={args.n_trials}\n\n")
        f.write(f"{'Condition':20s}  {'MacroF1':>7}  {'±':>5}  "
                f"{'ptF1':>7}  {'AUC':>7}  {'ECE':>7}\n")
        for name, res in all_results.items():
            f.write(f"{name:20s}  {res['macro_f1']:7.3f}  {res['std_macro_f1']:5.3f}  "
                    f"{res['pt_macro_f1']:7.3f}  {res['auc']:7.3f}  {res['ece']:7.4f}\n")

    print(f"Results  -> {json_path}")
    print(f"Summary  -> {txt_path}")


if __name__ == "__main__":
    main()
