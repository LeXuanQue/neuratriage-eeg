"""One-shot test-half evaluation of the advisory ``eye`` reason (plan: docs/paper_outline.md s.7).

The rule (delta_ratio >= 0.857 and alpha_peak <= -0.104, weight 0) was fixed on the TUAR
calibration half. This script runs it once on the test half and on the E9 cohorts and applies
the four criteria committed in 1d03614 before any test number was seen:

(a) eye-movement channel-windows get a correct reason more often than without ``eye``;
(b) ``eye`` fires on <= 7% of clean test channel-windows;
(c) E7 (correct type among channel-windows with a reason) drops by at most 2 points from 0.71;
(d) ``eye`` does not fire more on stroke (IS) than control (NS) channel-windows, nor more on
    TUSL slowing than background.

Usage::

    .venv/Scripts/python.exe scripts/eye_reason_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

E7_BEFORE = 0.7134649803716046  # results/tuar_sqi_eval.json, reason_accuracy_e7 (2026-11-17)
MAX_CLEAN_RATE = 0.07
MAX_E7_DROP = 0.02


def eye_fires(df) -> np.ndarray:
    """Where the eye rule holds, whatever other reasons rank first (NaN never fires)."""
    import sqi_v2

    cfg = sqi_v2.SqiV2Config()
    d, a = df["delta_ratio"].to_numpy(float), df["alpha_peak"].to_numpy(float)
    with np.errstate(invalid="ignore"):
        return (d >= cfg.eye_delta_min) & (a <= cfg.eye_alpha_max)


def verdict(m: Mapping) -> dict:
    share = m["eye_share"]
    criteria = {
        "a_eyem_improves": bool(m["eyem_correct_after"] > m["eyem_correct_before"]),
        "b_clean_rate_le_7pct": bool(m["clean_eye_rate"] <= MAX_CLEAN_RATE),
        "c_e7_not_down_2pts": bool(m["e7_correct_among_flagged"] >= E7_BEFORE - MAX_E7_DROP),
        "d_is_le_ns": bool(share["IS"] <= share["NS"]),
        "d_slow_le_bckg": bool(share["TUSL_slow"] <= share["TUSL_bckg"]),
    }
    return {"criteria": criteria, "ship": all(criteria.values())}


def _test_half_metrics() -> dict:
    import pandas as pd
    import sqi_v2
    import tuar_sqi_eval as T

    df = pd.read_csv(ROOT / "results" / "tuar_sqi_features.csv")
    df["kind"] = df["kind"].fillna("")
    df = df[df["label"] >= 0]
    _, test_pids = T.split_patients(df["pid"].unique())
    test = df[df["pid"].isin(test_pids)].reset_index(drop=True)
    ramp = json.loads((ROOT / "results" / "sqi_v2_calibration.json").read_text(encoding="utf-8"))["drift_ramp"]
    base = {"drift_ramp": ramp, "line_freq": T.TUH_LINE_FREQ}
    art = test[test["label"] == 1]
    _, why_on = T.rescore_with_reasons(art, sqi_v2.config_from_dict(base))
    _, why_off = T.rescore_with_reasons(art, sqi_v2.config_from_dict({**base, "eye_delta_min": 2.0}))
    eyem = (art["kind"] == "eyem").to_numpy()
    ok = T.expected_reasons("eyem")
    clean = test[(test["label"] == 0) & (test["v2_flat"] == 0)]
    accuracy = T.reason_accuracy(art["kind"].to_numpy(), why_on)
    return {
        "eyem_correct_before": float(np.mean([r in ok for r in why_off[eyem]])),
        "eyem_correct_after": float(np.mean([r in ok for r in why_on[eyem]])),
        "eyem_eye_first": float(np.mean(why_on[eyem] == "eye")),
        "clean_eye_rate": float(eye_fires(clean).mean()),
        "artifact_eye_rate_by_kind": {k: float(eye_fires(g).mean()) for k, g in art.groupby("kind") if len(g) >= 100},
        "e7_correct_among_flagged": accuracy["correct_among_flagged"],
        "e7_flagged_share": accuracy["flagged_share"],
    }


def main() -> None:
    from sqi_v2_gate_check import gate_check

    metrics = _test_half_metrics()
    print(json.dumps(metrics, indent=2), flush=True)
    e9 = gate_check()
    metrics["eye_share"] = {k: e9[k]["reason_channel_share"]["eye"] for k in ("IS", "NS", "TUSL_slow", "TUSL_bckg")}
    out = {"metrics": metrics, **verdict(metrics), "e9_gated_rate": {k: e9[k]["gated_rate"] for k in metrics["eye_share"]}}
    (ROOT / "results" / "eye_reason_eval.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("criteria", "ship")}, indent=2), metrics["eye_share"])


if __name__ == "__main__":
    main()
