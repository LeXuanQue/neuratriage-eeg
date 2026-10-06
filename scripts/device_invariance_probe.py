"""Device-confound harness + Device-Adversarial Feature Elimination (DAFE).

The 50 IS / 50 NS cohort cannot separate pathology from recording device
(source == label for every subject). This harness measures device leakage on
pairs where the pathology label is held CONSTANT, so any separability is site:

  device_normal : PhysioNet NS  vs TUH background   (both label 0)
  device_patho  : clinical IS   vs TUH slowing      (both label 1)

and pathology signal on a single rig:

  patho_samerig : TUH slowing vs TUH background (TUSL)

A feature set is good when device AUC -> 0.5 AND same-rig pathology AUC stays
high. DAFE selects features on `device_normal` only (site labels, never
pathology labels) and is checked on the held-out `device_patho` pair.

Caveat: "site" = device + population (TUH patients vs PhysioNet volunteers),
not device alone.

Usage:
  .venv/Scripts/python.exe scripts/device_invariance_probe.py [--fast] [--cap 60]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Callable

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from diagnose_source_confound import _binary_cv  # noqa: E402

RESULTS_DIR = ROOT / "results"
META = ("patient_id", "label", "t_end_sec", "orig_label")


def build_probe_frames(cross: pd.DataFrame, tuh: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return the four evaluation frames; in device_* frames `label` = site (1 = TUH)."""
    def _site_pair(orig_label: int) -> pd.DataFrame:
        a = cross[cross["label"] == orig_label].assign(orig_label=orig_label, label=0)
        b = tuh[tuh["label"] == orig_label].assign(orig_label=orig_label, label=1)
        return pd.concat([a, b], ignore_index=True)

    return {
        "device_normal": _site_pair(0),
        "device_patho": _site_pair(1),
        "patho_samerig": tuh.reset_index(drop=True),
        "crosscohort": cross.reset_index(drop=True),
    }


def cap_windows_per_patient(df: pd.DataFrame, cap: int, seed: int = 0) -> pd.DataFrame:
    """Keep at most `cap` windows per patient (deterministic) so big cohorts don't dominate."""
    parts = [g.sample(n=min(len(g), cap), random_state=seed) for _, g in df.groupby("patient_id", sort=True)]
    return pd.concat(parts).sort_values(["patient_id", "t_end_sec"]).reset_index(drop=True)


def add_mfdfa_contrasts(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Add left-minus-right MFDFA features per region.

    A device shifts both hemispheres alike, so within-recording contrasts should
    cancel much of the rig signature while keeping lateralised (stroke-like) change.
    """
    new = {}
    for col in df.columns:
        if "_left_" in col:
            right = col.replace("_left_", "_right_", 1)
            if right in df.columns:
                new[col.replace("_left_", "_lr_", 1)] = df[col] - df[right]
    return pd.concat([df, pd.DataFrame(new, index=df.index)], axis=1), list(new)


def _auc(df: pd.DataFrame, feats: list[str], folds: int, fast: bool) -> float:
    folds = min(folds, df["patient_id"].nunique())
    return _binary_cv(df, feats, folds, fast)["auc"]


def evaluate_candidate(probes: dict[str, pd.DataFrame], feats: list[str], folds: int = 5,
                       fast: bool = True) -> dict[str, float]:
    return {
        "n_features": len(feats),
        "device_auc_normal": _auc(probes["device_normal"], feats, folds, fast),
        "device_auc_patho": _auc(probes["device_patho"], feats, folds, fast),
        "patho_auc_samerig": _auc(probes["patho_samerig"], feats, folds, fast),
        "crosscohort_auc": _auc(probes["crosscohort"], feats, folds, fast),
    }


def split_patients(df: pd.DataFrame, frac: float = 0.5, seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by patient (never by window), separately within each label, into (select, held-out)."""
    rng = np.random.default_rng(seed)
    pick: set = set()
    for _, g in df.groupby("label"):
        pats = np.array(sorted(g["patient_id"].unique()))
        rng.shuffle(pats)
        pick.update(pats[: max(1, int(round(frac * len(pats))))])
    mask = df["patient_id"].isin(pick)
    return df[mask].reset_index(drop=True), df[~mask].reset_index(drop=True)


def device_adversarial_elimination(device_df: pd.DataFrame, feats: list[str], target_auc: float = 0.65,
                                   drop_per_step: int = 5, folds: int = 5, fast: bool = True,
                                   max_steps: int = 100,
                                   on_step: Callable[[list[str]], dict] | None = None) -> dict:
    """Repeatedly drop the features a site classifier relies on most, until it fails.

    Uses only site labels from `device_df`, so pathology labels never inform selection.
    `on_step(kept)` is evaluated at every step to trace the invariance/utility frontier.
    """
    kept = [f for f in feats if f in device_df.columns]
    history = []
    for _ in range(max_steps):
        auc = _auc(device_df, kept, folds, fast)
        step = {"n_features": len(kept), "device_auc": auc, "dropped": []}
        if on_step is not None:
            step["eval"] = on_step(list(kept))
        history.append(step)
        if auc <= target_auc or len(kept) <= drop_per_step:
            break
        clf = lgb.LGBMClassifier(objective="binary", is_unbalance=True, random_state=42,
                                 n_estimators=120, num_leaves=31, importance_type="gain", verbosity=-1)
        clf.fit(device_df[kept].astype(float).to_numpy(), device_df["label"].to_numpy(dtype=int))
        order = np.argsort(clf.feature_importances_)[::-1][:drop_per_step]
        step["dropped"] = [kept[i] for i in order]
        kept = [f for f in kept if f not in step["dropped"]]
    return {"kept": kept, "history": history}


def univariate_device_auc(device_df: pd.DataFrame, feats: list[str]) -> dict[str, float]:
    """|AUC - 0.5| + 0.5 of each feature alone for separating sites (no model)."""
    from sklearn.metrics import roc_auc_score
    y = device_df["label"].to_numpy(dtype=int)
    out = {}
    for f in feats:
        x = device_df[f].astype(float)
        ok = x.notna().to_numpy()
        if ok.sum() > 10 and len(np.unique(y[ok])) == 2:
            a = roc_auc_score(y[ok], x[ok])
            out[f] = float(max(a, 1 - a))
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cross-csv", default=str(ROOT / "dataset_ischemic" / "feature_table_combined.csv"))
    ap.add_argument("--tuh-csv", default=str(ROOT / "dataset_tuh" / "feature_table_tuh.csv"))
    ap.add_argument("--cap", type=int, default=60, help="max windows per patient")
    ap.add_argument("--target-auc", type=float, default=0.65)
    ap.add_argument("--drop-per-step", type=int, default=5)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--frontier", action="store_true", help="trace held-out invariance/utility along DAFE")
    ap.add_argument("--frontier-step", type=int, default=10)
    ap.add_argument("--out", default=str(RESULTS_DIR / "device_invariance.json"))
    args = ap.parse_args()

    cross = cap_windows_per_patient(pd.read_csv(args.cross_csv), args.cap)
    tuh = cap_windows_per_patient(pd.read_csv(args.tuh_csv), args.cap)
    cross, contrast = add_mfdfa_contrasts(cross)
    tuh, _ = add_mfdfa_contrasts(tuh)
    probes = build_probe_frames(cross, tuh)

    base = [c for c in cross.columns if c not in META and c not in contrast]
    sqi = [c for c in base if c.startswith("sqi_")]
    ent = [c for c in base if c.startswith(("apen", "fuen", "apfu"))]
    ent_asym = [c for c in ent if "asym" in c or "absdiff" in c]
    mfdfa = [c for c in base if c not in sqi and c not in ent]
    candidates = {
        "FULL (125)": base,
        "NO_SQI": ent + mfdfa,
        "ENTROPY": ent,
        "MFDFA": mfdfa,
        "ASYM (entropy asym + MFDFA L-R)": ent_asym + contrast,
    }
    results = {name: evaluate_candidate(probes, feats, fast=args.fast) for name, feats in candidates.items()}

    dafe = device_adversarial_elimination(probes["device_normal"], base + contrast, args.target_auc,
                                          args.drop_per_step, fast=args.fast)
    results["DAFE (selected on device_normal)"] = evaluate_candidate(probes, dafe["kept"], fast=args.fast)

    print(f"{'candidate':36s} {'#f':>4s} {'devAUC_norm':>11s} {'devAUC_patho':>12s} {'pathoAUC_rig':>12s} {'crossAUC':>9s}")
    for name, r in results.items():
        print(f"{name:36s} {r['n_features']:4d} {r['device_auc_normal']:11.3f} {r['device_auc_patho']:12.3f} "
              f"{r['patho_auc_samerig']:12.3f} {r['crosscohort_auc']:9.3f}")
    uni = univariate_device_auc(probes["device_normal"], base)
    print("\nTop device-leaky single features (device_normal):")
    for f, a in list(uni.items())[:12]:
        print(f"  {f:34s} {a:.3f}")

    frontier = []
    if args.frontier:
        # Honest DAFE: select on half the device_normal patients, measure on the other half.
        sel, held = split_patients(probes["device_normal"], frac=0.5, seed=0)

        def _eval(kept: list[str]) -> dict:
            return {
                "device_auc_normal_heldout": _auc(held, kept, 5, args.fast),
                "device_auc_patho": _auc(probes["device_patho"], kept, 5, args.fast),
                "patho_auc_samerig": _auc(probes["patho_samerig"], kept, 5, args.fast),
            }

        path = device_adversarial_elimination(sel, base + contrast, target_auc=0.55,
                                              drop_per_step=args.frontier_step, fast=args.fast, on_step=_eval)
        print(f"\nFrontier (select on {sel['patient_id'].nunique()} pts, held-out {held['patient_id'].nunique()} pts):")
        print(f"{'#f':>4s} {'devAUC_sel':>10s} {'devAUC_held':>11s} {'devAUC_patho':>12s} {'pathoAUC_rig':>12s}")
        for h in path["history"]:
            e = h["eval"]
            print(f"{h['n_features']:4d} {h['device_auc']:10.3f} {e['device_auc_normal_heldout']:11.3f} "
                  f"{e['device_auc_patho']:12.3f} {e['patho_auc_samerig']:12.3f}")
            frontier.append({"n_features": h["n_features"], "device_auc_select": h["device_auc"], **e,
                             "dropped": h["dropped"]})

    out = {"args": vars(args), "results": results, "dafe": dafe, "frontier": frontier,
           "univariate_device_auc_top30": dict(list(uni.items())[:30]),
           "n_patients": {k: int(v["patient_id"].nunique()) for k, v in probes.items()}}
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nReport -> {args.out}")


if __name__ == "__main__":
    main()
