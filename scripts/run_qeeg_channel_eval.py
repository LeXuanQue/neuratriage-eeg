"""Do qEEG band-power markers and/or per-channel MFDFA rescue a low-channel montage?

Rebuilds features NATIVELY from only the requested channels (native common-average
reference over the montage -- no 18-ch CAR approximation), for each window computing:

  * entropy family  -- ApEn / FuEn per channel + homologous asymmetry (reused from
    ``eeg_stroke_pipeline.extract_entropy_features``);
  * MFDFA family     -- multifractal spectrum summary computed PER CHANNEL (not the
    18-ch regional pooling of the main pipeline, which collapses at 4 channels),
    via ``eeg_stroke_pipeline.mfdfa_features`` on each channel signal;
  * qEEG family      -- classic stroke/ischemia band-power markers:
        DAR   = delta / alpha                              (per channel)
        DTABR = (delta + theta) / (alpha + beta)           (per channel)
        pdBSI = mean_band |R_b - L_b| / (R_b + L_b)         (per homologous pair)

Then compares feature families under the SAME patient-level GroupKFold
(``run_low_channel_ablation.run_cv``): entropy alone, qEEG alone, MFDFA alone, and
the combinations up to the full "old system per-channel + qEEG" stack. Answers
whether MFDFA / band-power markers add signal on a fixed few-channel headband.

Bands: delta 1-4, theta 4-8, alpha 8-13, beta 13-30 Hz. No SQI gating here -- every
window is kept so the family deltas are measured on identical rows. (SQI is a runtime
quality gate / No-Decision mechanism, not a pathology feature, so it is intentionally
excluded from the classifier here.)

Usage
-----
  .venv/Scripts/python.exe scripts/run_qeeg_channel_eval.py ^
      --manifest dataset_tuh/manifest_tuh.csv --channels T3,T4,O1,O2 --fast
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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

BANDS = {"delta": (1.0, 4.0), "theta": (4.0, 8.0),
         "alpha": (8.0, 13.0), "beta": (13.0, 30.0)}
_EPS = 1e-8


def qeeg_features(bp_window, channels, fs) -> dict:
    """DAR/DTABR per channel + pdBSI per homologous pair, from one band-power window."""
    import numpy as np
    from eeg_stroke_pipeline import HOMOLOGOUS_PAIRS, compute_welch_bandpower

    bpow = {b: compute_welch_bandpower(bp_window, fs, band) for b, band in BANDS.items()}
    feats: dict[str, float] = {}
    for i, ch in enumerate(channels):
        d, t, a, be = (bpow["delta"][i], bpow["theta"][i],
                       bpow["alpha"][i], bpow["beta"][i])
        feats[f"dar_{ch}"] = float(d / (a + _EPS))
        feats[f"dtabr_{ch}"] = float((d + t) / (a + be + _EPS))
    idx = {ch: i for i, ch in enumerate(channels)}
    for left, right in HOMOLOGOUS_PAIRS:
        if left in idx and right in idx:
            vals = [abs(bpow[b][idx[right]] - bpow[b][idx[left]])
                    / (bpow[b][idx[right]] + bpow[b][idx[left]] + _EPS) for b in BANDS]
            feats[f"pdbsi_{left}_{right}"] = float(np.mean(vals))
    return feats


def mfdfa_perch_features(mfdfa_window, channels, cfg) -> dict:
    """Per-channel multifractal spectrum summary (10 features/channel).

    Unlike the pipeline's region-pooled MFDFA (which needs several electrodes per
    region and mostly vanishes at 4 channels), this runs ``mfdfa_features`` on each
    channel signal directly, so every channel keeps its own multifractal descriptors.
    """
    import numpy as np
    from eeg_stroke_pipeline import mfdfa_features

    feats: dict[str, float] = {}
    min_finite = max(64, 4 * cfg.mfdfa_scale_min)
    for i, ch in enumerate(channels):
        sig = np.asarray(mfdfa_window[i], dtype=float)
        if int(np.sum(np.isfinite(sig))) < min_finite:
            continue
        try:
            summary = mfdfa_features(sig, q_values=cfg.mfdfa_q, order=cfg.mfdfa_order,
                                     scale_min=cfg.mfdfa_scale_min,
                                     scale_count=cfg.mfdfa_scale_count)
        except Exception:
            continue
        for key, value in summary.items():
            feats[f"mfdfa_{ch}_{key}"] = float(value)
    return feats


def _extract_one(args: tuple):
    """Worker: load one npz, rebuild entropy + MFDFA + qEEG rows for the subset channels."""
    import warnings
    warnings.filterwarnings("ignore")
    import sys as _sys
    _sys.path.insert(0, str(BACKEND))

    from eeg_stroke_pipeline import (
        PipelineConfig, extract_entropy_features, load_array_file, parse_label,
        preprocess_eeg, reorder_to_target_channels,
    )

    patient_id, label_raw, path_str, fs_manifest, channels, cfg_dict = args
    cfg = PipelineConfig(**cfg_dict)
    cfg.channels = list(channels)

    data, ch_names, fs_file = load_array_file(path_str)
    fs = float(fs_manifest) if fs_manifest is not None else (fs_file or cfg.fs)
    ordered = reorder_to_target_channels(data, ch_names, channels)
    x = preprocess_eeg(ordered, fs, cfg)
    label = parse_label(label_raw)

    entropy_len = int(round(cfg.entropy_window_sec * cfg.fs))
    bp_len = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step = int(round(cfg.entropy_step_sec * cfg.fs))
    min_len = max(entropy_len, bp_len)

    rows = []
    for end in range(min_len, x.shape[1] + 1, step):
        bpw = x[:, end - bp_len:end]
        ent = extract_entropy_features(x[:, end - entropy_len:end], channels, cfg)
        qee = qeeg_features(bpw, channels, cfg.fs)
        mfd = mfdfa_perch_features(bpw, channels, cfg)
        rows.append({**ent, **qee, **mfd, "patient_id": patient_id, "label": label,
                     "t_end_sec": end / cfg.fs})
    return patient_id, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest",
                        default=str(ROOT / "dataset_tuh" / "manifest_tuh.csv"))
    parser.add_argument("--channels", default="T3,T4,O1,O2")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out",
                        default=str(ROOT / "results" / "qeeg_channel_eval.json"))
    args = parser.parse_args()

    import pandas as pd
    from eeg_stroke_pipeline import PipelineConfig
    from run_low_channel_ablation import run_cv

    channels = [c.strip().upper() for c in args.channels.split(",") if c.strip()]
    cfg = PipelineConfig()
    cfg_dict = {k: (list(v) if isinstance(v, tuple) else v) for k, v in cfg.__dict__.items()}

    manifest = pd.read_csv(args.manifest)
    worker_args = [
        (str(r["patient_id"]), r["label"], str(r["path"]),
         float(r["fs"]) if "fs" in r and not pd.isna(r["fs"]) else None,
         channels, cfg_dict)
        for _, r in manifest.iterrows()
    ]

    print(f"Manifest : {args.manifest}  ({len(worker_args)} recordings)")
    print(f"Channels : {', '.join(channels)}   (native CAR over subset; no SQI gating)\n")

    t0 = time.time()
    all_rows: list[dict] = []
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_extract_one, wa) for wa in worker_args]
        for i, fut in enumerate(as_completed(futures), 1):
            _pid, rows = fut.result()
            all_rows.extend(rows)
            if i % 25 == 0:
                print(f"  ...{i}/{len(worker_args)} recordings", flush=True)
    ft = pd.DataFrame(all_rows)
    print(f"Built {len(ft):,} windows / {ft['patient_id'].nunique()} patients "
          f"in {(time.time()-t0)/60:.1f} min\n")

    ent_cols = [c for c in ft.columns if c.startswith(("apen_", "fuen_", "apfu_"))]
    qeeg_cols = [c for c in ft.columns if c.startswith(("dar_", "dtabr_", "pdbsi_"))]
    mfdfa_cols = [c for c in ft.columns if c.startswith("mfdfa_")]
    families = {
        "ENTROPY-only": ent_cols,
        "QEEG-only (DAR/DTABR/pdBSI)": qeeg_cols,
        "MFDFA-only (per-channel)": mfdfa_cols,
        "ENTROPY + QEEG": ent_cols + qeeg_cols,
        "ENTROPY + MFDFA(per-ch)": ent_cols + mfdfa_cols,
        "ENTROPY + MFDFA + QEEG (full)": ent_cols + mfdfa_cols + qeeg_cols,
    }

    print(f"{'feature family':32s}  {'#feat':>5}  {'macroF1':>7}  {'AUC':>6}  {'ptAUC':>6}")
    print("-" * 64)
    results = {}
    for name, cols in families.items():
        if not cols:
            continue
        res = run_cv(ft, cols, args.folds, args.fast)
        results[name] = {"n_features": len(cols),
                         "macro_f1": res["macro_f1"], "auc": res["auc"],
                         "pt_auc": res["pt_auc"]}
        print(f"{name:32s}  {len(cols):5d}  {res['macro_f1']:7.3f}  "
              f"{res['auc']:6.3f}  {res['pt_auc']:6.3f}")
    print("-" * 64)

    out = {"manifest": str(Path(args.manifest).resolve()), "channels": channels,
           "n_windows": int(len(ft)), "n_patients": int(ft["patient_id"].nunique()),
           "n_qeeg_features": len(qeeg_cols), "n_mfdfa_features": len(mfdfa_cols),
           "families": results,
           "note": "Native per-subset re-extraction (no 18-ch CAR approx, no SQI gating); "
                   "MFDFA computed per-channel."}
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
