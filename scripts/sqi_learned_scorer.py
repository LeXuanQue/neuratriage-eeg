"""Fit, freeze and check the learned SQI v2 channel scorer (plan: docs/paper_outline.md section 6).

Pre-registered in commit 4d03e4d before any number of this model was seen:

1. fit ``tuar_sqi_eval.fit_logistic`` on SQI v2 features of the TUAR *calibration* half;
   operating threshold = 95th percentile of P(artifact) on its clean channel-windows;
2. evaluate once on the test half against v1 fitted the same way (patient bootstrap);
3. E9 safety gate with the scorer (IS not gated more than NS, TUSL slow not more than bckg).
   If it fails, one fixed variant drops the brain-state features (delta_ratio, alpha_peak);
4. promote the scorer to ``results/sqi_v2_learned_scorer.json`` (what the live tracker
   loads) only if steps 2 and 3 pass.

Usage::

    .venv/Scripts/python.exe scripts/sqi_learned_scorer.py
    .venv/Scripts/python.exe scripts/sqi_learned_scorer.py --variant no_brain_state
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CLEAN_QUANTILE = 0.95
VARIANTS = {
    "all": (),
    "no_brain_state": ("delta_ratio", "alpha_peak"),
}
DEPLOYED = ROOT / "results" / "sqi_v2_learned_scorer.json"


def export_pipeline(model, features: Sequence[str], threshold: float) -> dict:
    """Plain-number copy of a fitted ``fit_logistic`` pipeline (imputer -> quantile -> logistic)."""
    imputer, quantile, logistic = (step for _, step in model.steps)
    if quantile.output_distribution != "normal":
        raise ValueError("the numpy runtime only replays output_distribution='normal'")
    medians = np.nan_to_num(np.asarray(imputer.statistics_, dtype=float), nan=0.0)
    return {
        "features": list(features),
        "medians": medians.tolist(),
        "quantiles": np.asarray(quantile.quantiles_, dtype=float).tolist(),
        "references": np.asarray(quantile.references_, dtype=float).tolist(),
        "coef": np.asarray(logistic.coef_, dtype=float).ravel().tolist(),
        "intercept": float(np.ravel(logistic.intercept_)[0]),
        "threshold": float(threshold),
    }


def operating_threshold(p_clean: np.ndarray, quantile: float = CLEAN_QUANTILE) -> float:
    """P(artifact) above which only ``1 - quantile`` of clean channel-windows are flagged."""
    return float(np.quantile(np.asarray(p_clean, dtype=float), quantile))


def _load_features():
    import pandas as pd

    df = pd.read_csv(ROOT / "results" / "tuar_sqi_features.csv")
    df["kind"] = df["kind"].fillna("")
    return df[df["label"] >= 0].reset_index(drop=True)


def fit_and_test(df, features: Sequence[str], n_boot: int, seed: int) -> tuple[dict, dict]:
    """Steps 1-2: (frozen scorer dict, test-half report)."""
    import sqi_learned
    import tuar_sqi_eval as T

    calib_pids, test_pids = T.split_patients(df["pid"].unique())
    calib, test = df[df["pid"].isin(calib_pids)], df[df["pid"].isin(test_pids)]
    y_cal = calib["label"].to_numpy()
    v2 = T.fit_logistic(calib[list(features)].to_numpy(float), y_cal)
    v1 = T.fit_logistic(calib[list(T.V1_FEATURES)].to_numpy(float), y_cal)
    p_cal = v2.predict_proba(calib[list(features)].to_numpy(float))[:, 1]
    frozen = export_pipeline(v2, features, operating_threshold(p_cal[y_cal == 0]))

    scorer = sqi_learned.learned_scorer_from_dict(frozen)
    y, pids = test["label"].to_numpy(), test["pid"].to_numpy()
    s2 = scorer.probability_matrix(test[list(features)].to_numpy(float))
    s1 = v1.predict_proba(test[list(T.V1_FEATURES)].to_numpy(float))[:, 1]
    vs_learned = T.paired_patient_bootstrap(pids, y, s1, s2, n_boot, seed)
    vs_fixed = T.paired_patient_bootstrap(pids, y, 1 - test["v1_total"].to_numpy(), s2, n_boot, seed)
    flagged = s2 > scorer.threshold
    report = {
        "n_test_rows": int(len(test)), "n_test_patients": int(test["pid"].nunique()),
        "vs_v1_learned_on_calib": T._result_dict(vs_learned),
        "vs_v1_fixed": T._result_dict(vs_fixed),
        "test_clean_flag_rate": float(flagged[y == 0].mean()),
        "test_artifact_flag_rate": float(flagged[y == 1].mean()),
        "beats_v1": bool(vs_learned.diff > 0 and vs_fixed.diff > 0),
    }
    return frozen, report


def main() -> None:
    from sqi_v2_gate_check import gate_check
    import sqi_learned

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="all")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import tuar_sqi_eval as T

    features = [f for f in T.V2_FEATURES if f not in VARIANTS[args.variant]]
    df = _load_features()
    frozen, test_report = fit_and_test(df, features, args.n_boot, args.seed)
    frozen["meta"] = {
        "fitted_on": "TUAR v3.0.1 calibration half", "split_salt": T.SPLIT_SALT,
        "clean_quantile": CLEAN_QUANTILE, "variant": args.variant, "date": date.today().isoformat(),
    }
    candidate = ROOT / "results" / f"sqi_v2_learned_scorer_candidate_{args.variant}.json"
    candidate.write_text(json.dumps(frozen), encoding="utf-8")
    print(json.dumps(test_report, indent=2), flush=True)

    e9 = gate_check(sqi_learned.learned_scorer_from_dict(frozen))
    promote = test_report["beats_v1"] and e9["safety_ok"]
    report = {"variant": args.variant, "features": features, "threshold": frozen["threshold"],
              "test_half": test_report, "e9_with_scorer": e9, "promoted": promote}
    out = ROOT / "results" / f"sqi_learned_scorer_eval_{args.variant}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if promote:
        shutil.copyfile(candidate, DEPLOYED)
    print(json.dumps({k: report[k] for k in ("variant", "threshold", "promoted")}, indent=2))
    print("E9:", {k: e9[k]["gated_rate"] for k in ("IS", "NS", "TUSL_slow", "TUSL_bckg")}, "safety_ok", e9["safety_ok"])


if __name__ == "__main__":
    main()
