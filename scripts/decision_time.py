"""E13: how long must the operator record before the system can decide?

Each held-out recording is streamed through the deployed real-time detector (Riemannian
window model, SQI gate, 0.5 s chunks), exactly like clinical_utility.stream. For a horizon
T the patient score is the mean P(stroke) over the scored (non-No-Decision) events in the
first T seconds. Per T we report the patient AUC and the conformal No-Decision outcome
(random calibration/test patient halves, as in conformal_no_decision.py).

Only split S2 (train tianjin + oslo45 -> test xuanwu + physionet_eo): the tianjin rests in
S1 are 8.6 s fragments, too short to stream (same reason as clinical_utility.py).

Usage::

    .venv/Scripts/python.exe scripts/decision_time.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import conformal_triage as C  # noqa: E402

HORIZONS = (8.0, 15.0, 30.0, 45.0, 60.0, 90.0, 120.0)
ALPHAS = (0.10, 0.20)
CHUNK = 128  # 0.5 s at 256 Hz, as in the app

Trace = Tuple[np.ndarray, np.ndarray]  # (event times in s, P(stroke) or nan for no-decision)


def score_up_to(times: np.ndarray, probs: np.ndarray, horizon: float) -> float:
    """Mean P(stroke) over scored events within the first ``horizon`` seconds (nan if none)."""
    m = (np.asarray(times) <= horizon) & np.isfinite(probs)
    return float(np.mean(np.asarray(probs)[m])) if m.any() else float("nan")


def patient_scores_at(traces: Dict[str, Trace], pids: Sequence[str], horizon: float) -> np.ndarray:
    return np.array([score_up_to(*traces[p], horizon) for p in pids])


def stream_trace(model, x: np.ndarray, max_sec: float) -> Trace:
    """Event times and P(stroke) of the deployed detector over the first max_sec seconds."""
    from eeg_stroke_pipeline import PipelineConfig, RealTimeStrokeDetector

    det = RealTimeStrokeDetector(None, config=PipelineConfig(), window_model=model)
    times, probs = [], []
    for i in range(0, min(x.shape[1], int(max_sec * 256)), CHUNK):
        for e in det.update(x[:, i : i + CHUNK]):
            times.append(float(e["timestamp_sec"]))
            raw = e.get("probabilities_raw")
            probs.append(float(raw[1]) if e.get("status") != "no-decision" and raw is not None else float("nan"))
    return np.array(times), np.array(probs)


def conformal_at(p: np.ndarray, y: np.ndarray, alpha: float, n_rep: int, seed: int) -> dict:
    """Conformal outcome on random halves; patients without a score count as No-Decision."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_rep):
        cal, test = C.stratified_half_split(y, rng)
        ok = np.isfinite(p[cal])
        if (y[cal][ok] == 0).sum() == 0 or (y[cal][ok] == 1).sum() == 0:
            continue
        thr = C.fit_thresholds(p[cal][ok], y[cal][ok], alpha_far=alpha, alpha_miss=alpha)
        states = np.array([C.decide(v, thr).state for v in p[test]])
        rows.append(C.decision_metrics(states, y[test]))
    keys = ("far", "miss", "sensitivity", "no_decision_control", "no_decision_stroke")
    return {k: float(np.nanmean([r[k] for r in rows])) for k in keys} | {"n_rep_used": len(rows)}


def main() -> None:
    from sklearn.metrics import roc_auc_score

    from clinical_utility import SPLITS, _fit, _recordings

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n-rep", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "results" / "decision_time.json"))
    args = ap.parse_args()

    train, test = SPLITS["S2"]
    model = _fit(train)
    traces: Dict[str, Trace] = {}
    labels: Dict[str, int] = {}
    lengths = []
    for source in test:
        y = 0 if source.startswith("physionet") else 1
        for pid, x in _recordings(source):
            traces[pid] = stream_trace(model, x, max(HORIZONS))
            labels[pid] = y
            lengths.append(x.shape[1] / 256.0)
        print(f"[stream] {source}: {sum(1 for v in labels.values() if v == y)} recordings", flush=True)

    pids = list(traces)
    y = np.array([labels[p] for p in pids])
    report: dict = {
        "split": "S2", "train": train, "test": test,
        "n_stroke": int(y.sum()), "n_control": int((y == 0).sum()),
        "recording_sec_median": float(np.median(lengths)), "recording_sec_min": float(np.min(lengths)),
        "horizons": {},
    }
    for h in HORIZONS:
        p = patient_scores_at(traces, pids, h)
        ok = np.isfinite(p)
        auc = float(roc_auc_score(y[ok], p[ok])) if np.unique(y[ok]).size == 2 else float("nan")
        report["horizons"][str(h)] = {
            "auc": auc,
            "n_scored_stroke": int((ok & (y == 1)).sum()),
            "n_scored_control": int((ok & (y == 0)).sum()),
            **{f"alpha_{a}": conformal_at(p, y, a, args.n_rep, args.seed) for a in ALPHAS},
        }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nS2: {report['n_stroke']} stroke / {report['n_control']} control, "
          f"median recording {report['recording_sec_median']:.0f} s (min {report['recording_sec_min']:.0f} s)")
    print("   T    AUC   scored IS/NS | a=0.1 FAR sens ND_IS | a=0.2 FAR sens ND_IS")
    for h, r in report["horizons"].items():
        a1, a2 = r["alpha_0.1"], r["alpha_0.2"]
        print(f"{float(h):5.0f}  {r['auc']:.3f}   {r['n_scored_stroke']:3d}/{r['n_scored_control']:3d}    | "
              f"{a1['far']:.3f} {a1['sensitivity']:.2f} {a1['no_decision_stroke']:.2f} | "
              f"{a2['far']:.3f} {a2['sensitivity']:.2f} {a2['no_decision_stroke']:.2f}")


if __name__ == "__main__":
    main()
