"""
Build feature table for all patients in a manifest (parallel workers).

Workers load their own .npz files to avoid large IPC transfers on Windows.

Output:
  dataset_real/feature_table_ischemic.csv
  dataset_healthy/feature_table_healthy.csv  (after PhysioNet download)

Usage:
  .venv/Scripts/python.exe build_feature_table.py
  .venv/Scripts/python.exe build_feature_table.py ^
      --manifest dataset_healthy/manifest_healthy.csv ^
      --out dataset_healthy/feature_table_healthy.csv ^
      --workers 8
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
_BACKEND = str(ROOT / "backend")


# ── Top-level worker — only small picklable args, worker loads its own file ──

def _process_row(args: tuple) -> tuple[str, list[dict]]:
    """Load one .npz, extract all feature windows, return (patient_id, rows)."""
    import warnings
    warnings.filterwarnings("ignore")
    import sys
    sys.path.insert(0, _BACKEND)

    from eeg_stroke_pipeline import (
        PipelineConfig,
        build_feature_row_from_windows,
        load_array_file,
        parse_label,
        reorder_to_target_channels,
        preprocess_eeg,
        preprocess_eeg_for_sqi,
    )

    patient_id, label_raw, path_str, fs_manifest, cfg_dict = args
    cfg = PipelineConfig(**cfg_dict)

    data, channels, fs_file = load_array_file(path_str)
    fs = float(fs_manifest) if fs_manifest is not None else (fs_file or cfg.fs)
    ordered = reorder_to_target_channels(data, channels, cfg.channels)
    label = parse_label(label_raw)

    entropy_len = int(round(cfg.entropy_window_sec * cfg.fs))
    mfdfa_len   = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step_len    = int(round(cfg.entropy_step_sec * cfg.fs))
    min_len     = max(entropy_len, mfdfa_len)

    x     = preprocess_eeg(ordered, fs, cfg)
    x_sqi = preprocess_eeg_for_sqi(ordered, fs, cfg)
    rows: list[dict] = []

    for end in range(min_len, x.shape[1] + 1, step_len):
        feat = build_feature_row_from_windows(
            entropy_window=x[:, end - entropy_len : end],
            mfdfa_window=x[:, end - mfdfa_len : end],
            channels=list(cfg.channels),
            fs=cfg.fs,
            config=cfg,
            sqi_window=x_sqi[:, end - entropy_len : end],
        )
        if cfg.drop_low_sqi_windows and feat["sqi_total"] < cfg.sqi_threshold:
            continue
        feat["patient_id"] = patient_id
        feat["label"] = label
        feat["t_end_sec"] = end / cfg.fs
        rows.append(feat)

    return patient_id, rows


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest",
                        default=str(ROOT / "dataset_real" / "manifest_ischemic.csv"))
    parser.add_argument("--out",
                        default=str(ROOT / "dataset_real" / "feature_table_ischemic.csv"))
    parser.add_argument("--workers", type=int,
                        default=min(8, max(1, os.cpu_count() - 2)),
                        help="Parallel workers (default: min(8, cpu_count-2))")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, _BACKEND)
    import pandas as pd
    from eeg_stroke_pipeline import PipelineConfig, ALL_FEATURES

    cfg = PipelineConfig()
    cfg_dict = {k: (list(v) if isinstance(v, tuple) else v)
                for k, v in cfg.__dict__.items()}

    manifest = pd.read_csv(manifest_path)
    n = len(manifest)
    eta_guess = n // args.workers * 8

    print(f"Manifest : {manifest_path}  ({n} patients)")
    print(f"Output   : {out_path}")
    print(f"Workers  : {args.workers}  (ETA ~{eta_guess} min)")
    print()

    worker_args = [
        (
            str(row["patient_id"]),
            row["label"],
            str(row["path"]),
            float(row["fs"]) if "fs" in row and not pd.isna(row["fs"]) else None,
            cfg_dict,
        )
        for _, row in manifest.iterrows()
    ]

    t_start = time.time()
    all_rows: list[dict] = []

    if args.workers <= 1:
        for i, wargs in enumerate(worker_args):
            t0 = time.time()
            print(f"  [{i+1:3d}/{n}] {wargs[0]}", end="", flush=True)
            pid, rows = _process_row(wargs)
            done = i + 1
            eta = (time.time() - t_start) / done * (n - done) / 60
            print(f"  windows={len(rows)}  [{time.time()-t0:.0f}s | ETA {eta:.0f}min]")
            all_rows.extend(rows)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_process_row, wa): wa[0] for wa in worker_args}
            done = 0
            for future in as_completed(futures):
                pid, rows = future.result()
                all_rows.extend(rows)
                done += 1
                eta = (time.time() - t_start) / done * (n - done) / 60
                print(f"  [{done:3d}/{n}] {pid}  windows={len(rows)}"
                      f"  [ETA {eta:.0f}min]", flush=True)

    if not all_rows:
        raise RuntimeError("No windows produced — check SQI threshold and signal lengths.")

    frame = pd.DataFrame(all_rows)
    cols = ["patient_id", "label", "t_end_sec"] + list(ALL_FEATURES)
    frame = frame[cols]
    frame.to_csv(out_path, index=False)

    total_min = (time.time() - t_start) / 60
    print(f"\nDone: {len(frame):,} windows  |  {frame.shape[1]} cols")
    print(f"Time : {total_min:.1f} min")
    print(f"Saved -> {out_path}")


if __name__ == "__main__":
    main()
