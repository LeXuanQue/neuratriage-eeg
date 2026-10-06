"""Train the real-time Riemannian stroke model (backend/riemann_model.py) for the app.

Training data = the window caches built by scripts/leave_source_out.py (same pipeline
preprocessing, microvolts, 4 s windows, SQI-gated):
  stroke  : xuanwu (acute IS) + tianjin (chronic stroke, IS+HS)
  control : physionet_eo (eyes OPEN only)
Eyes-closed controls are left out on purpose: with them the model learns "strong
alpha = healthy" (shown by --experiment eyes), which would call a drowsy or
eyes-closed stroke patient healthy, i.e. a missed stroke.

The held-out numbers stored in the model metadata come from results/
leave_source_out_*_riemann_app.json (train on one source pair, test on unseen ones).

Run with the APP venv so the pickled scikit-learn objects match the server:
  .venv/Scripts/python.exe scripts/train_riemann_model.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from eeg_stroke_pipeline import DEFAULT_CHANNELS  # noqa: E402
from riemann_model import RiemannStrokeModel  # noqa: E402

CACHE = Path("F:/eeg_extra/cache_lso")
STROKE, CONTROL = ("xuanwu", "tianjin"), ("physionet_eo",)


def _heldout_summary() -> dict:
    out = {}
    for exp in ("main", "eyes"):
        p = ROOT / "results" / f"leave_source_out_{exp}_riemann_app.json"
        if p.exists():
            rows = json.loads(p.read_text(encoding="utf-8"))["source_swap"]
            out[exp] = [{"train": r["train"], "test": r["test"], "patient_auc": round(r["patient_auc"], 3)} for r in rows]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=24)
    ap.add_argument("--out", default=str(ROOT / "backend" / "models" / "riemann_model.joblib"))
    args = ap.parse_args()

    xs, ys, counts = [], [], {}
    for name in STROKE + CONTROL:
        z = np.load(CACHE / f"{name}_cap{args.cap}.npz", allow_pickle=True)
        label = 1 if name in STROKE else 0
        assert set(np.unique(z["y"])) == {label}, f"{name}: unexpected labels {np.unique(z['y'])}"
        xs.append(z["windows"])
        ys.append(z["y"])
        counts[name] = {"windows": int(len(z["y"])), "patients": int(len(np.unique(z["pids"])))}
    x, y = np.concatenate(xs), np.concatenate(ys)

    meta = {
        "created": dt.date.today().isoformat(),
        "train_sources": counts,
        "classes": ["non-stroke", "stroke (IS; tianjin also contains HS)"],
        "heldout_patient_auc": _heldout_summary(),
        "intended_use": "research prototype for triage support; NOT a diagnostic device",
        "known_limits": [
            "both stroke sources are Chinese hospitals recorded inside motor-imagery sessions",
            "tianjin mixes ischemic and hemorrhagic chronic stroke (per-subject type unpublished)",
            "eye-state matched held-out patient AUC ~0.82; cannot separate IS from HS",
        ],
    }
    model = RiemannStrokeModel.fit(x, y, channels=DEFAULT_CHANNELS, fs=256.0, window_sec=x.shape[2] / 256.0,
                                   metadata=meta)
    train_acc = float(np.mean([(model.predict_proba_from_window(w)[1] >= 0.5) == t for w, t in zip(x, y)]))
    model.metadata["train_window_accuracy"] = round(train_acc, 3)
    model.save(args.out)
    print(json.dumps({k: v for k, v in model.metadata.items() if k != "heldout_patient_auc"}, indent=2))
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
