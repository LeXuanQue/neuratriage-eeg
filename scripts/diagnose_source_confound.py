"""Diagnose cross-cohort acquisition (site/rig) confound in the binary IS-vs-NS task.

Motivation
----------
`results/cv_summary.txt` reports AUC=1.000 for ischemic-vs-non-stroke. But the
ischemic cohort (`sub-*`, clinical rig) and the non-stroke cohort (`ns-*`, PhysioNet
resting) come from *different acquisition setups*, and in the current data the
recording source is 100% correlated with the label. A near-perfect AUC may therefore
reflect a rig/batch signature rather than stroke pathology.

This script quantifies that risk and doubles as the same-rig evaluation harness for
when a same-rig cohort (e.g. TUH) is added:

  1. source<->label cross-tab (is the confound perfect on this data?).
  2. "shortcut" probe -- patient-level GroupKFold CV using three feature families:
       * ENTROPY-only  (pathology-bearing non-linear features)
       * SQI-only      (signal-quality / acquisition proxy -- should NOT encode stroke)
       * FULL          (entropy + MFDFA + SQI)
     If SQI-only ~= FULL ~= 1.0 >> ENTROPY-only, the classifier has an
     acquisition-correlated shortcut == confound evidence.
  3. (optional) leave-one-source-out cross-source test for genuine same-rig data.

Usage
-----
  .venv/Scripts/python.exe scripts/diagnose_source_confound.py
  .venv/Scripts/python.exe scripts/diagnose_source_confound.py --fast
  .venv/Scripts/python.exe scripts/diagnose_source_confound.py \
      --combined-csv dataset_ischemic/feature_table_combined.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold

import lightgbm as lgb

from eeg_stroke_pipeline import ENTROPY_FEATURES, MFDFA_FEATURES, SQI_FEATURES

RESULTS_DIR = ROOT / "results"

# patient_id prefix -> acquisition source. In the current data source == label,
# which is exactly the confound this script measures.
_SOURCE_RULES: tuple[tuple[str, str], ...] = (
    ("sub-", "clinical_ischemic"),
    ("ns-", "physionet_nonstroke"),
    ("uclh", "uclh_hemorrhagic"),
    ("tuh", "tuh_samerig"),  # future same-rig cohort
)


def derive_source(patient_ids: pd.Series) -> pd.Series:
    """Map each patient_id to its acquisition source by prefix."""
    def _one(pid: str) -> str:
        low = str(pid).lower()
        for prefix, name in _SOURCE_RULES:
            if low.startswith(prefix):
                return name
        return "other"

    return patient_ids.map(_one)


def source_label_crosstab(ft: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """Cross-tabulate source vs label. Returns (crosstab, is_perfectly_confounded).

    Perfectly confounded == every source carries exactly one label.
    """
    src = derive_source(ft["patient_id"])
    ct = pd.crosstab(src, ft["label"])
    nonzero_labels_per_source = (ct > 0).sum(axis=1)
    confounded = bool((nonzero_labels_per_source == 1).all())
    return ct, confounded


def _binary_cv(ft: pd.DataFrame, feature_cols: list[str], n_folds: int,
               fast: bool) -> dict:
    """Patient-level GroupKFold CV; returns mean macro-F1 / AUC over folds."""
    feats = [c for c in feature_cols if c in ft.columns]
    X = ft[feats].astype(float).to_numpy()
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()

    params = dict(objective="binary", is_unbalance=True, random_state=42,
                  n_jobs=-1, verbosity=-1)
    if fast:
        params.update(n_estimators=120, num_leaves=31)

    f1s, aucs = [], []
    for tr, te in GroupKFold(n_splits=n_folds).split(X, y, groups):
        clf = lgb.LGBMClassifier(**params)
        clf.fit(X[tr], y[tr])
        prob = clf.predict_proba(X[te])[:, 1]
        pred = (prob >= 0.5).astype(int)
        f1s.append(f1_score(y[te], pred, average="macro", zero_division=0))
        if len(np.unique(y[te])) > 1:
            aucs.append(roc_auc_score(y[te], prob))
    return {
        "n_features": len(feats),
        "macro_f1": float(np.mean(f1s)),
        "auc": float(np.mean(aucs)) if aucs else float("nan"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--combined-csv",
        default=str(ROOT / "dataset_ischemic" / "feature_table_combined.csv"),
    )
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--fast", action="store_true",
                        help="Smaller LightGBM for a quick sanity check")
    args = parser.parse_args()

    csv_path = Path(args.combined_csv)
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found.")
        sys.exit(1)

    ft = pd.read_csv(csv_path)
    label_map = {0: 0, 1: 1, "non-stroke": 0, "nonstroke": 0, "normal": 0,
                 "ischemic": 1, "is": 1}
    ft["label"] = ft["label"].map(lambda v: label_map.get(v, v))
    ft = ft[ft["label"].isin([0, 1])].copy()
    ft["label"] = ft["label"].astype(int)

    print(f"Loaded {csv_path.name}: {len(ft):,} windows, "
          f"{ft['patient_id'].nunique()} patients\n")

    # 1) confound structure
    ct, confounded = source_label_crosstab(ft)
    print("Source x label cross-tab (rows=source, cols=label 0=NS/1=IS):")
    print(ct.to_string())
    print(f"\nPerfectly confounded (each source -> one label): {confounded}")
    if confounded:
        print("  => Within THIS data, pathology and acquisition cannot be "
              "separated.\n     A same-rig cohort (e.g. TUH) is required to "
              "resolve it; the\n     shortcut probe below only demonstrates the "
              "risk.\n")

    # 2) shortcut probe
    feature_sets = {
        "ENTROPY-only": list(ENTROPY_FEATURES),
        "SQI-only": list(SQI_FEATURES),
        "FULL (Ent+MFDFA+SQI)": list(ENTROPY_FEATURES) + list(MFDFA_FEATURES)
        + list(SQI_FEATURES),
    }
    print(f"Patient-level {args.folds}-fold CV by feature family"
          f"{' (fast)' if args.fast else ''}:")
    print(f"{'Feature family':24s}  {'#feat':>5}  {'MacroF1':>7}  {'AUC':>7}")
    print("-" * 50)
    probe = {}
    for name, feats in feature_sets.items():
        res = _binary_cv(ft, feats, args.folds, args.fast)
        probe[name] = res
        print(f"{name:24s}  {res['n_features']:5d}  "
              f"{res['macro_f1']:7.3f}  {res['auc']:7.3f}")
    print("-" * 50)

    sqi = probe["SQI-only"]["auc"]
    ent = probe["ENTROPY-only"]["auc"]
    verdict = (
        "CONFOUND LIKELY: signal-quality features alone nearly separate the "
        "classes, so the model can shortcut on acquisition rather than pathology."
        if (not np.isnan(sqi) and sqi >= 0.95 and sqi - ent > 0.05)
        else "No strong SQI shortcut detected on this split."
    )
    print(f"\nVerdict: {verdict}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "csv": str(csv_path),
        "n_windows": int(len(ft)),
        "n_patients": int(ft["patient_id"].nunique()),
        "perfectly_confounded": confounded,
        "crosstab": ct.to_dict(),
        "probe": probe,
        "verdict": verdict,
    }
    json_path = RESULTS_DIR / "source_confound_report.json"
    json_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nReport -> {json_path}")


if __name__ == "__main__":
    main()
