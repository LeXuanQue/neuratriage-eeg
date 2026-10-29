"""Real headband montage: 2 differential (bipolar) channels + selective prediction.

Target headband has electrodes F3, F4, T7(=T3), T8(=T4) but streams only 2
DIFFERENTIAL channels. This synthesises the exact bipolar montage from same-rig TUH
monopolar data -- default L = F3-T3 (left), R = F4-T4 (right), i.e. a fronto-temporal
derivation per hemisphere -- computes the wearable feature stack (entropy + per-channel
MFDFA + qEEG DAR/DTABR/pdBSI) on the 2 bipolar signals, runs patient-level GroupKFold,
and reports a SELECTIVE-PREDICTION (risk-coverage) curve: accuracy on the windows the
system chooses to decide (No-Decision as a measurable accuracy lever).

CAR cancels in a bipolar difference ((F3-mean) - (T3-mean) = F3 - T3), so preprocessing
the monopolar set with the pipeline's CAR then subtracting yields the true reference-free
bipolar signal. Pairing (which electrode minus which) is a device fact -- confirm via
ble_probe; override with --pairs "F3-T3,F4-T4".

Usage
-----
  .venv/Scripts/python.exe scripts/run_headband_eval.py --fast
  .venv/Scripts/python.exe scripts/run_headband_eval.py --pairs "F3-T3,F4-T4" --fast
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

BANDS = {"delta": (1.0, 4.0), "theta": (4.0, 8.0),
         "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}
_EPS = 1e-8


def _bipolar_feature_row(bip, labels, cfg):
    """entropy + per-channel MFDFA + qEEG for the 2 bipolar signals (rows of bip)."""
    import numpy as np
    from eeg_stroke_pipeline import (approximate_entropy, compute_welch_bandpower,
                                     fuzzy_entropy, mfdfa_features)

    feats: dict[str, float] = {}
    apen, fuen = {}, {}
    for i, lab in enumerate(labels):
        sig = np.asarray(bip[i], dtype=float)
        apen[lab] = approximate_entropy(sig, m=cfg.entropy_m, r_factor=cfg.entropy_r_factor)
        fuen[lab] = fuzzy_entropy(sig, m=cfg.entropy_m, r_factor=cfg.entropy_r_factor,
                                  n_power=cfg.fuzzy_n)
        feats[f"apen_{lab}"] = float(apen[lab])
        feats[f"fuen_{lab}"] = float(fuen[lab])
        if int(np.sum(np.isfinite(sig))) >= max(64, 4 * cfg.mfdfa_scale_min):
            try:
                summ = mfdfa_features(sig, q_values=cfg.mfdfa_q, order=cfg.mfdfa_order,
                                      scale_min=cfg.mfdfa_scale_min,
                                      scale_count=cfg.mfdfa_scale_count)
                for k, v in summ.items():
                    feats[f"mfdfa_{lab}_{k}"] = float(v)
            except Exception:
                pass
    # left/right asymmetry between the two bipolar channels
    l, r = labels[0], labels[1]
    feats[f"apen_asym_{l}_{r}"] = float(apen[l] - apen[r])
    feats[f"fuen_asym_{l}_{r}"] = float(fuen[l] - fuen[r])
    feats[f"apfu_absdiff_{l}_{r}"] = float(abs((apen[l] + fuen[l]) - (apen[r] + fuen[r])))
    # qEEG band-power markers
    bpow = {b: compute_welch_bandpower(bip, cfg.fs, band) for b, band in BANDS.items()}
    for i, lab in enumerate(labels):
        d, t, a, be = (bpow["delta"][i], bpow["theta"][i], bpow["alpha"][i], bpow["beta"][i])
        feats[f"dar_{lab}"] = float(d / (a + _EPS))
        feats[f"dtabr_{lab}"] = float((d + t) / (a + be + _EPS))
    feats[f"pdbsi_{l}_{r}"] = float(np.mean(
        [abs(bpow[b][1] - bpow[b][0]) / (bpow[b][1] + bpow[b][0] + _EPS) for b in BANDS]))
    return feats


def _extract_one(args):
    import warnings
    warnings.filterwarnings("ignore")
    import sys as _sys
    _sys.path.insert(0, str(BACKEND))
    import numpy as np
    from eeg_stroke_pipeline import (PipelineConfig, load_array_file, parse_label,
                                     preprocess_eeg, reorder_to_target_channels)

    patient_id, label_raw, path_str, fs_manifest, pairs, labels, cfg_dict = args
    cfg = PipelineConfig(**cfg_dict)
    electrodes = sorted({e for p in pairs for e in p})
    cfg.channels = electrodes

    data, ch_names, fs_file = load_array_file(path_str)
    fs = float(fs_manifest) if fs_manifest is not None else (fs_file or cfg.fs)
    ordered = reorder_to_target_channels(data, ch_names, electrodes)
    x = preprocess_eeg(ordered, fs, cfg)              # CAR cancels in the bipolar diff
    eidx = {e: i for i, e in enumerate(electrodes)}
    label = parse_label(label_raw)

    entropy_len = int(round(cfg.entropy_window_sec * cfg.fs))
    bp_len = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step = int(round(cfg.entropy_step_sec * cfg.fs))
    min_len = max(entropy_len, bp_len)

    rows = []
    for end in range(min_len, x.shape[1] + 1, step):
        bip = np.vstack([x[eidx[a], end - bp_len:end] - x[eidx[b], end - bp_len:end]
                         for a, b in pairs])
        feats = _bipolar_feature_row(bip, labels, cfg)
        feats.update(patient_id=patient_id, label=label, t_end_sec=end / cfg.fs)
        rows.append(feats)
    return patient_id, rows


def risk_coverage(y, oof, coverages):
    """Accuracy on the top-coverage most-confident windows (selective prediction)."""
    import numpy as np
    from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score

    conf = np.abs(oof - 0.5)
    pred = (oof >= 0.5).astype(int)
    order = np.argsort(-conf)
    out = []
    for cov in coverages:
        k = max(20, int(round(cov * len(y))))
        idx = order[:k]
        yi, pi, pr = y[idx], oof[idx], pred[idx]
        auc = float(roc_auc_score(yi, pi)) if len(np.unique(yi)) > 1 else float("nan")
        out.append({"coverage": cov, "n": int(k),
                    "macro_f1": float(f1_score(yi, pr, average="macro", zero_division=0)),
                    "bal_acc": float(balanced_accuracy_score(yi, pr)),
                    "auc": auc, "pos_rate": float(np.mean(yi))})
    return out


def main():
    import numpy as np
    import pandas as pd
    from concurrent.futures import ProcessPoolExecutor, as_completed
    import lightgbm as lgb
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import f1_score, roc_auc_score
    from sklearn.model_selection import GroupKFold
    from eeg_stroke_pipeline import PipelineConfig

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(ROOT / "dataset_tuh" / "manifest_tuh.csv"))
    parser.add_argument("--pairs", default="F3-T3,F4-T4",
                        help="Bipolar channels 'A-B,C-D' (T7->T3, T8->T4).")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", default=str(ROOT / "results" / "headband_eval.json"))
    args = parser.parse_args()

    pairs = tuple(tuple(p.split("-")) for p in args.pairs.split(","))
    labels = ["".join(p) for p in pairs]          # e.g. ['F3T3','F4T4']
    cfg = PipelineConfig()
    cfg_dict = {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.__dict__.items()}

    manifest = pd.read_csv(args.manifest)
    wargs = [(str(r["patient_id"]), r["label"], str(r["path"]),
              float(r["fs"]) if "fs" in r and not pd.isna(r["fs"]) else None,
              pairs, labels, cfg_dict) for _, r in manifest.iterrows()]

    print(f"Headband bipolar montage: {'  '.join(f'{a}-{b}' for a, b in pairs)} "
          f"(2 differential channels)")
    print(f"Manifest : {args.manifest}  ({len(wargs)} recordings)\n")

    t0 = time.time()
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_extract_one, wa) for wa in wargs]
        for i, fut in enumerate(as_completed(futures), 1):
            rows.extend(fut.result()[1])
            if i % 25 == 0:
                print(f"  ...{i}/{len(wargs)}", flush=True)
    ft = pd.DataFrame(rows)
    feat_cols = [c for c in ft.columns if c not in ("patient_id", "label", "t_end_sec")]
    print(f"Built {len(ft):,} windows / {ft['patient_id'].nunique()} patients, "
          f"{len(feat_cols)} features in {(time.time()-t0)/60:.1f} min\n")

    X = SimpleImputer(strategy="median").fit_transform(ft[feat_cols].astype(float).to_numpy())
    y = ft["label"].to_numpy(dtype=int)
    groups = ft["patient_id"].to_numpy()
    params = dict(objective="binary", is_unbalance=True, random_state=42,
                  n_jobs=-1, verbosity=-1)
    if args.fast:
        params.update(n_estimators=120, num_leaves=31)

    oof = np.full(len(y), np.nan)
    f1s, aucs = [], []
    for tr, te in GroupKFold(n_splits=args.folds).split(X, y, groups):
        clf = lgb.LGBMClassifier(**params).fit(X[tr], y[tr])
        p = clf.predict_proba(X[te])[:, 1]
        oof[te] = p
        f1s.append(f1_score(y[te], (p >= 0.5).astype(int), average="macro", zero_division=0))
        if len(np.unique(y[te])) > 1:
            aucs.append(roc_auc_score(y[te], p))
    full = {"macro_f1": float(np.mean(f1s)), "auc": float(np.mean(aucs))}
    print(f"Full-coverage (no abstention): macro-F1 {full['macro_f1']:.3f}  "
          f"AUC {full['auc']:.3f}\n")

    coverages = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
    rc = risk_coverage(y, oof, coverages)
    print("Selective prediction (abstain on low-confidence windows):")
    print(f"{'coverage':>8}  {'#win':>6}  {'macroF1':>7}  {'balAcc':>6}  {'AUC':>6}  {'pos%':>5}")
    print("-" * 52)
    for r in rc:
        print(f"{r['coverage']*100:6.0f}%  {r['n']:6d}  {r['macro_f1']:7.3f}  "
              f"{r['bal_acc']:6.3f}  {r['auc']:6.3f}  {r['pos_rate']*100:4.0f}%")
    print("-" * 52)

    out = {"manifest": str(Path(args.manifest).resolve()),
           "pairs": [f"{a}-{b}" for a, b in pairs], "n_features": len(feat_cols),
           "n_windows": int(len(ft)), "n_patients": int(ft["patient_id"].nunique()),
           "full_coverage": full, "risk_coverage": rc,
           "note": "2 bipolar differential channels from monopolar TUH (CAR cancels in "
                   "diff). Same-rig proxy (slow/bckg), directional. Confidence = |p-0.5|."}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
