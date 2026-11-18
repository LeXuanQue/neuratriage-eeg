"""E12: how many patients does on-site conformal calibration need?

Same setting as conformal_no_decision.py (deployed Riemannian model, unseen eye-state
matched sources; cached window probabilities). For each per-class calibration size n, we
draw n control + n stroke calibration patients at random, decide on the rest, and repeat.

Reported per (split, alpha, n):

* far_mean: mean false-alert rate over draws (the marginal guarantee: <= alpha);
* far_p90, p_far_exceeds: how much one site's realised FAR varies. A clinic calibrates
  once, so the share of draws with FAR > alpha + 0.05 is what that clinic risks;
* miss_mean, sensitivity, no-decision share per class, share of draws that can never alert.

Theory: below min_calibration_size(alpha) patients per class the threshold is infinite and
the system can never alert (alpha 0.1 -> 9, alpha 0.2 -> 4).

Usage::

    .venv/Scripts/python.exe scripts/conformal_calibration_size.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import conformal_triage as C  # noqa: E402
from conformal_no_decision import window_probs  # noqa: E402

ALPHAS = (0.10, 0.20)
SIZES = (4, 6, 9, 12, 15, 20)
EXCEED_MARGIN = 0.05


def curve(p: np.ndarray, y: np.ndarray, alpha: float, n: int, n_rep: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    rows, never = [], []
    for _ in range(n_rep):
        cal, test = C.sized_split(y, n_control=n, n_stroke=n, rng=rng)
        thr = C.fit_thresholds(p[cal], y[cal], alpha_far=alpha, alpha_miss=alpha)
        never.append(not np.isfinite(thr.q_control))
        states = np.array([C.decide(v, thr).state for v in p[test]])
        rows.append(C.decision_metrics(states, y[test]))
    far = np.array([r["far"] for r in rows])
    mean = lambda k: float(np.nanmean([r[k] for r in rows]))  # noqa: E731
    return {
        "far_mean": float(far.mean()),
        "far_p90": float(np.quantile(far, 0.9)),
        "p_far_exceeds": float(np.mean(far > alpha + EXCEED_MARGIN)),
        "miss_mean": mean("miss"),
        "sensitivity": mean("sensitivity"),
        "nd_control": mean("no_decision_control"),
        "nd_stroke": mean("no_decision_stroke"),
        "never_alert": float(np.mean(never)),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--splits", nargs="+", default=["S1", "S2"])
    ap.add_argument("--n-rep", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "results" / "conformal_calibration_size.json"))
    args = ap.parse_args()

    report: dict = {
        "condition": "eye-state matched, unseen sources; n control + n stroke calibration patients",
        "n_rep": args.n_rep,
        "exceed_margin": EXCEED_MARGIN,
        "min_calibration_size": {str(a): C.min_calibration_size(a) for a in ALPHAS},
        "splits": {},
    }
    for split in args.splits:
        win = window_probs(split, reuse=True)
        agg = C.aggregate_patients(win["pid"].to_numpy(), win["p"].to_numpy())
        y = win.groupby("pid", sort=False)["y"].first().reindex(list(agg.pids)).to_numpy()
        max_n = min((y == 0).sum(), (y == 1).sum()) - 1
        report["splits"][split] = {
            str(a): {str(n): curve(agg.scores, y, a, n, args.n_rep, args.seed) for n in SIZES if n <= max_n}
            for a in ALPHAS
        }
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")

    for split, by_alpha in report["splits"].items():
        for a, by_n in by_alpha.items():
            print(f"\n== {split} alpha={a} (min n = {report['min_calibration_size'][a]})")
            print("  n  FAR_mean  FAR_p90  P(FAR>a+.05)  miss  sens  ND_ctrl  ND_stroke  never_alert")
            for n, r in by_n.items():
                print(
                    f"{int(n):3d}  {r['far_mean']:.3f}    {r['far_p90']:.3f}    {r['p_far_exceeds']:.2f}        "
                    f"{r['miss_mean']:.3f} {r['sensitivity']:.2f}  {r['nd_control']:.2f}     {r['nd_stroke']:.2f}       "
                    f"{r['never_alert']:.2f}"
                )


if __name__ == "__main__":
    main()
