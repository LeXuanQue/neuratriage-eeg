"""E4: per-chunk processing latency of the live path, as deployed, on CPU.

Replays a real recording (dataset_ischemic/sub-01.npz, 18 channels, 256 Hz) in 0.5 s
chunks through exactly what the WebSocket handler does per chunk:

  map_to_pipeline -> RealTimeStrokeDetector.update (model from SessionManager, i.e. the
  deployed realtime model) -> ChannelQualityTracker.push (SQI v2 per channel)

plus the 2-channel tracker the headband uses. Network and browser time are excluded.
Real-time factor = p95 processing time / chunk duration (must be << 1).

Usage::

    .venv/Scripts/python.exe scripts/latency_bench.py
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

CHUNK_SEC = 0.5


def summarize_ms(samples_sec: Sequence[float]) -> dict:
    if len(samples_sec) == 0:
        return {"n": 0}
    ms = np.asarray(samples_sec, dtype=float) * 1000.0
    return {
        "n": int(ms.size),
        "mean_ms": float(ms.mean()),
        "p50_ms": float(np.percentile(ms, 50)),
        "p95_ms": float(np.percentile(ms, 95)),
        "p99_ms": float(np.percentile(ms, 99)),
        "max_ms": float(ms.max()),
    }


def realtime_factor(p95_ms: float, chunk_sec: float) -> float:
    return p95_ms / (chunk_sec * 1000.0)


def _timed(fn, *args):
    t0 = time.perf_counter()
    out = fn(*args)
    return out, time.perf_counter() - t0


def run(recording: Path, seconds: float) -> dict:
    from app.config import get_settings
    from app.services.channel_mapper import map_to_pipeline
    from app.services.channel_quality import ChannelQualityTracker
    from app.services.model_manager import get_manager
    from app.services.session_manager import get_session_manager
    from eeg_stroke_pipeline import DEFAULT_CHANNELS

    settings = get_settings()
    mgr = get_manager()
    if not mgr.is_loaded and not mgr.auto_load(settings.candidate_model_paths()):
        raise SystemExit("no model available to benchmark")

    d = np.load(recording)
    data, fs = d["data"].astype(float), float(d["fs"])
    channels = [str(c) for c in d["channels"]]
    n_chunk = int(round(CHUNK_SEC * fs))
    n_total = min(data.shape[1], int(seconds * fs))

    sm = get_session_manager()
    session_id = uuid.uuid4().hex
    detector = sm.create_session(session_id, channels, fs=fs)
    q18 = ChannelQualityTracker(channels, fs)
    q2 = ChannelQualityTracker(channels[:2], fs)

    t_map, t_det, t_det_event, t_q18, t_q2, t_total = [], [], [], [], [], []
    try:
        for k in range(0, n_total - n_chunk + 1, n_chunk):
            chunk = data[:, k : k + n_chunk]
            t0 = time.perf_counter()
            (mapped, _), dt_map = _timed(map_to_pipeline, chunk, channels, fs)
            events, dt_det = _timed(detector.update, mapped)
            msg18, dt_q18 = _timed(q18.push, chunk)
            t_total.append(time.perf_counter() - t0)
            msg2, dt_q2 = _timed(q2.push, chunk[:2])
            t_map.append(dt_map)
            t_det.append(dt_det)
            if events:
                t_det_event.append(dt_det)
            if msg18 is not None:
                t_q18.append(dt_q18)
            if msg2 is not None:
                t_q2.append(dt_q2)
    finally:
        sm.close_session(session_id)

    stages = {
        "map_to_pipeline": summarize_ms(t_map),
        "detector_update_all_chunks": summarize_ms(t_det),
        "detector_update_chunks_with_events": summarize_ms(t_det_event),
        "sqi_v2_18ch_when_scored": summarize_ms(t_q18),
        "sqi_v2_2ch_when_scored": summarize_ms(t_q2),
        "end_to_end_18ch_per_chunk": summarize_ms(t_total),
    }
    e2e = stages["end_to_end_18ch_per_chunk"]
    return {
        "recording": recording.name,
        "seconds": n_total / fs,
        "chunk_sec": CHUNK_SEC,
        "env": {
            "cpu": platform.processor(),
            "cpu_count": os.cpu_count(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "realtime_model": settings.realtime_model,
        },
        "stages": stages,
        "realtime_factor_p95": realtime_factor(e2e["p95_ms"], CHUNK_SEC) if e2e["n"] else None,
        "excluded": "WebSocket/network and browser rendering",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--recording", default=str(ROOT / "dataset_ischemic" / "sub-01.npz"))
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--out", default=str(ROOT / "results" / "latency.json"))
    args = ap.parse_args()
    report = run(Path(args.recording), args.seconds)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("env", "realtime_factor_p95")}, indent=2))
    for name, s in report["stages"].items():
        if s["n"]:
            print(f"{name:38s} n={s['n']:4d} mean {s['mean_ms']:7.2f}  p50 {s['p50_ms']:7.2f}  "
                  f"p95 {s['p95_ms']:7.2f}  max {s['max_ms']:7.2f} ms")


if __name__ == "__main__":
    main()
