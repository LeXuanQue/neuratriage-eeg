"""
Patient-wise feature-family ablation for testing whether MFDFA adds value.

This script is stricter than run_cv_ablation.py:
- separates ApFu, MFDFA, and SQI feature families;
- supports binary or multiclass feature tables;
- uses patient-wise folds only;
- applies Optuna parameters correctly to the final LightGBM model;
- reports fold-wise paired deltas for the MFDFA comparisons.

Recommended report run:
  .venv\\Scripts\\python.exe run_mfdfa_ablation.py --n-trials 30 --folds 5

Fast sanity check:
  .venv\\Scripts\\python.exe run_mfdfa_ablation.py --fast --folds 3
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
import warnings
from collections import Counter
from pathlib import Path
from typing import Iterable

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from scipy import stats
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold

try:
    from sklearn.model_selection import StratifiedGroupKFold
except Exception:  # pragma: no cover
    StratifiedGroupKFold = None

from eeg_stroke_pipeline import ENTROPY_FEATURES, MFDFA_FEATURES, SQI_FEATURES


RESULTS_DIR = ROOT / "results"
CLASS_NAMES = {
    0: "non-stroke",
    1: "ischemic",
    2: "hemorrhagic",
    3: "tia",
}
LABEL_MAP = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "non-stroke": 0,
    "nonstroke": 0,
    "normal": 0,
    "healthy": 0,
    "control": 0,
    "ns": 0,
    "ischemic": 1,
    "is": 1,
    "infarction": 1,
    "cerebral infarction": 1,
    "hemorrhagic": 2,
    "hemorrhage": 2,
    "hs": 2,
    "ich": 2,
    "intracerebral hemorrhage": 2,
    "tia": 3,
    "transient ischemic attack": 3,
}


CONDITIONS = {
    "apfu": {
        "label": "ApFu",
        "features": list(ENTROPY_FEATURES),
    },
    "mfdfa": {
        "label": "MFDFA",
        "features": list(MFDFA_FEATURES),
    },
    "sqi": {
        "label": "SQI",
        "features": list(SQI_FEATURES),
    },
    "apfu_mfdfa": {
        "label": "ApFu+MFDFA",
        "features": list(ENTROPY_FEATURES) + list(MFDFA_FEATURES),
    },
    "apfu_sqi": {
        "label": "ApFu+SQI",
        "features": list(ENTROPY_FEATURES) + list(SQI_FEATURES),
    },
    "apfu_mfdfa_sqi": {
        "label": "ApFu+MFDFA+SQI",
        "features": list(ENTROPY_FEATURES)
        + list(MFDFA_FEATURES)
        + list(SQI_FEATURES),
    },
}

DEFAULT_CONDITIONS = [
    "apfu",
    "mfdfa",
    "apfu_mfdfa",
    "apfu_sqi",
    "apfu_mfdfa_sqi",
]

PAIRED_COMPARISONS = [
    ("apfu_mfdfa", "apfu", "MFDFA gain without SQI"),
    ("apfu_mfdfa_sqi", "apfu_sqi", "MFDFA gain with SQI"),
    ("apfu_sqi", "apfu", "SQI gain over ApFu"),
    ("apfu_mfdfa_sqi", "apfu_mfdfa", "SQI gain over ApFu+MFDFA"),
]


def parse_label(value) -> int | None:
    if pd.isna(value):
        return None
    key = str(value).strip().lower()
    return LABEL_MAP.get(value, LABEL_MAP.get(key))


def parse_classes(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    parsed = set()
    for part in raw.split(","):
        label = parse_label(part.strip())
        if label is None:
            raise ValueError(f"Unknown class label in --classes: {part!r}")
        parsed.add(label)
    return parsed


def load_feature_table(path: Path, classes: set[int] | None) -> pd.DataFrame:
    ft = pd.read_csv(path)
    if "patient_id" not in ft.columns or "label" not in ft.columns:
        raise ValueError("Feature table must contain patient_id and label columns.")
    ft["patient_id"] = ft["patient_id"].astype(str)
    ft["label"] = ft["label"].map(parse_label)
    ft = ft.dropna(subset=["label"]).copy()
    ft["label"] = ft["label"].astype(int)
    if classes is not None:
        ft = ft[ft["label"].isin(classes)].copy()
    if ft.empty:
        raise ValueError("No rows remain after label parsing/filtering.")
    validate_patient_labels(ft)
    labels = sorted(ft["label"].unique())
    remap = {old: new for new, old in enumerate(labels)}
    ft["label_original"] = ft["label"]
    ft["label"] = ft["label"].map(remap).astype(int)
    ft.attrs["label_remap"] = remap
    ft.attrs["label_originals"] = labels
    return ft


def validate_patient_labels(ft: pd.DataFrame) -> None:
    counts = ft.groupby("patient_id")["label"].nunique()
    bad = counts[counts > 1]
    if not bad.empty:
        sample = ", ".join(map(str, bad.index[:5]))
        raise ValueError(
            "Some patient_id values have multiple labels. "
            f"Fix patient grouping before CV. Examples: {sample}"
        )


def selected_condition_keys(raw: str) -> list[str]:
    if raw.strip().lower() in {"all", "default"}:
        return DEFAULT_CONDITIONS
    keys = [x.strip().lower() for x in raw.split(",") if x.strip()]
    unknown = [k for k in keys if k not in CONDITIONS]
    if unknown:
        raise ValueError(f"Unknown condition(s): {unknown}")
    return keys


def validate_features(ft: pd.DataFrame, condition_keys: Iterable[str]) -> None:
    missing: dict[str, list[str]] = {}
    for key in condition_keys:
        cols = CONDITIONS[key]["features"]
        miss = [c for c in cols if c not in ft.columns]
        if miss:
            missing[key] = miss[:8]
    if missing:
        details = "; ".join(
            f"{key}: {len(cols)} missing, e.g. {cols}" for key, cols in missing.items()
        )
        raise ValueError(f"Feature table is missing required columns: {details}")


def choose_splitter(y: np.ndarray, groups: np.ndarray, n_folds: int, seed: int):
    if StratifiedGroupKFold is not None:
        return StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    return GroupKFold(n_splits=n_folds)


def split_iter(splitter, X: np.ndarray, y: np.ndarray, groups: np.ndarray):
    if isinstance(splitter, GroupKFold):
        return splitter.split(X, y, groups)
    return splitter.split(X, y, groups)


def ece_score(y_true: np.ndarray, probs: np.ndarray, n_bins: int = 10) -> float:
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y_true).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        if hi == 1.0:
            mask = (conf >= lo) & (conf <= hi)
        else:
            mask = (conf >= lo) & (conf < hi)
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def auc_score(y_true: np.ndarray, probs: np.ndarray, n_classes: int) -> float:
    try:
        if n_classes == 2:
            return float(roc_auc_score(y_true, probs[:, 1]))
        return float(
            roc_auc_score(
                y_true,
                probs,
                labels=list(range(n_classes)),
                multi_class="ovr",
                average="macro",
            )
        )
    except ValueError:
        return float("nan")


def metrics_from_probs(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_classes: int,
    prefix: str = "",
) -> dict:
    preds = probs.argmax(axis=1)
    return {
        f"{prefix}accuracy": float(accuracy_score(y_true, preds)),
        f"{prefix}macro_f1": float(
            f1_score(
                y_true,
                preds,
                average="macro",
                labels=list(range(n_classes)),
                zero_division=0,
            )
        ),
        f"{prefix}bal_acc": float(balanced_accuracy_score(y_true, preds)),
        f"{prefix}auc": auc_score(y_true, probs, n_classes),
        f"{prefix}ece": ece_score(y_true, probs),
    }


def patient_level_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    groups: np.ndarray,
    n_classes: int,
) -> dict:
    rows = {"pid": groups, "y": y_true}
    for i in range(n_classes):
        rows[f"p{i}"] = probs[:, i]
    df = pd.DataFrame(rows)
    agg = {f"p{i}": "mean" for i in range(n_classes)}
    agg["y"] = "first"
    pt = df.groupby("pid", sort=False).agg(agg)
    pt_probs = pt[[f"p{i}" for i in range(n_classes)]].to_numpy()
    pt_y = pt["y"].to_numpy(dtype=int)
    out = metrics_from_probs(pt_y, pt_probs, n_classes, prefix="pt_")
    out["n_test_patients"] = int(len(pt))
    return out


def base_lgbm_params(n_classes: int, seed: int) -> dict:
    params = {
        "boosting_type": "gbdt",
        "class_weight": "balanced",
        "random_state": seed,
        "n_jobs": -1,
        "verbosity": -1,
    }
    if n_classes == 2:
        params["objective"] = "binary"
        params["metric"] = "binary_logloss"
    else:
        params["objective"] = "multiclass"
        params["metric"] = "multi_logloss"
        params["num_class"] = n_classes
    return params


def suggest_lgbm_params(trial: optuna.Trial) -> dict:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "n_estimators": trial.suggest_int("n_estimators", 200, 1200),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127),
        "max_depth": trial.suggest_int("max_depth", 3, 10),
        "min_child_samples": trial.suggest_int("min_child_samples", 10, 80),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 5.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 5.0, log=True),
    }


def make_inner_split(
    X_train: np.ndarray,
    y_train: np.ndarray,
    g_train: np.ndarray,
    n_classes: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    unique_groups = np.unique(g_train)
    if len(unique_groups) < 4:
        splitter = GroupKFold(n_splits=2)
    else:
        n_splits = min(5, len(unique_groups))
        splitter = choose_splitter(y_train, g_train, n_splits, seed)
    tr_inner, va_inner = next(split_iter(splitter, X_train, y_train, g_train))
    if len(np.unique(y_train[va_inner])) < min(n_classes, 2):
        rng = np.random.default_rng(seed)
        pats = np.array(unique_groups)
        rng.shuffle(pats)
        val_count = max(1, int(math.ceil(len(pats) * 0.2)))
        val_pats = set(pats[:val_count])
        va_mask = np.array([g in val_pats for g in g_train])
        tr_inner = np.where(~va_mask)[0]
        va_inner = np.where(va_mask)[0]
    return tr_inner, va_inner


def optimize_params(
    X_train: np.ndarray,
    y_train: np.ndarray,
    g_train: np.ndarray,
    n_classes: int,
    n_trials: int,
    seed: int,
) -> dict:
    tr_inner, va_inner = make_inner_split(X_train, y_train, g_train, n_classes, seed)
    X_tr, X_va = X_train[tr_inner], X_train[va_inner]
    y_tr, y_va = y_train[tr_inner], y_train[va_inner]

    def objective(trial: optuna.Trial) -> float:
        params = {
            **base_lgbm_params(n_classes, seed),
            **suggest_lgbm_params(trial),
        }
        clf = lgb.LGBMClassifier(**params)
        clf.fit(
            X_tr,
            y_tr,
            eval_set=[(X_va, y_va)],
            callbacks=[lgb.early_stopping(40, verbose=False)],
        )
        probs = clf.predict_proba(X_va)
        if isinstance(probs, list):
            probs = np.vstack([p[:, 1] for p in probs]).T
        preds = np.asarray(probs).argmax(axis=1)
        return float(
            f1_score(
                y_va,
                preds,
                average="macro",
                labels=list(range(n_classes)),
                zero_division=0,
            )
        )

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed, multivariate=True),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return dict(study.best_params)


def run_one_fold(
    ft: pd.DataFrame,
    feature_cols: list[str],
    tr_idx: np.ndarray,
    te_idx: np.ndarray,
    n_classes: int,
    n_trials: int,
    fast: bool,
    seed: int,
) -> dict:
    X_raw = ft[feature_cols].replace([np.inf, -np.inf], np.nan).astype(float).to_numpy()
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()

    imputer = SimpleImputer(strategy="median")
    X_train = imputer.fit_transform(X_raw[tr_idx])
    X_test = imputer.transform(X_raw[te_idx])
    y_train, y_test = y[tr_idx], y[te_idx]
    g_train, g_test = groups[tr_idx], groups[te_idx]

    tuned = {}
    if not fast and n_trials > 0:
        tuned = optimize_params(X_train, y_train, g_train, n_classes, n_trials, seed)

    clf = lgb.LGBMClassifier(
        **base_lgbm_params(n_classes, seed),
        **tuned,
    )
    clf.fit(X_train, y_train)

    probs = clf.predict_proba(X_test)
    if isinstance(probs, list):
        probs = np.vstack([p[:, 1] for p in probs]).T
    probs = np.asarray(probs, dtype=float)
    if n_classes == 2 and probs.shape[1] == 1:
        probs = np.column_stack([1.0 - probs[:, 0], probs[:, 0]])

    out = metrics_from_probs(y_test, probs, n_classes)
    out.update(patient_level_metrics(y_test, probs, g_test, n_classes))
    out["n_test_windows"] = int(len(y_test))
    out["best_params"] = tuned
    return out


def run_condition(
    ft: pd.DataFrame,
    key: str,
    folds: list[tuple[np.ndarray, np.ndarray]],
    n_classes: int,
    n_trials: int,
    fast: bool,
    seed: int,
) -> dict:
    info = CONDITIONS[key]
    fold_results = []
    t0 = time.time()
    print(f"=== {info['label']} ({len(info['features'])} features) ===")
    for fold_id, (tr_idx, te_idx) in enumerate(folds, start=1):
        res = run_one_fold(
            ft,
            info["features"],
            tr_idx,
            te_idx,
            n_classes,
            n_trials,
            fast,
            seed + fold_id,
        )
        res["fold"] = fold_id
        fold_results.append(res)
        print(
            f"  fold {fold_id}/{len(folds)} "
            f"F1={res['macro_f1']:.4f} "
            f"AUC={res['auc']:.4f} "
            f"ptF1={res['pt_macro_f1']:.4f} "
            f"ECE={res['ece']:.4f}"
        )
    mdf = pd.DataFrame(fold_results)
    summary = mdf.drop(columns=["best_params"], errors="ignore").mean(
        numeric_only=True
    ).to_dict()
    summary.update(
        {
            "key": key,
            "label": info["label"],
            "n_features": len(info["features"]),
            "std_macro_f1": float(mdf["macro_f1"].std()),
            "std_auc": float(mdf["auc"].std()),
            "std_pt_macro_f1": float(mdf["pt_macro_f1"].std()),
            "elapsed_min": (time.time() - t0) / 60,
            "fold_results": fold_results,
        }
    )
    print()
    return summary


def paired_delta(
    results: dict[str, dict],
    left: str,
    right: str,
    label: str,
    metric: str = "macro_f1",
) -> dict | None:
    if left not in results or right not in results:
        return None
    ldf = pd.DataFrame(results[left]["fold_results"]).sort_values("fold")
    rdf = pd.DataFrame(results[right]["fold_results"]).sort_values("fold")
    if len(ldf) != len(rdf):
        return None
    delta = ldf[metric].to_numpy(dtype=float) - rdf[metric].to_numpy(dtype=float)
    p_value = float("nan")
    if len(delta) > 1 and np.isfinite(delta).all():
        try:
            p_value = float(stats.ttest_rel(ldf[metric], rdf[metric]).pvalue)
        except Exception:
            p_value = float("nan")
    mean_delta = float(np.mean(delta))
    verdict = "no_improvement"
    if mean_delta > 0 and (not np.isfinite(p_value) or p_value >= 0.05):
        verdict = "positive_trend"
    if mean_delta > 0 and np.isfinite(p_value) and p_value < 0.05:
        verdict = "supports_improvement"
    return {
        "label": label,
        "left": left,
        "right": right,
        "metric": metric,
        "fold_deltas": delta.tolist(),
        "mean_delta": mean_delta,
        "std_delta": float(np.std(delta, ddof=1)) if len(delta) > 1 else 0.0,
        "paired_ttest_p": p_value,
        "verdict": verdict,
    }


def summarize_dataset(ft: pd.DataFrame) -> dict:
    label_originals = ft.attrs.get("label_originals", sorted(ft["label"].unique()))
    label_names = {
        int(i): CLASS_NAMES.get(int(original), str(original))
        for i, original in enumerate(label_originals)
    }
    patient_labels = ft.groupby("patient_id")["label"].first()
    return {
        "n_windows": int(len(ft)),
        "n_patients": int(ft["patient_id"].nunique()),
        "class_names": label_names,
        "window_label_counts": {
            str(k): int(v) for k, v in Counter(ft["label"]).items()
        },
        "patient_label_counts": {
            str(k): int(v) for k, v in Counter(patient_labels).items()
        },
    }


def write_summary(
    txt_path: Path,
    metadata: dict,
    results: dict[str, dict],
    comparisons: list[dict],
) -> None:
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("MFDFA feature-family ablation\n")
        f.write(f"Feature table: {metadata['feature_table']}\n")
        f.write(
            f"Task: {metadata['task']}  folds={metadata['folds']}  "
            f"n_trials={metadata['n_trials']}  fast={metadata['fast']}\n"
        )
        f.write(
            f"Windows={metadata['dataset']['n_windows']}  "
            f"Patients={metadata['dataset']['n_patients']}\n"
        )
        f.write(f"Class names: {metadata['dataset']['class_names']}\n\n")
        f.write(
            f"{'Condition':18s} {'Feat':>5s} {'MacroF1':>8s} {'std':>7s} "
            f"{'ptF1':>8s} {'AUC':>8s} {'ECE':>8s}\n"
        )
        f.write("-" * 72 + "\n")
        for key, res in results.items():
            f.write(
                f"{res['label']:18s} {res['n_features']:5d} "
                f"{res['macro_f1']:8.4f} {res['std_macro_f1']:7.4f} "
                f"{res['pt_macro_f1']:8.4f} {res['auc']:8.4f} {res['ece']:8.4f}\n"
            )
        f.write("\nPaired fold deltas (left - right, metric=macro_f1)\n")
        f.write("-" * 72 + "\n")
        for comp in comparisons:
            f.write(
                f"{comp['label']}: mean_delta={comp['mean_delta']:.6f}, "
                f"p={comp['paired_ttest_p']:.4g}, verdict={comp['verdict']}\n"
            )


def build_payload(metadata: dict, results: dict[str, dict]) -> dict:
    comparisons = [
        comp
        for comp in (
            paired_delta(results, left, right, label)
            for left, right, label in PAIRED_COMPARISONS
        )
        if comp is not None
    ]
    return {
        "metadata": metadata,
        "results": results,
        "paired_comparisons": comparisons,
    }


def write_outputs(json_path: Path, txt_path: Path, metadata: dict, results: dict[str, dict]) -> dict:
    payload = build_payload(metadata, results)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    write_summary(txt_path, metadata, results, payload["paired_comparisons"])
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feature-table",
        default=str(ROOT / "dataset_real" / "feature_table_combined.csv"),
        help="CSV with patient_id, label, and feature columns.",
    )
    parser.add_argument(
        "--classes",
        default=None,
        help="Optional comma list, e.g. non-stroke,ischemic or 0,1,2.",
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument(
        "--n-trials",
        type=int,
        default=20,
        help="Optuna trials per condition/fold. Use 0 with --fast for smoke tests.",
    )
    parser.add_argument("--fast", action="store_true", help="Skip Optuna tuning.")
    parser.add_argument(
        "--conditions",
        default="default",
        help="default/all or comma list: apfu,mfdfa,sqi,apfu_mfdfa,apfu_sqi,apfu_mfdfa_sqi",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-prefix",
        default="mfdfa_ablation",
        help="Output prefix under results/.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed conditions from an existing output JSON.",
    )
    args = parser.parse_args()

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    feature_table = Path(args.feature_table)
    classes = parse_classes(args.classes)
    condition_keys = selected_condition_keys(args.conditions)
    ft = load_feature_table(feature_table, classes)
    validate_features(ft, condition_keys)

    labels = sorted(ft["label"].unique())
    n_classes = len(labels)
    if n_classes < 2:
        raise ValueError("Need at least two classes for CV.")
    if ft["patient_id"].nunique() < args.folds:
        raise ValueError("Number of patients must be >= folds.")

    task = "binary" if n_classes == 2 else "multiclass"
    dataset_meta = summarize_dataset(ft)
    print(f"Loaded {feature_table}")
    print(f"Task: {task}")
    print(f"Windows: {dataset_meta['n_windows']:,}")
    print(f"Patients: {dataset_meta['n_patients']:,}")
    print(f"Class names: {dataset_meta['class_names']}")
    print(f"Window counts: {dataset_meta['window_label_counts']}")
    print(f"Patient counts: {dataset_meta['patient_label_counts']}\n")

    X_dummy = np.zeros((len(ft), 1))
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()
    splitter = choose_splitter(y, groups, args.folds, args.seed)
    folds = list(split_iter(splitter, X_dummy, y, groups))

    json_path = RESULTS_DIR / f"{args.output_prefix}_results.json"
    txt_path = RESULTS_DIR / f"{args.output_prefix}_summary.txt"
    metadata = {
        "feature_table": str(feature_table),
        "task": task,
        "folds": args.folds,
        "n_trials": args.n_trials,
        "fast": bool(args.fast),
        "conditions": condition_keys,
        "dataset": dataset_meta,
    }

    all_results = {}
    if args.resume and json_path.exists():
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        old_meta = existing.get("metadata", {})
        compatible = (
            old_meta.get("feature_table") == metadata["feature_table"]
            and old_meta.get("folds") == metadata["folds"]
            and old_meta.get("n_trials") == metadata["n_trials"]
            and bool(old_meta.get("fast")) == metadata["fast"]
        )
        if compatible:
            all_results = {
                key: value
                for key, value in existing.get("results", {}).items()
                if key in condition_keys
            }
            if all_results:
                done = ", ".join(all_results)
                print(f"Resuming from {json_path}; completed: {done}\n")
        else:
            print(f"Ignoring incompatible resume file: {json_path}\n")

    for key in condition_keys:
        if key in all_results:
            print(f"=== {CONDITIONS[key]['label']} already completed; skipping ===\n")
            continue
        all_results[key] = run_condition(
            ft,
            key,
            folds,
            n_classes,
            args.n_trials,
            args.fast,
            args.seed,
        )
        write_outputs(json_path, txt_path, metadata, all_results)
        print(f"Checkpoint -> {json_path}\n")

    payload = write_outputs(json_path, txt_path, metadata, all_results)

    print("=" * 72)
    print(
        f"{'Condition':18s} {'Feat':>5s} {'MacroF1':>8s} {'std':>7s} "
        f"{'ptF1':>8s} {'AUC':>8s} {'ECE':>8s}"
    )
    print("-" * 72)
    for key, res in all_results.items():
        print(
            f"{res['label']:18s} {res['n_features']:5d} "
            f"{res['macro_f1']:8.4f} {res['std_macro_f1']:7.4f} "
            f"{res['pt_macro_f1']:8.4f} {res['auc']:8.4f} {res['ece']:8.4f}"
        )
    if payload["paired_comparisons"]:
        print("\nPaired deltas, macro_f1")
        for comp in payload["paired_comparisons"]:
            print(
                f"- {comp['label']}: mean_delta={comp['mean_delta']:.6f}, "
                f"p={comp['paired_ttest_p']:.4g}, verdict={comp['verdict']}"
            )
    print(f"\nResults -> {json_path}")
    print(f"Summary -> {txt_path}")


if __name__ == "__main__":
    main()
