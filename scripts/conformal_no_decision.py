"""R2 evaluation: does patient-level conformal No-Decision keep false alerts <= alpha?

Setting (the most honest one we have, see clinical_utility.py): the deployed Riemannian
model is trained on two sources and scored on two *unseen* sources, eye-state matched.
Patient score = mean window probability.

Conformal needs calibration patients exchangeable with the patients it decides on, so we
model on-site calibration: the unseen-source patients are split at random into a
calibration half and a test half (stratified), many times. Per alpha we report, on the
test halves:

* conformal (patient level): FAR, miss, No-Decision share per class, accuracy when decided;
* heuristic baseline: alert p >= 0.80 (deployed theta_high), clear p <= 0.20, else ND;
* window-level conformal with "alert if any window alerts" (what a naive streaming
  calibration does): FAR at patient level.

Pre-registered drop rule (docs/full_paper_plan.md, R2): if the mean empirical FAR exceeds
alpha by more than 0.02 in a split, report the rule as a heuristic, not a guarantee.

Usage::

    .venv/Scripts/python.exe scripts/conformal_no_decision.py            # fits models, caches probs
    .venv/Scripts/python.exe scripts/conformal_no_decision.py --reuse     # reuse cached probs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import conformal_triage as C  # noqa: E402

ALPHAS = (0.05, 0.10, 0.20)
HEURISTIC_ALERT, HEURISTIC_CLEAR = 0.80, 0.20
GUARANTEE_SLACK = 0.02


def window_probs(split: str, reuse: bool) -> pd.DataFrame:
    cache = ROOT / "results" / f"conformal_window_probs_{split}.csv"
    if reuse and cache.exists():
        return pd.read_csv(cache)
    from clinical_utility import SPLITS, _fit, patient_scores

    train, test = SPLITS[split]
    win = patient_scores(_fit(train), test)
    cache.parent.mkdir(parents=True, exist_ok=True)
    win.to_csv(cache, index=False)
    return win


def heuristic_states(p: np.ndarray) -> np.ndarray:
    return np.where(p >= HEURISTIC_ALERT, "alert", np.where(p <= HEURISTIC_CLEAR, "clear", "no_decision"))


def _summary(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    return {
        m: {"mean": float(df[m].mean()), "p05": float(df[m].quantile(0.05)), "p95": float(df[m].quantile(0.95))}
        for m in df.columns
    }


def _window_any_far(win_by_pid: dict, pids: tuple, y: np.ndarray, cal: np.ndarray, test: np.ndarray, alpha: float) -> float:
    """Naive streaming calibration: window-level thresholds, alert if any window alerts."""
    cal_w = [(win_by_pid[pids[i]], y[i]) for i in cal]
    thr = C.fit_thresholds(
        np.concatenate([w for w, _ in cal_w]),
        np.concatenate([np.full(w.size, lab) for w, lab in cal_w]),
        alpha_far=alpha, alpha_miss=alpha,
    )
    ctrl = [i for i in test if y[i] == 0]
    return float(np.mean([any(C.decide(v, thr).state == "alert" for v in win_by_pid[pids[i]]) for i in ctrl]))


def run_split(win: pd.DataFrame, n_rep: int, seed: int) -> dict:
    agg = C.aggregate_patients(win["pid"].to_numpy(), win["p"].to_numpy())
    y = win.groupby("pid", sort=False)["y"].first().reindex(list(agg.pids)).to_numpy()
    p = agg.scores
    win_by_pid = {pid: g["p"].to_numpy() for pid, g in win.groupby("pid")}
    out: dict = {"n_stroke": int(y.sum()), "n_control": int((y == 0).sum()), "alphas": {}}
    for alpha in ALPHAS:
        rng = np.random.default_rng(seed)
        conf_rows, heur_rows, window_far, never_alert = [], [], [], []
        for _ in range(n_rep):
            cal, test = C.stratified_half_split(y, rng)
            thr = C.fit_thresholds(p[cal], y[cal], alpha_far=alpha, alpha_miss=alpha)
            never_alert.append(not np.isfinite(thr.q_control))
            states = np.array([C.decide(v, thr).state for v in p[test]])
            conf_rows.append(C.decision_metrics(states, y[test]))
            heur_rows.append(C.decision_metrics(heuristic_states(p[test]), y[test]))
            window_far.append(_window_any_far(win_by_pid, agg.pids, y, cal, test, alpha))
        conf = _summary(conf_rows)
        out["alphas"][str(alpha)] = {
            "conformal": conf,
            "heuristic_0.8_0.2": _summary(heur_rows),
            "window_level_any_alert_far": _summary([{"far": f} for f in window_far])["far"],
            "share_reps_never_alert": float(np.mean(never_alert)),
            "guarantee_holds": bool(conf["far"]["mean"] <= alpha + GUARANTEE_SLACK),
        }
    return out


def _print(report: dict) -> None:
    for split, r in report["splits"].items():
        print(f"\n== {split}: {r['n_stroke']} stroke / {r['n_control']} control patients")
        for alpha, a in r["alphas"].items():
            c, h = a["conformal"], a["heuristic_0.8_0.2"]
            print(
                f"alpha={alpha}: conformal FAR {c['far']['mean']:.3f} miss {c['miss']['mean']:.3f} "
                f"ND ctrl/stroke {c['no_decision_control']['mean']:.2f}/{c['no_decision_stroke']['mean']:.2f} "
                f"sens {c['sensitivity']['mean']:.2f} | heuristic FAR {h['far']['mean']:.3f} "
                f"sens {h['sensitivity']['mean']:.2f} | window-any FAR {a['window_level_any_alert_far']['mean']:.3f} "
                f"| holds={a['guarantee_holds']}"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--splits", nargs="+", default=["S1", "S2"])
    ap.add_argument("--n-rep", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reuse", action="store_true", help="reuse cached window probabilities")
    ap.add_argument("--out", default=str(ROOT / "results" / "conformal_no_decision.json"))
    args = ap.parse_args()

    report = {
        "condition": "eye-state matched, unseen sources; on-site calibration by random patient halves",
        "n_rep": args.n_rep, "drop_rule": f"guarantee_holds iff mean FAR <= alpha + {GUARANTEE_SLACK}",
        "splits": {},
    }
    for split in args.splits:
        report["splits"][split] = run_split(window_probs(split, args.reuse), args.n_rep, args.seed)
        print(f"[{split}] done", flush=True)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print(report)


if __name__ == "__main__":
    main()
