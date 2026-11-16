"""E5: SQI v1 vs SQI v2 on a real Brain-Life Focus+ recording (data/ble_signals_log.csv).

The log was captured with the headband on a person (raw ADC counts, 256 Hz, AF3/AF4).
docs/full_paper_plan.md notes that its spectrum was 94-98% delta with no alpha, a sign of
poor contact/drift, while the deployed SQI v1 still scored it about 0.88 (usable). This
script replays the log through both quality paths exactly as the live app does:

* v1: DeviceSqiMonitor (1 s windows, preprocess_eeg_for_sqi + compute_sqi, gate 0.55);
* v2: ChannelQualityTracker (4 s per-channel SQI v2 + guidance, ~1 Hz), using the frozen
  TUAR drift ramp if results/sqi_v2_calibration.json exists, else the synthetic default.

Usage::

    .venv/Scripts/python.exe scripts/headband_case_study.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

FS = 256.0
CHUNK = 128


def parse_log(raw_hex_rows: Iterable[Optional[str]]) -> Dict[str, np.ndarray]:
    """Per-channel samples from the 'Raw Signal(Hex)' column, in arrival order."""
    from app.services.device_source import BrainLifeAsciiDecoder

    dec = BrainLifeAsciiDecoder()
    by_header: Dict[int, list] = {h: [] for h, _ in dec.eeg_headers}
    for row in raw_hex_rows:
        if not isinstance(row, str) or not row.strip():
            continue
        try:
            raw = bytes.fromhex(row.strip())
        except ValueError:
            continue
        for header, values in dec.parse(raw).items():
            by_header[header].extend(values)
    return {label: np.asarray(by_header[h], dtype=float) for h, label in dec.eeg_headers}


def aligned(channels: Dict[str, np.ndarray]) -> np.ndarray:
    """Stack channels as (2, n), truncated to the shorter one (AF3/AF4 arrive separately)."""
    n = min(len(v) for v in channels.values())
    return np.stack([v[:n] for v in channels.values()])


def run(log_path: Path) -> dict:
    import pandas as pd

    from app.services.channel_quality import ChannelQualityTracker, load_sqi_config
    from app.services.device_stream import DeviceSqiMonitor
    from eeg_stroke_pipeline import PipelineConfig

    df = pd.read_csv(log_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    channels = parse_log(df["Raw Signal(Hex)"])
    x = aligned(channels)
    cfg = PipelineConfig()
    v1 = DeviceSqiMonitor(2, FS, cfg)
    v2_cfg = load_sqi_config(line_freq=50.0)
    v2 = ChannelQualityTracker(list(channels), FS, config=v2_cfg)

    v1_scores, v2_msgs = [], []
    for k in range(0, x.shape[1] - CHUNK + 1, CHUNK):
        chunk = x[:, k : k + CHUNK]
        s1 = v1.push(chunk)
        if s1 is not None:
            v1_scores.append(float(s1["sqi_total"]))
        m2 = v2.push(chunk)
        if m2 is not None:
            v2_msgs.append(m2)

    import sqi_v2

    spectral = {}
    if x.shape[1] >= 4 * FS:
        win = x[:, -int(4 * FS):]
        for i, name in enumerate(channels):
            f = sqi_v2.channel_features(win[i], FS, v2_cfg)
            spectral[name] = {k: round(float(f[k]), 3) for k in ("delta_ratio", "alpha_peak", "drift_excess", "drift_ratio", "hf_ratio")}

    gate = float(cfg.sqi_threshold)
    reasons: Dict[str, int] = {}
    for m in v2_msgs:
        for c in m["channels"]:
            for r in c["reasons"]:
                reasons[r] = reasons.get(r, 0) + 1
    tips = [m["guidance"] for m in v2_msgs if m["guidance"]]
    return {
        "log": log_path.name,
        "n_samples": int(x.shape[1]),
        "seconds": float(x.shape[1] / FS),
        "v2_drift_ramp": list(v2_cfg.drift_ramp),
        "v1": {
            "n_windows": len(v1_scores),
            "sqi_mean": float(np.mean(v1_scores)) if v1_scores else None,
            "share_passing_gate": float(np.mean(np.array(v1_scores) >= gate)) if v1_scores else None,
        },
        "v2": {
            "n_windows": len(v2_msgs),
            "score_mean": float(np.mean([m["score"] for m in v2_msgs])) if v2_msgs else None,
            "share_channels_usable": float(np.mean([c["score"] >= sqi_v2.CHANNEL_OK for m in v2_msgs for c in m["channels"]]))
            if v2_msgs else None,
            "reason_counts": reasons,
            "first_tip": tips[0] if tips else None,
            "timeline": [
                {"t": m["timestamp_sec"], "channels": [{k: c[k] for k in ("name", "score", "reasons")} for c in m["channels"]]}
                for m in v2_msgs
            ],
        },
        "spectral_last_4s": spectral,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--log", default=str(ROOT / "data" / "ble_signals_log.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "headband_case_study.json"))
    args = ap.parse_args()
    report = run(Path(args.log))
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
