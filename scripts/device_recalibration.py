"""Per-device threshold recalibration for the real-time detector.

On an unseen device the Riemannian model ranks patients well (AUC ~0.82) but its
probability scale shifts, so the fixed theta_high = 0.80 yields 51-66 false alerts per
hour on healthy controls (results/clinical_utility.json). Proposed fix: record a few
minutes of resting EEG from healthy people ON THE NEW DEVICE and set theta_high just
above the highest smoothed P(stroke) they produce. No stroke data from that device is
needed.

Evaluation (honest by construction):
  * calibration controls and evaluation controls are disjoint subjects (random splits,
    repeated), so false alerts are measured on people the threshold never saw;
  * the stroke patients are on a DIFFERENT device than the controls in our data, so the
    sensitivity reported after recalibration is an estimate, not a same-device measure.

The detector is streamed once per recording to store raw P(stroke) per hop; alert logic
is then replayed offline by `simulate_alerts`, which is tested to match
RealTimeStrokeDetector exactly, so hundreds of settings cost seconds.

Run with the app venv:  .venv/Scripts/python.exe scripts/device_recalibration.py
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eeg_stroke_pipeline import PipelineConfig  # noqa: E402

CACHE = Path("F:/eeg_extra/cache_recal")
FIRST_EVENT_SEC, HOP_SEC = 4.0, 0.5


# ------------------------------------------------------------------ alert simulation
def smoothed(seq, beta: float) -> np.ndarray:
    """EMA of the scored hops of one recording (no-decision hops skipped, as in the detector)."""
    out, s = [], None
    for p in seq:
        if p is None:
            continue
        s = p if s is None else beta * p + (1 - beta) * s
        out.append(s)
    return np.asarray(out if out else [0.0])


def simulate_alerts(probs, cfg: PipelineConfig) -> list[str]:
    """Replay RealTimeStrokeDetector's binary alert logic on a sequence of P(stroke) (None = SQI gated)."""
    step = int(round(cfg.entropy_step_sec * cfg.fs))
    cooldown = int(round(cfg.cooldown_sec * cfg.fs))
    smooth, alert, high, low = None, False, 0, 0
    last_alert, last_class = -10 ** 12, None
    out = []
    for h, p in enumerate(probs):
        emit = h * step
        if p is None:
            out.append("no-decision")
            continue
        smooth = p if smooth is None else cfg.ema_beta * p + (1 - cfg.ema_beta) * smooth
        is_stroke = smooth > 1.0 - smooth                      # argmax over [P(NS), P(stroke)]
        cooldown_active = (emit - last_alert) < cooldown
        if not alert:
            if is_stroke and smooth >= cfg.theta_high and not (cooldown_active and last_class == 1):
                high += 1
            else:
                high = 0
            if is_stroke and high >= cfg.enter_k:
                alert, last_alert, last_class = True, emit, 1
                out.append("alert-enter")
            else:
                out.append("monitor")
            continue
        low = low + 1 if smooth < cfg.theta_low else 0
        if low >= cfg.exit_m:
            alert, low, high = False, 0, 0
            out.append("alert-exit")
        else:
            out.append("alert-hold")
    return out


def calibrate_threshold(healthy_seqs, cfg: PipelineConfig, rule: str = "max", margin: float = 0.005,
                        q: float = 0.99, target_spec: float = 0.9, floor: float = 0.80, ceil: float = 0.999) -> float:
    """theta_high from healthy recordings on the new device (never below the deployed 0.80).

    rule="max":  just above every healthy smoothed value (no healthy recording may alert)
    rule="q":    above the q-quantile of all healthy smoothed values
    rule="spec": above the target_spec-quantile of each recording's peak, i.e. about
                 target_spec of healthy recordings stay silent - an explicit specificity target
    """
    if rule == "spec":
        peaks = np.array([smoothed(s, cfg.ema_beta).max() for s in healthy_seqs])
        ref = np.quantile(peaks, target_spec, method="higher")
    else:
        vals = np.concatenate([smoothed(s, cfg.ema_beta) for s in healthy_seqs])
        ref = vals.max() if rule == "max" else np.quantile(vals, q)
    return float(min(ceil, max(floor, ref + margin)))


def summarize(seqs, cfg: PipelineConfig) -> dict:
    episodes, hops, first = 0, 0, []
    for s in seqs:
        st = simulate_alerts(s, cfg)
        episodes += st.count("alert-enter")
        hops += len(st)
        first.append(FIRST_EVENT_SEC + HOP_SEC * st.index("alert-enter") if "alert-enter" in st else None)
    alerted = [f for f in first if f is not None]
    hours = hops * HOP_SEC / 3600
    return {"alerts_per_hour": episodes / hours if hours else float("nan"),
            "share_alerted": len(alerted) / len(seqs),
            "median_first_alert_sec": float(np.median(alerted)) if alerted else None}


# ------------------------------------------------------------------ data
def record_sequences(split: str, source: str, model) -> list[list]:
    """Stream each recording once and keep raw P(stroke) per hop (None where SQI-gated). Cached."""
    path = CACHE / f"{split}_{source}.json"
    if path.exists():
        return json.loads(path.read_text())
    from clinical_utility import _recordings
    from eeg_stroke_pipeline import RealTimeStrokeDetector
    seqs = []
    for _, x in _recordings(source):
        det = RealTimeStrokeDetector(None, config=PipelineConfig(), window_model=model)
        events = []
        for i in range(0, x.shape[1], 128):
            events += det.update(x[:, i:i + 128])
        seqs.append([None if e["probabilities_raw"] is None else float(e["probabilities_raw"][1]) for e in events])
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seqs))
    return seqs


# ------------------------------------------------------------------ main
def _q3(vals) -> list[float] | None:
    v = np.asarray([x for x in vals if x is not None], dtype=float)
    return [float(np.quantile(v, a)) for a in (0.025, 0.5, 0.975)] if v.size else None


def main() -> None:
    from clinical_utility import SPLITS, _fit
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=500)
    ap.add_argument("--out", default=str(ROOT / "results" / "device_recalibration.json"))
    args = ap.parse_args()
    base = PipelineConfig()
    thetas = [0.80, 0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 0.99, 0.995, 0.999]
    report: dict = {}

    for split, (train, test) in SPLITS.items():
        model = _fit(train)
        controls = record_sequences(split, "physionet_eo", model)
        stroke_src = [t for t in test if t != "physionet_eo"][0]
        stroke = record_sequences(split, stroke_src, model) if stroke_src == "xuanwu" else None
        r: dict = {"sweep": []}
        for k in (2, 6, 10):
            for t in thetas:
                cfg = replace(base, theta_high=t, enter_k=k)
                row = {"theta_high": t, "enter_k": k, "controls": summarize(controls, cfg)}
                if stroke:
                    row["stroke"] = summarize(stroke, cfg)
                r["sweep"].append(row)

        rng = np.random.default_rng(0)
        for n_cal in (10, 20):
            rules = {"max": {"rule": "max"}, "q99": {"rule": "q"},
                     "spec80": {"rule": "spec", "target_spec": 0.8}, "spec90": {"rule": "spec", "target_spec": 0.9}}
            for rule, kwargs in rules.items():
                rows = []
                for _ in range(args.repeats):
                    idx = rng.permutation(len(controls))
                    cal, ev = [controls[i] for i in idx[:n_cal]], [controls[i] for i in idx[n_cal:]]
                    theta = calibrate_threshold(cal, base, **kwargs)
                    cfg = replace(base, theta_high=theta)
                    row = {"theta": theta, "controls": summarize(ev, cfg)}
                    if stroke:
                        row["stroke"] = summarize(stroke, cfg)
                    rows.append(row)
                r[f"calibrated_n{n_cal}_{rule}"] = {
                    "theta": _q3([x["theta"] for x in rows]),
                    "false_alerts_per_hour": _q3([x["controls"]["alerts_per_hour"] for x in rows]),
                    "share_controls_alerted": _q3([x["controls"]["share_alerted"] for x in rows]),
                    **({"stroke_sensitivity": _q3([x["stroke"]["share_alerted"] for x in rows]),
                        "stroke_median_first_alert_sec": _q3([x["stroke"]["median_first_alert_sec"] for x in rows])}
                       if stroke else {}),
                }
        report[split] = r
        print(f"[{split}] done", flush=True)

    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    for split, r in report.items():
        print(f"\n== {split}  (2.5% / median / 97.5% over {args.repeats} random calibration splits)")
        d = next(x for x in r["sweep"] if x["theta_high"] == 0.80 and x["enter_k"] == 2)
        line = (f"  fixed 0.80            : {d['controls']['alerts_per_hour']:5.1f} false alerts/h, "
                f"{d['controls']['share_alerted']:.0%} controls alerted")
        if "stroke" in d:
            line += f" | stroke sens {d['stroke']['share_alerted']:.0%}"
        print(line)
        for key in [k for k in r if k.startswith("calibrated")]:
            c = r[key]
            def fmt(v, p=1):
                return "/".join(f"{x:.{p}f}" for x in v)
            line = (f"  {key:22s}: theta {fmt(c['theta'], 3)}  false alerts/h {fmt(c['false_alerts_per_hour'])}  "
                    f"controls alerted {fmt(c['share_controls_alerted'], 2)}")
            if c.get("stroke_sensitivity"):
                line += f" | stroke sens {fmt(c['stroke_sensitivity'], 2)}"
                if c.get("stroke_median_first_alert_sec"):
                    line += f", first alert {fmt(c['stroke_median_first_alert_sec'])} s"
            print(line)


if __name__ == "__main__":
    main()
