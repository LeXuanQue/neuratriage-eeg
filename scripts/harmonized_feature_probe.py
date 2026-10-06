"""Acquisition-chain harmonization: recompute features under a common filter chain.

Spectral audit (2026-10-06) showed the clinical ischemic recordings were
low-pass filtered upstream (~35-40 Hz; -31 dB at 50 Hz vs alpha) while the
PhysioNet and TUH recordings were not (-11/-12 dB). Their low-frequency drift
also differs (0.5-1 Hz). Harmonization passes every source through the
narrowest band that all sources genuinely contain, so features cannot encode
which filter chain a recording went through. The filter is causal IIR, so the
same chain runs in the real-time path.

Each variant re-extracts features for a fixed, evenly spaced subset of windows
per recording (identical SQI gate across variants -> identical windows), then
scores them with the device-invariance probes.

Usage:
  .venv/Scripts/python.exe scripts/harmonized_feature_probe.py [--cap 12] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
_BACKEND = str(ROOT / "backend")
sys.path.insert(0, _BACKEND)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from eeg_stroke_pipeline import PipelineConfig  # noqa: E402

RESULTS_DIR = ROOT / "results" / "harmonized"

# (low Hz, high Hz, Butterworth order). The deployed order-4 filter is only ~9 dB down
# at 45 Hz, so the 35-45 Hz band where the sources differ leaks through; harmonized
# variants use order 8 to actually remove it.
VARIANTS: dict[str, tuple[float, float, int, str | None]] = {
    "baseline": (1.0, 35.0, 4, None),            # current pipeline
    "harm_1_30": (1.0, 30.0, 8, None),           # cut below the clinical low-pass roll-off
    "harm_2_30": (2.0, 30.0, 8, None),           # also cut the differing slow drift
    # Spectral whitening uses the whole recording's PSD (non-causal): an upper bound.
    "ccsw_1_30": (1.0, 30.0, 8, "common"),       # channel-common whitening (cancels shared H(f))
    "pcw_1_30": (1.0, 30.0, 8, "per_channel"),   # control: per-channel whitening
}


def variant_config(name: str) -> PipelineConfig:
    low, high, order, _ = VARIANTS[name]
    return replace(PipelineConfig(), bandpass_low=low, bandpass_high=high, bandpass_order=order)


def whiten_common_spectrum(x: np.ndarray, fs: float, band: tuple[float, float] = (1.0, 30.0),
                           nperseg: int = 256, per_channel: bool = False, reg: float = 1e-3) -> np.ndarray:
    """Divide every channel's spectrum by the recording's channel-median spectrum.

    A device acts as one transfer function H(f) on all channels, so it scales the
    channel-median PSD by |H|^2 too and cancels out; focal (channel-specific)
    spectral differences survive. `per_channel=True` whitens each channel by its
    own PSD instead (control: also erases focal slowing). Zero gain outside `band`.
    """
    from scipy.signal import welch

    x = np.asarray(x, dtype=float)
    n = x.shape[1]
    f, p = welch(x, fs=fs, nperseg=min(nperseg, n), axis=1)
    ref = p if per_channel else np.median(p, axis=0, keepdims=True)
    inband = (f >= band[0]) & (f <= band[1])
    ref = ref + reg * ref[:, inband].max(axis=1, keepdims=True)
    gain = np.where(inband, 1.0 / np.sqrt(ref), 0.0)
    gain /= np.sqrt(np.mean(gain[:, inband] ** 2, axis=1, keepdims=True))
    fb = np.fft.rfftfreq(n, 1.0 / fs)
    g = np.vstack([np.interp(fb, f, row) for row in gain])
    out = np.fft.irfft(np.fft.rfft(x, axis=1) * g, n=n, axis=1)
    # One scalar for all channels: removes the device's overall gain, keeps
    # relative channel amplitudes (part of the focal signal).
    return out / (np.std(out) + 1e-12)


def select_window_ends(n_samples: int, min_len: int, step: int, cap: int) -> list[int]:
    """Up to `cap` window end indices, evenly spread over the recording, on the hop grid."""
    grid = list(range(min_len, n_samples + 1, step))
    if len(grid) <= cap:
        return grid
    idx = np.unique(np.round(np.linspace(0, len(grid) - 1, cap)).astype(int))
    return [grid[i] for i in idx]


def _features_for_recording(args: tuple) -> list[dict]:
    import warnings as _w
    _w.filterwarnings("ignore")
    sys.path.insert(0, _BACKEND)
    from eeg_stroke_pipeline import (
        build_feature_row_from_windows, load_array_file, parse_label,
        preprocess_eeg, preprocess_eeg_for_sqi, reorder_to_target_channels,
    )

    patient_id, label_raw, path, fs_manifest, variant, cap = args
    cfg = variant_config(variant)
    data, channels, fs_file = load_array_file(path)
    fs = float(fs_manifest) if fs_manifest == fs_manifest else (fs_file or cfg.fs)
    x_raw = reorder_to_target_channels(data, channels, cfg.channels)
    x = preprocess_eeg(x_raw, fs, cfg)
    transform = VARIANTS[variant][3]
    if transform is not None:
        x = whiten_common_spectrum(x, cfg.fs, band=(cfg.bandpass_low, cfg.bandpass_high),
                                   per_channel=(transform == "per_channel"))
    x_sqi = preprocess_eeg_for_sqi(x_raw, fs, cfg)
    e_len = int(round(cfg.entropy_window_sec * cfg.fs))
    m_len = int(round(cfg.mfdfa_window_sec * cfg.fs))
    step = int(round(cfg.entropy_step_sec * cfg.fs))
    rows = []
    for end in select_window_ends(x.shape[1], max(e_len, m_len), step, cap):
        feat = build_feature_row_from_windows(
            entropy_window=x[:, end - e_len:end], mfdfa_window=x[:, end - m_len:end],
            channels=list(cfg.channels), fs=cfg.fs, config=cfg, sqi_window=x_sqi[:, end - e_len:end])
        if feat["sqi_total"] < cfg.sqi_threshold:
            continue
        feat.update(patient_id=patient_id, label=parse_label(label_raw), t_end_sec=end / cfg.fs)
        rows.append(feat)
    return rows


def _manifests(n_ns: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    ischemic = pd.read_csv(ROOT / "dataset_ischemic" / "manifest_ischemic.csv")
    healthy = pd.read_csv(ROOT / "dataset_healthy" / "manifest_healthy.csv").head(n_ns)
    tuh = pd.read_csv(ROOT / "dataset_tuh" / "manifest_tuh.csv")
    tuh["path"] = tuh["path"].map(lambda p: str(ROOT / p) if not Path(p).is_absolute() else p)
    return pd.concat([ischemic, healthy], ignore_index=True), tuh


def build_variant_tables(variant: str, cap: int, workers: int, n_ns: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = []
    for manifest in _manifests(n_ns):
        jobs = [(r.patient_id, r.label, r.path, r.fs, variant, cap) for r in manifest.itertuples()]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            rows = [row for chunk in pool.map(_features_for_recording, jobs) for row in chunk]
        out.append(pd.DataFrame(rows))
    return out[0], out[1]


def main() -> None:
    import device_invariance_probe as dip

    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=12, help="windows per recording")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--n-ns", type=int, default=50, help="PhysioNet subjects (50 = original cohort)")
    ap.add_argument("--variants", default=",".join(VARIANTS))
    args = ap.parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    summary = {}
    for variant in args.variants.split(","):
        cross_csv = RESULTS_DIR / f"cross_{variant}_cap{args.cap}.csv"
        tuh_csv = RESULTS_DIR / f"tuh_{variant}_cap{args.cap}.csv"
        if cross_csv.exists() and tuh_csv.exists():
            cross, tuh = pd.read_csv(cross_csv), pd.read_csv(tuh_csv)
        else:
            cross, tuh = build_variant_tables(variant, args.cap, args.workers, args.n_ns)
            cross.to_csv(cross_csv, index=False)
            tuh.to_csv(tuh_csv, index=False)
        cross, contrast = dip.add_mfdfa_contrasts(cross)
        tuh, _ = dip.add_mfdfa_contrasts(tuh)
        probes = dip.build_probe_frames(cross, tuh)
        base = [c for c in cross.columns if c not in dip.META and c not in contrast]
        sqi = [c for c in base if c.startswith("sqi_")]
        no_sqi = [c for c in base if c not in sqi]
        summary[variant] = {
            "windows": {"cross": len(cross), "tuh": len(tuh)},
            "NO_SQI": dip.evaluate_candidate(probes, no_sqi, fast=True),
            "NO_SQI+contrasts": dip.evaluate_candidate(probes, no_sqi + contrast, fast=True),
        }
        print(f"[{variant}] windows cross={len(cross)} tuh={len(tuh)}", flush=True)

    print(f"\n{'variant':10s} {'features':18s} {'devAUC_norm':>11s} {'devAUC_patho':>12s} {'pathoAUC_rig':>12s} {'crossAUC':>9s}")
    for variant, res in summary.items():
        for fs_name in ("NO_SQI", "NO_SQI+contrasts"):
            r = res[fs_name]
            print(f"{variant:10s} {fs_name:18s} {r['device_auc_normal']:11.3f} {r['device_auc_patho']:12.3f} "
                  f"{r['patho_auc_samerig']:12.3f} {r['crosscohort_auc']:9.3f}")
    (RESULTS_DIR / f"summary_cap{args.cap}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
