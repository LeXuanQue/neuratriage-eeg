"""E11: does the patient-level conformal rule (R2) still hold behind the SQI v2 quality gate?

Same setting as conformal_no_decision.py (Riemannian model trained on two sources, scored on
two unseen eye-state-matched sources, on-site calibration by random patient halves), but a
4 s window only counts when SQI v2 scores it usable (window score >= CHANNEL_OK, frozen TUAR
drift threshold when results/sqi_v2_calibration.json exists). A patient without any usable
window gets No-Decision (reason ``quality``) and is left out of calibration, as at deployment.

Reported per split and alpha: FAR, miss and No-Decision shares on the test halves, how many
patients and windows the gate removes per class, and whether mean FAR <= alpha + 0.02.

Usage (after conformal_no_decision.py has cached the window probabilities)::

    .venv/Scripts/python.exe scripts/conformal_quality_gate.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import conformal_triage as C  # noqa: E402

ALPHAS = (0.05, 0.10, 0.20)
GUARANTEE_SLACK = 0.02
CAP_PER_PATIENT = 24  # same cap as the cached model windows (conformal_window_probs_*.csv)
SPLIT_SOURCES = {"S1": ("tianjin", "physionet_eo"), "S2": ("xuanwu", "physionet_eo")}

# Mains frequency of the country each cohort was recorded in. PhysioNet eegmmidb (US) shows a
# 60 Hz peak ~100x the background; the Chinese and Norwegian cohorts are 50 Hz.
LINE_FREQ = {
    "xuanwu": 50.0, "tianjin": 50.0, "oslo": 50.0, "oslo45": 50.0,
    "physionet": 60.0, "physionet_eo": 60.0, "physionet_ec": 60.0, "tuh": 60.0,
}


def line_freq_for(source: str) -> float:
    return LINE_FREQ[source]


def usable_windows(windows: np.ndarray, fs: float, line_freq: float, scorer=None) -> np.ndarray:
    """True where SQI v2 scores the whole window at or above CHANNEL_OK (``scorer``: learned channel score)."""
    import sqi_v2 as S
    from sqi_v2_gate_check import make_config

    cfg = make_config(line_freq)
    return np.array([S.assess_window(np.asarray(w, float), fs, config=cfg, scorer=scorer).score >= S.CHANNEL_OK
                     for w in windows], dtype=bool)


def _patients(win: pd.DataFrame, usable: np.ndarray) -> Tuple[C.PatientScores, np.ndarray]:
    agg = C.aggregate_patients(win["pid"].to_numpy(), win["p"].to_numpy(), valid=usable)
    y = win.groupby("pid", sort=False)["y"].first().reindex(list(agg.pids)).to_numpy()
    return agg, y


def gated_states_once(win: pd.DataFrame, usable: np.ndarray, alpha: float,
                      rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One calibration/test draw: (states, labels, fully-gated mask) on the test half."""
    agg, y = _patients(win, usable)
    return _decide_draw(agg.scores, y, alpha, rng)


def _decide_draw(p: np.ndarray, y: np.ndarray, alpha: float,
                 rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    cal, test = C.stratified_half_split(y, rng)
    thr = C.fit_thresholds(p[cal], y[cal], alpha_far=alpha, alpha_miss=alpha)  # ignores nan
    states = np.array([C.decide(v, thr).state for v in p[test]])
    return states, y[test], ~np.isfinite(p[test])


def _summary(rows: Sequence[dict]) -> dict:
    df = pd.DataFrame(list(rows))
    return {m: {"mean": float(df[m].mean()), "p05": float(df[m].quantile(0.05)),
                "p95": float(df[m].quantile(0.95))} for m in df.columns}


def run_gated_split(win: pd.DataFrame, usable: np.ndarray, n_rep: int, seed: int,
                    alphas: Sequence[float] = ALPHAS) -> dict:
    usable = np.asarray(usable, dtype=bool)
    agg, y = _patients(win, usable)
    gone = ~np.isfinite(agg.scores)
    yw = win["y"].to_numpy()
    out: dict = {
        "n_stroke": int(y.sum()), "n_control": int((y == 0).sum()),
        "usable_window_share": {"control": float(usable[yw == 0].mean()), "stroke": float(usable[yw == 1].mean())},
        "n_patients_without_usable_window": {"control": int((gone & (y == 0)).sum()),
                                             "stroke": int((gone & (y == 1)).sum())},
        "alphas": {},
    }
    for alpha in alphas:
        rng = np.random.default_rng(seed)
        rows = [C.decision_metrics(*_decide_draw(agg.scores, y, alpha, rng)[:2]) for _ in range(n_rep)]
        conf = _summary(rows)
        out["alphas"][str(alpha)] = {
            "conformal": conf,
            "guarantee_holds": bool(conf["far"]["mean"] <= alpha + GUARANTEE_SLACK),
        }
    return out


ALIGN_RTOL = 1e-3  # max |diff| relative to the window's peak, float32 round-off is ~1e-7


def align_windows(cached_pids: np.ndarray, cached: np.ndarray,
                  rebuilt_pids: np.ndarray, rebuilt: np.ndarray) -> np.ndarray:
    """Index of each cached window's twin among the rebuilt windows of the same patient, -1 if none.

    The rebuild reruns the window selection with today's code; a borderline v1 pre-gate decision
    can drop or add a window, so windows are matched by content, never by position."""
    cached_pids, rebuilt_pids = np.asarray(cached_pids).astype(str), np.asarray(rebuilt_pids).astype(str)
    out = np.full(len(cached), -1, dtype=int)
    for pid in np.unique(cached_pids):
        cand = np.flatnonzero(rebuilt_pids == pid)
        if cand.size == 0:
            continue
        for i in np.flatnonzero(cached_pids == pid):
            diff = np.abs(rebuilt[cand] - cached[i]).reshape(cand.size, -1).max(axis=1)
            k = int(np.argmin(diff))
            if diff[k] <= ALIGN_RTOL * max(float(np.abs(cached[i]).max()), 1e-6):
                out[i] = cand[k]
    return out


def split_usable(split: str, win: pd.DataFrame, workers: int, scorer=None) -> Tuple[np.ndarray, dict]:
    """SQI v2 usable mask for the cached window probabilities of one split (same order).

    The model's cached windows are band-passed and re-referenced; the deployed tracker scores
    the raw stream, so the gate runs on the unfiltered signal of the same windows. Cached
    windows without a rebuilt twin count as unusable (conservative) and are reported."""
    from leave_source_out import CACHE, _manifests, raw_source_windows

    manifests = _manifests(50)
    parts, unmatched = [], {}
    for source in SPLIT_SOURCES[split]:
        cached = np.load(CACHE / f"{source}_cap{CAP_PER_PATIENT}.npz", allow_pickle=True)
        rows = win[win["source"] == source]
        if not np.array_equal(rows["pid"].astype(str).to_numpy(), cached["pids"].astype(str)):
            raise SystemExit(f"{split}/{source}: cached probabilities and model windows are not aligned")
        z = raw_source_windows(source, manifests[source], CAP_PER_PATIENT, workers)
        idx = align_windows(cached["pids"], cached["windows"], z["pids"], z["windows"])
        ok = usable_windows(z["raw"], 256.0, line_freq_for(source), scorer)
        parts.append(np.where(idx >= 0, ok[np.maximum(idx, 0)], False))
        unmatched[source] = int((idx < 0).sum())
        print(f"[{split}] {source}: {parts[-1].mean():.1%} of {len(parts[-1])} windows usable, "
              f"{unmatched[source]} without a rebuilt twin", flush=True)
    return np.concatenate(parts), unmatched


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--splits", nargs="+", default=["S1", "S2"])
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", default=str(ROOT / "results" / "conformal_quality_gate.json"))
    args = ap.parse_args()

    from app.services.channel_quality import DEFAULT_SCORER, load_sqi_scorer

    calib = ROOT / "results" / "sqi_v2_calibration.json"
    scorer = load_sqi_scorer(DEFAULT_SCORER)  # the same channel score the live tracker uses
    report = {
        "condition": "as conformal_no_decision.py, windows kept only if SQI v2 on the raw signal >= CHANNEL_OK",
        "drift_ramp_source": str(calib) if calib.exists() else "default (synthetic)",
        "channel_scorer": str(DEFAULT_SCORER) if scorer is not None else "hand-set rules",
        "n_rep": args.n_rep, "drop_rule": f"guarantee_holds iff mean FAR <= alpha + {GUARANTEE_SLACK}",
        "splits": {},
    }
    for split in args.splits:
        win = pd.read_csv(ROOT / "results" / f"conformal_window_probs_{split}.csv")
        win = win.sort_values("source", key=lambda s: s.map(SPLIT_SOURCES[split].index), kind="stable")
        usable, unmatched = split_usable(split, win, args.workers, scorer)
        report["splits"][split] = run_gated_split(win.reset_index(drop=True), usable, args.n_rep, args.seed)
        report["splits"][split]["windows_without_rebuilt_twin"] = unmatched
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    for split, r in report["splits"].items():
        print(f"\n== {split}: usable windows {r['usable_window_share']}, "
              f"patients removed {r['n_patients_without_usable_window']}")
        for alpha, a in r["alphas"].items():
            c = a["conformal"]
            print(f"alpha={alpha}: FAR {c['far']['mean']:.3f} miss {c['miss']['mean']:.3f} "
                  f"ND ctrl/stroke {c['no_decision_control']['mean']:.2f}/{c['no_decision_stroke']['mean']:.2f} "
                  f"| holds={a['guarantee_holds']}")


if __name__ == "__main__":
    main()
