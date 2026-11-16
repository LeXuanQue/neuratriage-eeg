"""Study 1 blinded rating and time-to-usable-signal (TTU), docs/user_study_protocol.md 1.6-1.7.

prepare
    Cut every raw study recording (data/study_logs/raw/<opaque id>.npz) into 10 s epochs,
    give each a random id, shuffle across recordings and conditions, and write for the
    rater only ``rating/epochs/<epoch_id>.png`` + ``rating/ratings_template.csv``
    (epoch_id,usable,comment). The epoch -> recording map goes to ``rating/epoch_key.csv``,
    which the rater must not see.

score
    Join the rater's CSV (usable = 1/0) with the epoch key, the raw key (recording start
    time, participant, condition) and the facilitator's event log, then compute per trial
    TTU = start of the first run of 6 consecutive usable epochs (60 s) that starts at or
    after the trial start, minus the trial start. Trials without such a run are censored at
    TIMEOUT_SEC. With --ratings2 the inter-rater Cohen's kappa is reported.

Usage::

    .venv/Scripts/python.exe scripts/study_rating.py prepare
    .venv/Scripts/python.exe scripts/study_rating.py score --ratings rater1.csv [--ratings2 rater2.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EPOCH_SEC = 10.0
RUN_EPOCHS = 6           # 6 x 10 s = 60 s of usable signal
TIMEOUT_SEC = 480.0      # 8 min per trial (protocol 1.5)


# --------------------------------------------------------------------------- helpers
def epoch_bounds(n_samples: int, fs: float, epoch_sec: float = EPOCH_SEC) -> List[Tuple[int, int]]:
    step = int(round(epoch_sec * fs))
    return [(k, k + step) for k in range(0, n_samples - step + 1, step)]


def iso_seconds(ts: str) -> float:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def time_to_usable(
    epoch_starts: np.ndarray, usable: np.ndarray, trial_start: float, trial_end: Optional[float]
) -> Tuple[float, bool]:
    """Seconds from trial start to the first 60 s usable run (censored at the timeout)."""
    limit = trial_start + TIMEOUT_SEC
    if trial_end is not None:
        limit = min(limit, trial_end)
    starts, ok = np.asarray(epoch_starts, float), np.asarray(usable, bool)
    for i in range(starts.size - RUN_EPOCHS + 1):
        if starts[i] < trial_start:
            continue
        if starts[i + RUN_EPOCHS - 1] + EPOCH_SEC > limit:
            break
        if ok[i : i + RUN_EPOCHS].all():
            return float(starts[i] - trial_start), False
    return TIMEOUT_SEC, True


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, int), np.asarray(b, int)
    po = float(np.mean(a == b))
    pe = float(np.mean(a) * np.mean(b) + (1 - np.mean(a)) * (1 - np.mean(b)))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def trials_from_events(events: Sequence[dict]) -> List[dict]:
    """Pair trial_start / trial_end markers (server time) per trial number."""
    trials: Dict[int, dict] = {}
    for e in events:
        if e["type"] == "trial_start":
            trials[e["trial"]] = {"trial": e["trial"], "condition": e["condition"],
                                  "start": iso_seconds(e["server_ts"]), "end": None}
        elif e["type"] == "trial_end" and e["trial"] in trials:
            trials[e["trial"]]["end"] = iso_seconds(e["server_ts"])
    return [trials[k] for k in sorted(trials)]


# --------------------------------------------------------------------------- prepare
YLIM_FACTOR = 6.0  # y-axis = +/- 6 x the recording's typical per-channel epoch std


def typical_scale(data: np.ndarray, fs: float) -> np.ndarray:
    """Per-channel median epoch std over a whole recording (fixes the plot scale)."""
    stds = [np.std(data[:, a:b], axis=1) for a, b in epoch_bounds(data.shape[1], fs)]
    scale = np.median(np.stack(stds), axis=0) if stds else np.std(data, axis=1)
    return np.where(scale > 0, scale, 1.0)


def _render(png: Path, data: np.ndarray, channels: Sequence[str], fs: float, scale: np.ndarray) -> None:
    """Fixed per-recording y-scale: with autoscaling a flat or drifting channel would be
    blown up to look like ordinary EEG and mislead the rater."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.arange(data.shape[1]) / fs
    fig, axes = plt.subplots(data.shape[0], 1, figsize=(12, 1.6 * data.shape[0]), sharex=True)
    for ax, x, name, s in zip(np.atleast_1d(axes), data, channels, scale):
        lim = YLIM_FACTOR * s
        ax.plot(t, np.clip(x - np.median(x), -lim, lim), lw=0.6, color="black")
        ax.set_ylim(-lim, lim)
        ax.set_ylabel(str(name), rotation=0, ha="right", va="center")
        ax.set_yticks([])
    np.atleast_1d(axes)[-1].set_xlabel("s")
    fig.tight_layout()
    fig.savefig(png, dpi=80)
    plt.close(fig)


def prepare(root: Path, seed: int = 0, render: bool = True) -> Path:
    raw_files = sorted((root / "raw").glob("*.npz"))
    out = root / "rating"
    (out / "epochs").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    items = []
    for f in raw_files:
        z = np.load(f)
        fs = float(z["fs"])
        for a, b in epoch_bounds(z["data"].shape[1], fs):
            items.append((f.stem, a, b))
    order = rng.permutation(len(items))
    ids = [f"e{rng.integers(0, 16**8):08x}" for _ in items]
    scales = {}
    if render:
        for f in raw_files:
            z = np.load(f)
            scales[f.stem] = typical_scale(z["data"], float(z["fs"]))
    with open(out / "ratings_template.csv", "w", newline="", encoding="utf-8") as tpl, \
            open(out / "epoch_key.csv", "w", newline="", encoding="utf-8") as key:
        tw, kw = csv.writer(tpl), csv.writer(key)
        tw.writerow(["epoch_id", "usable", "comment"])
        kw.writerow(["epoch_id", "raw_id", "start_sample"])
        for i in order:
            raw_id, a, b = items[i]
            tw.writerow([ids[i], "", ""])
            kw.writerow([ids[i], raw_id, a])
            if render:
                z = np.load(root / "raw" / f"{raw_id}.npz")
                _render(out / "epochs" / f"{ids[i]}.png", z["data"][:, a:b], [str(c) for c in z["channels"]],
                        float(z["fs"]), scales[raw_id])
    return out


# --------------------------------------------------------------------------- score
def _read_csv(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _usable_by_recording(root: Path, ratings: Path) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    key = {r["epoch_id"]: (r["raw_id"], int(r["start_sample"])) for r in _read_csv(root / "rating" / "epoch_key.csv")}
    rows: Dict[str, list] = {}
    for r in _read_csv(ratings):
        if r["epoch_id"] in key and str(r["usable"]).strip() in ("0", "1"):
            raw_id, start = key[r["epoch_id"]]
            rows.setdefault(raw_id, []).append((start, int(r["usable"])))
    return {rid: (np.array([s for s, _ in v]), np.array([u for _, u in v], bool))
            for rid, v in ((rid, sorted(v)) for rid, v in rows.items())}


def score(root: Path, ratings: Path, ratings2: Optional[Path] = None) -> dict:
    raw_key = [json.loads(x) for x in (root / "raw_key.jsonl").read_text(encoding="utf-8").splitlines()]
    usable = _usable_by_recording(root, ratings)
    rows = []
    for log in sorted(root.glob("P*.jsonl")):
        participant = log.stem
        events = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
        sessions = [k for k in raw_key if k["participant"] == participant]
        for tr in trials_from_events(events):
            rec = next((k for k in sessions if iso_seconds(k["started_utc"]) <= tr["start"]
                        <= iso_seconds(k["started_utc"]) + k["n_samples"] / k["fs"]), None)
            if rec is None or rec["raw_id"] not in usable:
                rows.append({"participant": participant, "condition": tr["condition"], "trial": tr["trial"],
                             "ttu_sec": "", "censored": "", "note": "no rated recording"})
                continue
            t0 = iso_seconds(rec["started_utc"])
            starts, ok = usable[rec["raw_id"]]
            ttu, censored = time_to_usable(starts / rec["fs"], ok, tr["start"] - t0,
                                           None if tr["end"] is None else tr["end"] - t0)
            rows.append({"participant": participant, "condition": tr["condition"], "trial": tr["trial"],
                         "ttu_sec": round(ttu, 1), "censored": censored, "note": ""})
    out = {"trials": rows}
    if ratings2 is not None:
        r1 = {r["epoch_id"]: r["usable"] for r in _read_csv(ratings)}
        r2 = {r["epoch_id"]: r["usable"] for r in _read_csv(ratings2)}
        both = [k for k in r1 if k in r2 and r1[k] in ("0", "1") and r2[k] in ("0", "1")]
        out["kappa"] = cohen_kappa(np.array([int(r1[k]) for k in both]), np.array([int(r2[k]) for k in both]))
        out["n_double_rated"] = len(both)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["prepare", "score"])
    ap.add_argument("--root", default=str(ROOT / "data" / "study_logs"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ratings")
    ap.add_argument("--ratings2")
    ap.add_argument("--out", default=str(ROOT / "results" / "study1_ttu.csv"))
    args = ap.parse_args()
    root = Path(args.root)
    if args.command == "prepare":
        out = prepare(root, args.seed)
        print(f"rater folder: {out / 'epochs'} + {out / 'ratings_template.csv'} (do NOT share epoch_key.csv)")
        return
    if not args.ratings:
        sys.exit("score needs --ratings")
    res = score(root, Path(args.ratings), Path(args.ratings2) if args.ratings2 else None)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["participant", "condition", "trial", "ttu_sec", "censored", "note"])
        w.writeheader()
        w.writerows(res["trials"])
    print(f"{len(res['trials'])} trials -> {args.out}" + (f"; kappa {res['kappa']:.2f} on {res['n_double_rated']} epochs" if "kappa" in res else ""))


if __name__ == "__main__":
    main()
