"""Clinically interpretable metrics for the deployed Riemannian model on unseen sources.

AUC alone does not say whether a triage aid is usable. This script reports, under the
eye-state-matched leave-source-out condition (the most honest one we have):

  A. Patient level (held-out sources, mean window probability per patient)
     - AUC with patient-bootstrap 95% CI
     - sensitivity at fixed specificity and specificity at fixed sensitivity
       ("best achievable": the threshold is chosen on the test set -> optimistic)
     - PPV / NPV under ASSUMED prevalence scenarios (not field data)
  B. As deployed: the real-time detector (SQI gate, EMA, hysteresis, cooldown, fixed
     theta_high = 0.80 - nothing tuned on the test set) streamed over full recordings
     - stroke: share of patients alerted, time to first alert, time in alert
     - controls: alert episodes per monitored hour (exact Poisson CI), share alerted
     - No-Decision share for both
  C. Calibration: expected calibration error of window probabilities

Splits (train -> test, every test source unseen):
  S1: xuanwu + oslo45  -> tianjin + physionet_eo
  S2: tianjin + oslo45 -> xuanwu  + physionet_eo
Window caches come from scripts/leave_source_out.py (F:/eeg_extra/cache_lso).

Run with the app venv:  .venv/Scripts/python.exe scripts/clinical_utility.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy.stats import chi2
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CACHE = Path("F:/eeg_extra/cache_lso")
SPLITS = {"S1": (["xuanwu", "oslo45"], ["tianjin", "physionet_eo"]),
          "S2": (["tianjin", "oslo45"], ["xuanwu", "physionet_eo"])}
PREVALENCES = (0.3, 0.5, 0.7)


# ------------------------------------------------------------------ pure metrics
def _rates(y: np.ndarray, s: np.ndarray, thr: float) -> tuple[float, float]:
    pos = s >= thr
    return float(pos[y == 1].mean()), float((~pos)[y == 0].mean())


def sensitivity_at_specificity(y, s, target_spec: float) -> tuple[float, float, float]:
    """Highest sensitivity among thresholds with specificity >= target. Returns (sens, spec, thr)."""
    best = (-1.0, 0.0, float("nan"))
    for thr in np.unique(s):
        sens, spec = _rates(np.asarray(y), np.asarray(s), thr)
        if spec >= target_spec and (sens, spec) > best[:2]:
            best = (sens, spec, float(thr))
    return best


def specificity_at_sensitivity(y, s, target_sens: float) -> tuple[float, float, float]:
    """Highest specificity among thresholds with sensitivity >= target. Returns (spec, sens, thr)."""
    best = (-1.0, 0.0, float("nan"))
    for thr in np.unique(s):
        sens, spec = _rates(np.asarray(y), np.asarray(s), thr)
        if sens >= target_sens and (spec, sens) > best[:2]:
            best = (spec, sens, float(thr))
    return best


def ppv_npv(sens: float, spec: float, prevalence: float) -> tuple[float, float]:
    tp, fn = sens * prevalence, (1 - sens) * prevalence
    tn, fp = spec * (1 - prevalence), (1 - spec) * (1 - prevalence)
    return tp / (tp + fp) if tp + fp else float("nan"), tn / (tn + fn) if tn + fn else float("nan")


def bootstrap_ci(fn: Callable[[np.ndarray, np.ndarray], float], y, s, n_boot: int = 2000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Percentile CI, resampling patients within each class so both classes stay present."""
    rng = np.random.default_rng(seed)
    y, s = np.asarray(y), np.asarray(s)
    idx0, idx1 = np.flatnonzero(y == 0), np.flatnonzero(y == 1)
    stats = []
    for _ in range(n_boot):
        b = np.r_[rng.choice(idx0, idx0.size), rng.choice(idx1, idx1.size)]
        stats.append(fn(y[b], s[b]))
    return float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))


def count_alert_episodes(statuses) -> int:
    return sum(1 for st in statuses if st == "alert-enter")


def per_hour(count: int, n_events: int, hop_sec: float) -> float:
    return count / (n_events * hop_sec / 3600.0)


def poisson_rate_ci(k: int, hours: float, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) CI for a Poisson rate, events per hour."""
    lo = 0.0 if k == 0 else chi2.ppf(alpha / 2, 2 * k) / 2
    hi = chi2.ppf(1 - alpha / 2, 2 * k + 2) / 2
    return lo / hours, hi / hours


def expected_calibration_error(y, p, n_bins: int = 10) -> float:
    y, p = np.asarray(y), np.asarray(p)
    bins = np.minimum((p * n_bins).astype(int), n_bins - 1)
    return float(sum(abs(y[bins == b].mean() - p[bins == b].mean()) * (bins == b).mean()
                     for b in range(n_bins) if (bins == b).any()))


# ------------------------------------------------------------------ data + model
def _cache(name: str) -> dict:
    z = np.load(CACHE / f"{name}_cap24.npz", allow_pickle=True)
    return {k: z[k] for k in ("windows", "pids", "y")}


def _fit(train: list[str]):
    from riemann_model import RiemannStrokeModel
    parts = [_cache(n) for n in train]
    x, y = np.concatenate([p["windows"] for p in parts]), np.concatenate([p["y"] for p in parts])
    return RiemannStrokeModel.fit(x, y, channels=[f"c{i}" for i in range(x.shape[1])], fs=256.0, window_sec=4.0)


def patient_scores(model, test: list[str]) -> pd.DataFrame:
    rows = []
    for name in test:
        c = _cache(name)
        probs = np.array([model.predict_proba_from_window(w)[1] for w in c["windows"]])
        rows.append(pd.DataFrame({"pid": c["pids"], "y": c["y"], "p": probs, "source": name}))
    return pd.concat(rows, ignore_index=True)


def _recordings(source: str) -> list[tuple[str, np.ndarray]]:
    from eeg_stroke_pipeline import DEFAULT_CHANNELS, load_array_file, reorder_to_target_channels
    from leave_source_out import _manifests, slice_fraction, to_microvolts
    man = _manifests(50)[source]
    out = []
    for r in man.itertuples():
        data, chans, _ = load_array_file(r.path)
        x = to_microvolts(reorder_to_target_channels(data, chans, DEFAULT_CHANNELS))
        if "frac0" in man.columns:
            x = slice_fraction(x, (r.frac0, r.frac1))
        out.append((r.patient_id, x))
    return out


def stream(model, recordings) -> pd.DataFrame:
    """Run the deployed real-time detector (fixed thresholds) over each recording."""
    from eeg_stroke_pipeline import PipelineConfig, RealTimeStrokeDetector
    rows = []
    for pid, x in recordings:
        det = RealTimeStrokeDetector(None, config=PipelineConfig(), window_model=model)
        events = []
        for i in range(0, x.shape[1], 128):
            events += det.update(x[:, i:i + 128])
        st = [e["status"] for e in events]
        first = next((e["timestamp_sec"] for e in events if e["status"] == "alert-enter"), None)
        rows.append({"pid": pid, "n_events": len(st), "episodes": count_alert_episodes(st),
                     "first_alert_sec": first, "duration_sec": x.shape[1] / 256.0,
                     "alert_share": float(np.mean([s in ("alert-enter", "alert-hold") for s in st])) if st else 0.0,
                     "nodecision_share": float(np.mean([s == "no-decision" for s in st])) if st else 0.0})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--out", default=str(ROOT / "results" / "clinical_utility.json"))
    args = ap.parse_args()
    report: dict = {"condition": "eye-state matched, unseen sources", "splits": {}}

    for split, (train, test) in SPLITS.items():
        model = _fit(train)
        win = patient_scores(model, test)
        pt = win.groupby("pid").agg(y=("y", "first"), p=("p", "mean")).reset_index()
        y, s = pt["y"].to_numpy(), pt["p"].to_numpy()
        r: dict = {"train": train, "test": test, "n_stroke": int(y.sum()), "n_control": int((y == 0).sum()),
                   "auc": roc_auc_score(y, s), "auc_ci": bootstrap_ci(roc_auc_score, y, s, args.n_boot)}
        for spec_t in (0.8, 0.9):
            sens, spec, thr = sensitivity_at_specificity(y, s, spec_t)
            ci = bootstrap_ci(lambda yy, ss, t=spec_t: sensitivity_at_specificity(yy, ss, t)[0], y, s, args.n_boot)
            r[f"sens_at_spec{int(spec_t * 100)}"] = {"sens": sens, "spec": spec, "thr": thr, "sens_ci": ci}
        for sens_t in (0.9, 0.95):
            spec, sens, thr = specificity_at_sensitivity(y, s, sens_t)
            r[f"spec_at_sens{int(sens_t * 100)}"] = {"spec": spec, "sens": sens, "thr": thr}
        op = r["spec_at_sens90"]
        r["ppv_npv_at_sens90"] = {str(pr): ppv_npv(op["sens"], op["spec"], pr) for pr in PREVALENCES}
        r["ece_window"] = expected_calibration_error(win["y"], win["p"])

        stroke_src = [t for t in test if t != "physionet_eo"][0]
        streams = {"control": stream(model, _recordings("physionet_eo"))}
        if stroke_src == "xuanwu":            # tianjin rests are 8.6 s fragments: too short to stream
            streams["stroke"] = stream(model, _recordings("xuanwu"))
        dep: dict = {}
        c = streams["control"]
        hours = float((c["n_events"] * 0.5).sum() / 3600)
        k = int(c["episodes"].sum())
        dep["control"] = {"subjects": len(c), "monitored_hours": hours, "alert_episodes": k,
                          "false_alerts_per_hour": k / hours, "false_alerts_per_hour_ci": poisson_rate_ci(k, hours),
                          "share_subjects_alerted": float((c["episodes"] > 0).mean()),
                          "nodecision_share": float(c["nodecision_share"].mean())}
        if "stroke" in streams:
            st = streams["stroke"]
            alerted = st["first_alert_sec"].notna()
            dep["stroke"] = {"patients": len(st), "share_alerted_any": float(alerted.mean()),
                             "share_alerted_within_60s": float((st["first_alert_sec"] <= 60).mean()),
                             "median_first_alert_sec": float(st.loc[alerted, "first_alert_sec"].median()) if alerted.any() else None,
                             "mean_time_in_alert": float(st["alert_share"].mean()),
                             "nodecision_share": float(st["nodecision_share"].mean())}
            sens_dep, spec_dep = dep["stroke"]["share_alerted_any"], 1 - dep["control"]["share_subjects_alerted"]
            dep["patient_level_as_deployed"] = {"sens": sens_dep, "spec": spec_dep,
                                                "ppv_npv": {str(pr): ppv_npv(sens_dep, spec_dep, pr) for pr in PREVALENCES}}
        r["as_deployed"] = dep
        report["splits"][split] = r
        print(f"[{split}] done", flush=True)

    Path(args.out).write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    for split, r in report["splits"].items():
        print(f"\n== {split}: train {'+'.join(r['train'])} -> test {'+'.join(r['test'])} "
              f"({r['n_stroke']} stroke / {r['n_control']} control patients)")
        print(f"AUC {r['auc']:.3f} [{r['auc_ci'][0]:.3f}, {r['auc_ci'][1]:.3f}]   window ECE {r['ece_window']:.3f}")
        for key in ("sens_at_spec80", "sens_at_spec90"):
            v = r[key]
            print(f"  best-achievable sens {v['sens']:.2f} [{v['sens_ci'][0]:.2f}, {v['sens_ci'][1]:.2f}] at spec {v['spec']:.2f}")
        for key in ("spec_at_sens90", "spec_at_sens95"):
            v = r[key]
            print(f"  best-achievable spec {v['spec']:.2f} at sens {v['sens']:.2f}")
        print("  PPV/NPV at sens>=0.90 (assumed prevalence): " +
              "  ".join(f"{pr}: {a:.2f}/{b:.2f}" for pr, (a, b) in r["ppv_npv_at_sens90"].items()))
        d = r["as_deployed"]
        c = d["control"]
        print(f"  AS DEPLOYED controls: {c['false_alerts_per_hour']:.1f} false alerts/h "
              f"[{c['false_alerts_per_hour_ci'][0]:.1f}, {c['false_alerts_per_hour_ci'][1]:.1f}] over {c['monitored_hours']:.2f} h; "
              f"{c['share_subjects_alerted']:.0%} of controls ever alerted; No-Decision {c['nodecision_share']:.1%}")
        if "stroke" in d:
            s_ = d["stroke"]
            print(f"  AS DEPLOYED stroke: {s_['share_alerted_any']:.0%} alerted (within 60 s: {s_['share_alerted_within_60s']:.0%}), "
                  f"median first alert {s_['median_first_alert_sec']} s, in alert {s_['mean_time_in_alert']:.0%} of time, "
                  f"No-Decision {s_['nodecision_share']:.1%}")
            pdp = d["patient_level_as_deployed"]
            print(f"  AS DEPLOYED patient-level sens {pdp['sens']:.2f} / spec {pdp['spec']:.2f}; PPV/NPV: " +
                  "  ".join(f"{pr}: {a:.2f}/{b:.2f}" for pr, (a, b) in pdp["ppv_npv"].items()))


if __name__ == "__main__":
    main()
