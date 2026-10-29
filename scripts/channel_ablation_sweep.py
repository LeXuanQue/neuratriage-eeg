"""Channel-budget ablation sweep on a (same-rig) feature table.

Answers the wearable-headband question: *which ~4 channels still hold the
pathology signal?* Two parts:

  1. **Data-driven per-channel ranking** — train one LightGBM on every
     channel-attributable entropy/MFDFA feature and sum its gain-importance onto
     the channel(s) each feature comes from, giving a ranking of which electrodes
     actually carry discriminative signal.
  2. **Budget sweep** — evaluate several channel sets (all-18, data-driven
     top-8/4/2, a domain-symmetric 4, a Focus+-like device 4, an asymmetry-only 2)
     with the SAME patient-level GroupKFold CV, printed as one comparison table so
     the accuracy-vs-#channels tradeoff is explicit.

Reuse: the feature-subset selection and CV are imported verbatim from
``run_low_channel_ablation.py`` (no re-implementation). Same caveat as that
script — features are subset from the 18-channel, CAR-referenced table; the
asymmetry / abs-diff features are CAR-invariant (a difference cancels the common
average) and so are exact, but absolute per-channel entropy is approximate for a
true low-channel montage. Rebuild from raw NPZ per subset for final claims.

Usage
-----
  .venv/Scripts/python.exe scripts/channel_ablation_sweep.py ^
      --combined-csv dataset_tuh/feature_table_tuh.csv --fast
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from eeg_stroke_pipeline import (
    DEFAULT_CHANNELS,
    HOMOLOGOUS_PAIRS,
    MFDFA_SUMMARY_FEATURES,
    REGION_MAP,
)
from run_low_channel_ablation import LABEL_MAP, low_channel_features, run_cv


def feature_to_channels(feat: str) -> list[str]:
    """Map one feature column to the electrode(s) it is derived from."""
    for left, right in HOMOLOGOUS_PAIRS:
        if feat in (
            f"apen_asym_{left}_{right}",
            f"fuen_asym_{left}_{right}",
            f"apfu_absdiff_{left}_{right}",
        ):
            return [left, right]
    for region, chs in REGION_MAP.items():
        if feat.startswith(region + "_") and feat[len(region) + 1:] in MFDFA_SUMMARY_FEATURES:
            return list(chs)
    if feat.startswith("apen_"):
        return [feat[len("apen_"):]]
    if feat.startswith("fuen_"):
        return [feat[len("fuen_"):]]
    return []


def rank_channels(ft: pd.DataFrame, fast: bool) -> list[tuple[str, float]]:
    """Rank electrodes by summed LightGBM gain-importance of their features."""
    feats = low_channel_features(ft, list(DEFAULT_CHANNELS), include_sqi=False)
    X = SimpleImputer(strategy="median").fit_transform(ft[feats].astype(float).to_numpy())
    y = ft["label"].to_numpy(dtype=int)

    params = dict(objective="binary", is_unbalance=True, random_state=42,
                  n_jobs=-1, verbosity=-1)
    if fast:
        params.update(n_estimators=200, num_leaves=31)
    clf = lgb.LGBMClassifier(**params).fit(X, y)
    gain = clf.booster_.feature_importance(importance_type="gain")

    per_channel: dict[str, float] = {ch: 0.0 for ch in DEFAULT_CHANNELS}
    for f, g in zip(feats, gain):
        chans = feature_to_channels(f)
        if not chans:
            continue
        share = float(g) / len(chans)  # split gain evenly across contributing channels
        for ch in chans:
            per_channel[ch] = per_channel.get(ch, 0.0) + share
    return sorted(per_channel.items(), key=lambda kv: kv[1], reverse=True)


def build_sets(ranked: list[str]) -> dict[str, list[str]]:
    """Channel sets to sweep, derived from the data-driven ranking + priors."""
    return {
        "ALL-18": list(DEFAULT_CHANNELS),
        "data-top8": ranked[:8],
        "data-top4": ranked[:4],
        "data-top2": ranked[:2],
        "domain-SYM4 [C3,C4,T3,T4]": ["C3", "C4", "T3", "T4"],
        "device-FOCUS4 [F7,F8,T3,T4]": ["F7", "F8", "T3", "T4"],
        "asym-2 [T3,T4]": ["T3", "T4"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined-csv",
                        default=str(ROOT / "dataset_tuh" / "feature_table_tuh.csv"))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--include-sqi", action="store_true",
                        help="Add the 5 global SQI features to every set (off by "
                             "default so differences reflect channel content only).")
    parser.add_argument("--out",
                        default=str(ROOT / "results" / "channel_ablation_sweep.json"))
    args = parser.parse_args()

    ft = pd.read_csv(args.combined_csv)
    ft["patient_id"] = ft["patient_id"].astype(str)
    ft["label"] = ft["label"].map(lambda x: LABEL_MAP.get(x, LABEL_MAP.get(str(x).lower())))
    ft = ft.dropna(subset=["label"]).copy()
    ft["label"] = ft["label"].astype(int)
    ft = ft[ft["label"].isin([0, 1])].copy()

    print(f"Input    : {args.combined_csv}")
    print(f"Windows  : {len(ft):,}   Patients: {ft['patient_id'].nunique()}   "
          f"Labels: {dict(ft['label'].value_counts().sort_index())}")
    print(f"SQI      : {'included' if args.include_sqi else 'excluded'}   "
          f"(features subset from 18-ch CAR table; asym features CAR-invariant)\n")

    ranked_pairs = rank_channels(ft, args.fast)
    ranked = [ch for ch, _ in ranked_pairs]
    print("Per-channel importance ranking (summed gain):")
    for i, (ch, g) in enumerate(ranked_pairs, 1):
        print(f"  {i:2d}. {ch:3s}  {g:12.1f}")
    print()

    sets = build_sets(ranked)
    print(f"{'channel set':30s}  {'#ch':>3}  {'#feat':>5}  {'macroF1':>7}  "
          f"{'AUC':>6}  {'ptAUC':>6}")
    print("-" * 68)
    results = {}
    for name, chans in sets.items():
        feats = low_channel_features(ft, chans, include_sqi=args.include_sqi)
        res = run_cv(ft, feats, args.folds, args.fast)
        results[name] = {"channels": chans, "n_features": len(feats), **res}
        print(f"{name:30s}  {len(chans):3d}  {len(feats):5d}  "
              f"{res['macro_f1']:7.3f}  {res['auc']:6.3f}  {res['pt_auc']:6.3f}")
    print("-" * 68)

    out = {
        "input_csv": str(Path(args.combined_csv).resolve()),
        "n_windows": int(len(ft)),
        "n_patients": int(ft["patient_id"].nunique()),
        "include_sqi": args.include_sqi,
        "channel_ranking": [{"channel": c, "gain": g} for c, g in ranked_pairs],
        "sweep": {k: {kk: vv for kk, vv in v.items() if kk != "fold_results"}
                  for k, v in results.items()},
        "limitation": ("Subset from precomputed 18-ch CAR features; asym/absdiff "
                       "are CAR-invariant, absolute per-channel entropy approximate. "
                       "Rebuild raw per-subset montage for final evidence."),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
