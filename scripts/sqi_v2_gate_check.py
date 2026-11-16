"""R1 safety check: does SQI v2 gate stroke / slowing recordings more than controls?

Stroke raises delta power and steepens the 1/f slope, and so does poor electrode contact.
If SQI v2 confused the two it would withhold decisions mostly from the patients it should
help. This script compares, per cohort, how often a 4 s window falls below ``CHANNEL_OK``
and which reasons fire. It also reports how well the v2 record score alone separates
IS from NS: a high AUC would mean v2 carries the same acquisition shortcut as v1
(SQI-only AUC 0.998, docs/uist_evidence.md).

Cohorts: 50 IS (dataset_ischemic), 50 NS (dataset_healthy, first 50), and the same-rig
TUSL slow vs bckg segments (dataset_tuh).

Usage::

    .venv/Scripts/python.exe scripts/sqi_v2_gate_check.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import sqi_v2 as S  # noqa: E402

WIN_SEC = 4.0
MAX_WINDOWS_PER_RECORD = 40
N_CONTROLS = 50


CALIBRATION = ROOT / "results" / "sqi_v2_calibration.json"


def make_config(line_freq: float) -> S.SqiV2Config:
    """Default config, with the frozen TUAR drift ramp when a calibration file exists."""
    values: dict = {"line_freq": line_freq}
    if CALIBRATION.exists():
        values["drift_ramp"] = json.loads(CALIBRATION.read_text(encoding="utf-8"))["drift_ramp"]
    return S.config_from_dict(values)


def record_windows(path: Path, line_freq: float) -> list[dict]:
    d = np.load(path)
    x, fs = d["data"].astype(float), float(d["fs"])
    n = int(WIN_SEC * fs)
    cfg = make_config(line_freq)
    rows = []
    for k in list(range(0, x.shape[1] - n + 1, n))[:MAX_WINDOWS_PER_RECORD]:
        q = S.assess_window(x[:, k : k + n], fs, config=cfg)
        reasons = [r for c in q.channels for r in c.reasons]
        rows.append({
            "score": q.score,
            "gated": q.score < S.CHANNEL_OK,
            "bad_channels": float(np.mean([c.score < S.CHANNEL_OK for c in q.channels])),
            **{r: reasons.count(r) for r in S.REASON_ADVICE},
        })
    return rows


def summarize(paths: Sequence[Path], line_freq: float) -> tuple[dict, np.ndarray]:
    per_record, all_rows = [], []
    for p in paths:
        rows = record_windows(p, line_freq)
        if rows:
            all_rows.extend(rows)
            per_record.append((
                np.mean([r["score"] for r in rows]),
                np.mean([r["gated"] for r in rows]),
                np.mean([r["bad_channels"] for r in rows]),
            ))
    rec = np.array(per_record)
    summary = {
        "n_recordings": int(len(rec)),
        "n_windows": len(all_rows),
        "mean_score": float(rec[:, 0].mean()),
        "gated_rate": float(rec[:, 1].mean()),
        "bad_channel_rate": float(rec[:, 2].mean()),
        "reasons_per_window": {r: float(sum(w[r] for w in all_rows) / len(all_rows)) for r in S.REASON_ADVICE},
    }
    return summary, rec[:, 0]


def main() -> None:
    import pandas as pd
    from sklearn.metrics import roc_auc_score

    out: dict = {}
    out["IS"], is_scores = summarize(sorted((ROOT / "dataset_ischemic").glob("sub-*.npz")), 50.0)
    out["NS"], ns_scores = summarize(sorted((ROOT / "dataset_healthy").glob("*.npz"))[:N_CONTROLS], 50.0)
    manifest = pd.read_csv(ROOT / "dataset_tuh" / "manifest_tuh.csv")
    for label, name in [(1, "TUSL_slow"), (0, "TUSL_bckg")]:
        paths = [ROOT / Path(p.replace("\\", "/")) for p in manifest.loc[manifest["label"] == label, "path"]]
        out[name], _ = summarize(paths, 60.0)  # TUH is a US rig
    y = np.r_[np.ones(len(is_scores)), np.zeros(len(ns_scores))]
    out["auc_is_vs_ns_from_v2_record_score"] = float(roc_auc_score(y, np.r_[is_scores, ns_scores]))
    out["drift_ramp"] = list(make_config(50.0).drift_ramp)
    out["drift_ramp_source"] = str(CALIBRATION) if CALIBRATION.exists() else "default (synthetic)"
    out["safety_ok"] = bool(
        out["IS"]["gated_rate"] <= out["NS"]["gated_rate"]
        and out["TUSL_slow"]["gated_rate"] <= out["TUSL_bckg"]["gated_rate"]
    )
    dest = ROOT / "results" / "sqi_v2_gate_check.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
