"""R1 evaluation: does SQI v2 detect labelled artifacts better than SQI v1? (TUAR, one rig)

Unit of analysis is one bipolar channel x one 4 s window, which matches what the guidance UI
needs ("fix this electrode"). A window is an artifact on a channel when an annotated artifact
covers >= ``ARTIFACT_MIN_OVERLAP`` of it, clean when nothing overlaps, and dropped otherwise.

Compared, all with patient-level statistics (patients = TUH subject prefix):

* fixed rules: AUC of ``1 - v1 sqi_total`` vs ``1 - v2 channel score``;
* learned: logistic regression on v1 features vs v2 features, StratifiedGroupKFold by patient
  (same folds for both, quantile-normalised inputs so heavy-tailed v2 features are not
  handicapped);
* per artifact type (eyem, musc, chew, shiv, elpp, ...): the same out-of-fold learned scores,
  restricted to clean windows plus that type;
* window level (any channel artifact vs all channels clean), fixed rules;
* E7: on artifact channel-windows, whether the first SQI v2 reason names the right
  artifact type (musc/chew/shiv -> muscle, eyem -> transient/drift, elec/elpp -> contact);
* E8: in windows with both artifact and clean channels, whether the lowest-scoring channel
  (the one the interface tells the operator to fix) is an artifact channel, vs chance and v1.

Windows that contain any artifact keep every labelled channel (needed for E8); clean-only
windows keep a random ``--keep-clean`` share. Clean rows are therefore over-represented
from windows next to artifacts; this affects v1 and v2 equally (paired comparison).

v1 is computed as deployed: ``preprocess_eeg_for_sqi`` on the whole record (MAD clipping,
detrend, notch), then ``compute_sqi`` averaged over 1 s sub-windows. At channel level v1 sees
one channel, so its across-channel flatline term cannot fire; the window-level comparison
gives v1 its full multi-channel context. v2 gets the raw bipolar signal.

Pre-registered drop rule (docs/full_paper_plan.md, R1): keep R1 only if the learned v2 AUC
beats v1 by >= 0.05 at channel level (point estimate; the CI-based verdict is reported too).

Usage::

    .venv/Scripts/python.exe scripts/tuar_sqi_eval.py --tuar-root F:/tuh_data/tuar --workers 6
    .venv/Scripts/python.exe scripts/tuar_sqi_eval.py --eval-only   # reuse the feature cache
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

FS = 256.0
WIN_SEC = 4.0
STEP_SEC = 4.0
ARTIFACT_MIN_OVERLAP = 0.5  # share of the window an artifact must cover
KEEP_R1_MIN_GAIN = 0.05
TUH_LINE_FREQ = 60.0  # TUH is a US rig
V1_FEATURES = ("v1_total", "v1_clip", "v1_line", "v1_hf")
V2_SIGNAL_FEATURES = (
    "drift_ratio", "drift_excess", "delta_ratio", "hf_ratio", "line_ratio", "line_prominence",
    "aperiodic_exponent", "aperiodic_r2", "alpha_peak", "kurtosis", "clip_fraction", "missing_fraction",
)
# Flat/missing channels have no spectral features; the indicator keeps them visible to the model.
V2_FEATURES = V2_SIGNAL_FEATURES + ("v2_flat",)
MAX_UNMATCHED_SHARE = 0.05  # csv channels that match no montage label -> labels are wrong

# Pre-registered drift calibration (2026-11-16, before any TUAR result was seen): on the
# calibration half of the patients, the drift ramp starts at the 95th percentile of
# drift_excess over clean, non-flat channel-windows; width and weight stay as designed.
SPLIT_SALT = "tuar-r1-2026-11-16"
DRIFT_QUANTILE = 0.95
DRIFT_RAMP_WIDTH = 0.8
DRIFT_WEIGHT = 0.6
_MONTAGE_RE = re.compile(r"^\s*montage\s*=\s*\d+\s*,\s*([^:]+?)\s*:\s*(.+?)\s*--\s*(.+?)\s*$")


@dataclass(frozen=True)
class ArtifactEvent:
    channel: str
    start: float
    stop: float
    label: str


@dataclass(frozen=True)
class BootstrapResult:
    auc_a: float
    auc_b: float
    diff: float  # auc_b - auc_a
    diff_ci: Tuple[float, float]


# --------------------------------------------------------------------------- parsing
def parse_tuar_csv(text: str) -> Tuple[ArtifactEvent, ...]:
    """Parse a TUH csv_v1.0.0 annotation file; background rows are dropped."""
    body = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not body or not body[0].lower().startswith("channel,"):
        raise ValueError("TUAR csv: missing 'channel,start_time,...' header line")
    events = []
    for row in csv.DictReader(io.StringIO("\n".join(body))):
        label = row["label"].strip().lower()
        if label == "bckg":
            continue
        events.append(
            ArtifactEvent(row["channel"].strip().upper(), float(row["start_time"]), float(row["stop_time"]), label)
        )
    return tuple(events)


def parse_montage(text: str) -> Tuple[Tuple[str, str, str], ...]:
    """``montage = i, A-B: EEG A-REF -- EEG B-REF`` lines -> (label, plus, minus)."""
    out = []
    for line in text.splitlines():
        m = _MONTAGE_RE.match(line)
        if m:
            out.append((m.group(1).strip().upper(), m.group(2).strip(), m.group(3).strip()))
    return tuple(out)


def patient_id(bname: str) -> str:
    return Path(bname).stem.split("_")[0]


def bipolar(
    data: np.ndarray, names: Sequence[str], montage: Sequence[Tuple[str, str, str]]
) -> Tuple[np.ndarray, Tuple[str, ...]]:
    """Bipolar derivations from referential channels; pairs with a missing channel are skipped."""
    index = {n.strip().upper(): i for i, n in enumerate(names)}
    rows, labels = [], []
    for label, plus, minus in montage:
        i, j = index.get(plus.upper()), index.get(minus.upper())
        if i is None or j is None:
            continue
        rows.append(data[i] - data[j])
        labels.append(label)
    out = np.stack(rows) if rows else np.zeros((0, data.shape[1]))
    return out, tuple(labels)


def unmatched_events(events: Sequence[ArtifactEvent], labels: Sequence[str]) -> int:
    """Events whose channel is not one of the derived bipolar labels (silently lost otherwise)."""
    known = {lab.upper() for lab in labels}
    return sum(e.channel not in known for e in events)


def _union_length(intervals: Sequence[Tuple[float, float]]) -> float:
    total, end = 0.0, -np.inf
    for a, b in sorted(intervals):
        if b <= end:
            continue
        total += b - max(a, end)
        end = b
    return total


def window_labels(
    events: Sequence[ArtifactEvent], channel: str, n_windows: int, win_sec: float, step_sec: float
) -> Tuple[np.ndarray, Tuple[str, ...]]:
    """Per window: 1 artifact, 0 clean, -1 ambiguous; plus the dominant artifact type.

    Coverage is the union of overlapping events, so simultaneous rows (eyem + musc on the
    same span) are not double counted.
    """
    ch_events = [e for e in events if e.channel == channel.upper()]
    labels = np.zeros(n_windows, dtype=int)
    kinds = []
    for w in range(n_windows):
        t0, t1 = w * step_sec, w * step_sec + win_sec
        clipped = [(max(t0, e.start), min(t1, e.stop), e.label) for e in ch_events]
        clipped = [(a, b, lab) for a, b, lab in clipped if b > a]
        total = _union_length([(a, b) for a, b, _ in clipped])
        cover: dict[str, float] = {}
        for lab in {lab for _, _, lab in clipped}:
            cover[lab] = _union_length([(a, b) for a, b, k in clipped if k == lab])
        if total == 0:
            kinds.append("")
        elif total >= ARTIFACT_MIN_OVERLAP * win_sec:
            labels[w] = 1
            kinds.append(max(cover, key=cover.get))
        else:
            labels[w] = -1
            kinds.append("")
    return labels, tuple(kinds)


# --------------------------------------------------------------------------- calibration
def split_patients(pids: Sequence[str]) -> Tuple[set, set]:
    """Deterministic ~50/50 patient split from a salted hash (independent of order and data)."""
    import hashlib

    calib, test = set(), set()
    for pid in set(pids):
        digest = hashlib.sha256(f"{SPLIT_SALT}:{pid}".encode()).digest()
        (calib if digest[0] % 2 == 0 else test).add(pid)
    return calib, test


def calibrate_drift_ramp(df, quantile: float = DRIFT_QUANTILE) -> Tuple[float, float, float]:
    """Drift ramp starting at the clean-window quantile of drift_excess (flat rows excluded)."""
    clean = df[(df["label"] == 0) & (df["v2_flat"] == 0)]["drift_excess"].dropna()
    if clean.empty:
        raise ValueError("no clean channel-windows to calibrate the drift ramp on")
    start = float(np.quantile(clean.to_numpy(float), quantile))
    return start, start + DRIFT_RAMP_WIDTH, DRIFT_WEIGHT


def rescore_with_reasons(df, config) -> Tuple[np.ndarray, np.ndarray]:
    """v2 channel scores and first reason ('' if none) recomputed from cached features."""
    import sqi_v2

    scores = np.empty(len(df))
    reasons = np.empty(len(df), dtype=object)
    for i, row in enumerate(df[list(V2_SIGNAL_FEATURES) + ["v2_flat"]].itertuples(index=False)):
        rec = row._asdict()
        if rec.pop("v2_flat"):
            scores[i], reasons[i] = 0.0, "flat"
            continue
        score, why = sqi_v2.score_features(rec, config)
        scores[i], reasons[i] = score, (why[0] if why else "")
    return scores, reasons.astype(str)


def rescore(df, config) -> np.ndarray:
    """v2 channel scores recomputed from cached features under ``config``."""
    return rescore_with_reasons(df, config)[0]


# --------------------------------------------------------------------------- E7/E8: guidance checks
# Which SQI v2 reasons are a correct description of each TUAR artifact type. Electrode
# artifacts (elec, elpp) show up as lost contact, pops or slow wander, so several fit.
_KIND_REASONS = {
    "musc": {"muscle"}, "chew": {"muscle"}, "shiv": {"muscle"},
    "eyem": {"transient", "drift"},
    "elec": {"flat", "drift", "transient", "clipping", "missing"},
    "elpp": {"flat", "drift", "transient", "clipping", "missing"},
}


def select_channels(labels: np.ndarray, keep_clean: float, rng: np.random.Generator) -> Tuple[np.ndarray, bool]:
    """Channels to store for one window, and whether the window is stored complete.

    Windows with any artifact keep every labelled channel (needed to check which channel the
    interface points at, E8). Clean-only windows are subsampled to keep the cache small.
    """
    labels = np.asarray(labels)
    valid = np.flatnonzero(labels >= 0)
    if (labels == 1).any() or not keep_clean:
        return valid, True
    return valid[rng.random(valid.size) < keep_clean], False


def expected_reasons(kind: str) -> frozenset:
    """Reasons that correctly describe a (possibly combined, e.g. 'eyem_musc') TUAR label."""
    out: set = set()
    for part in str(kind).split("_"):
        out |= _KIND_REASONS.get(part, set())
    return frozenset(out)


def reason_accuracy(kinds: np.ndarray, reasons: np.ndarray) -> dict:
    """E7: on artifact channel-windows, how often a reason is shown and whether it is right."""
    kinds, reasons = np.asarray(kinds, dtype=str), np.asarray(reasons, dtype=str)
    flagged = reasons != ""
    correct = np.array([r in expected_reasons(k) for k, r in zip(kinds, reasons)])
    confusion: dict = {}
    for k, r in zip(kinds, reasons):
        row = confusion.setdefault(k, {})
        row[r or "none"] = row.get(r or "none", 0) + 1
    return {
        "n": int(kinds.size),
        "flagged_share": float(flagged.mean()) if kinds.size else float("nan"),
        "correct_among_flagged": float(correct[flagged].mean()) if flagged.any() else float("nan"),
        "confusion": confusion,
    }


def localization(df, score_col: str) -> dict:
    """E8: in complete windows with both artifact and clean channels, is the lowest-scoring
    channel (the one the interface tells the operator to fix) an artifact channel?"""
    hits, chances, pids = [], [], []
    for _, g in df[df["full_window"] == 1].groupby(["rec", "window"]):
        if g["label"].nunique() < 2:
            continue
        hits.append(float(g.loc[g[score_col].idxmin(), "label"] == 1))
        chances.append(float(g["label"].mean()))
        pids.append(g["pid"].iloc[0])
    return {
        "n_windows": len(hits),
        "hit_rate": float(np.mean(hits)) if hits else float("nan"),
        "chance": float(np.mean(chances)) if chances else float("nan"),
        "_hits": np.array(hits), "_chances": np.array(chances), "_pids": np.array(pids),
    }


# --------------------------------------------------------------------------- statistics
def _auc(y: np.ndarray, s: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y, s))


def paired_patient_bootstrap(
    pids: np.ndarray, y: np.ndarray, score_a: np.ndarray, score_b: np.ndarray, n_boot: int = 2000, seed: int = 0
) -> BootstrapResult:
    """AUC of two scores on the same windows; CI of the difference by resampling patients."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(pids == p) for p in np.unique(pids)]
    diffs = []
    for _ in range(n_boot):
        idx = np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])
        if np.unique(y[idx]).size < 2:
            continue
        diffs.append(_auc(y[idx], score_b[idx]) - _auc(y[idx], score_a[idx]))
    auc_a, auc_b = _auc(y, score_a), _auc(y, score_b)
    lo, hi = np.percentile(diffs, [2.5, 97.5]) if diffs else (np.nan, np.nan)
    return BootstrapResult(auc_a, auc_b, auc_b - auc_a, (float(lo), float(hi)))


def fit_logistic(x: np.ndarray, y: np.ndarray):
    """Median-impute, quantile-normalise (robust to heavy tails), balanced logistic regression."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import QuantileTransformer

    model = make_pipeline(
        SimpleImputer(strategy="median", keep_empty_features=True),
        QuantileTransformer(n_quantiles=min(1000, len(y)), output_distribution="normal", random_state=0),
        LogisticRegression(class_weight="balanced", max_iter=1000),
    )
    return model.fit(x, y)


def grouped_cv_scores(
    x: np.ndarray, y: np.ndarray, pids: np.ndarray, n_folds: int = 5, seed: int = 0, fit: Callable = fit_logistic
) -> Tuple[np.ndarray, list]:
    """Out-of-fold P(artifact); no patient is ever in both train and test."""
    from sklearn.model_selection import StratifiedGroupKFold

    n_folds = min(n_folds, len(np.unique(pids)))
    scores = np.full(y.shape, np.nan)
    folds = list(StratifiedGroupKFold(n_folds, shuffle=True, random_state=seed).split(x, y, pids))
    for tr, te in folds:
        scores[te] = fit(x[tr], y[tr]).predict_proba(x[te])[:, 1]
    return scores, folds


# --------------------------------------------------------------------------- extraction
def _montage_for(edf: Path, tuar_root: Path) -> Tuple[Tuple[str, str, str], ...]:
    docs = tuar_root / "DOCS" / f"{edf.parent.name}_montage.txt"
    if not docs.exists():
        raise FileNotFoundError(f"montage file not found: {docs}")
    return parse_montage(docs.read_text(encoding="utf-8", errors="replace"))


def _v1_subwindows(win: np.ndarray, cfg) -> list:
    """compute_sqi on consecutive 1 s sub-windows of a (channels, samples) window, as deployed."""
    import eeg_stroke_pipeline as P

    n = int(FS)
    return [P.compute_sqi(win[:, k : k + n], FS, cfg) for k in range(0, win.shape[1] - n + 1, n)]


def _v1_channel(win: np.ndarray, cfg) -> dict:
    """v1 features of one channel, averaged over 1 s sub-windows."""
    subs = _v1_subwindows(win[None, :], cfg)
    return {
        "v1_total": float(np.mean([s["sqi_total"] for s in subs])),
        "v1_clip": float(np.mean([s["sqi_clip"] for s in subs])),
        "v1_line": float(np.mean([s["sqi_line_ratio"] for s in subs])),
        "v1_hf": float(np.mean([s["sqi_hf_ratio"] for s in subs])),
    }


def _window_label(per_ch: dict, labels: Sequence[str], w: int) -> int:
    marks = [per_ch[ch][0][w] for ch in labels]
    if any(m == 1 for m in marks):
        return 1
    return 0 if all(m == 0 for m in marks) else -1


def safe_extract(args: Tuple[str, str, float, int]) -> dict:
    """extract_recording that never raises: one corrupt EDF must not kill a long run."""
    try:
        return extract_recording(args)
    except Exception as exc:  # noqa: BLE001 - logged per recording and reported at the end
        return {"rec": Path(args[0]).stem, "rows": [], "n_events": 0, "n_unmatched": 0, "error": repr(exc)}


def extract_recording(args: Tuple[str, str, float, int]) -> dict:
    """Feature rows plus label-matching counts for one EDF (runs in a worker process)."""
    import mne

    import eeg_stroke_pipeline as P
    import sqi_v2

    edf_path, tuar_root, keep_clean, seed = Path(args[0]), Path(args[1]), args[2], args[3]
    events = parse_tuar_csv(edf_path.with_suffix(".csv").read_text(encoding="utf-8", errors="replace"))
    raw = mne.io.read_raw_edf(edf_path, preload=True, verbose="ERROR")
    if abs(raw.info["sfreq"] - FS) > 1e-6:
        raw.resample(FS, verbose="ERROR")
    data, labels = bipolar(raw.get_data(), raw.ch_names, _montage_for(edf_path, tuar_root))
    summary = {"rec": edf_path.stem, "n_events": len(events), "n_unmatched": unmatched_events(events, labels), "error": None}
    if not labels:
        return {**summary, "rows": [], "error": "no montage channel found in EDF"}
    cfg = P.PipelineConfig(fs=FS, notch_freq=TUH_LINE_FREQ)
    v1_input = P.preprocess_eeg_for_sqi(data, FS, cfg)
    v2_cfg = sqi_v2.SqiV2Config(line_freq=TUH_LINE_FREQ)
    win, step = int(WIN_SEC * FS), int(STEP_SEC * FS)
    n_win = (data.shape[1] - win) // step + 1
    per_ch = {ch: window_labels(events, ch, n_win, WIN_SEC, STEP_SEC) for ch in labels}
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(n_win):
        wanted, full = select_channels(np.array([per_ch[ch][0][w] for ch in labels]), keep_clean, rng)
        if not wanted.size:
            continue
        sl = slice(w * step, w * step + win)
        quality = sqi_v2.assess_window(data[:, sl], FS, channel_names=labels, config=v2_cfg)
        v1_window = float(np.mean([s["sqi_total"] for s in _v1_subwindows(v1_input[:, sl], cfg)]))
        for c in wanted:
            ch, cq = labels[c], quality.channels[c]
            rows.append({
                "rec": edf_path.stem, "pid": patient_id(edf_path.stem), "montage": edf_path.parent.name,
                "channel": ch, "window": w, "full_window": int(full),
                "label": int(per_ch[ch][0][w]), "kind": per_ch[ch][1][w],
                "win_label": _window_label(per_ch, labels, w), "v1_window": v1_window, "v2_window": quality.score,
                "v2_score": cq.score, "v2_flat": int(bool({"flat", "missing"} & set(cq.reasons))),
                **_v1_channel(v1_input[c, sl], cfg),
                **{k: cq.features.get(k, np.nan) for k in V2_SIGNAL_FEATURES},
            })
    return {**summary, "rows": rows}


# --------------------------------------------------------------------------- evaluation
def _result_dict(r: BootstrapResult) -> dict:
    return {"auc_v1": r.auc_a, "auc_v2": r.auc_b, "diff": r.diff, "diff_ci95": list(r.diff_ci)}


def _per_kind(df, pids: np.ndarray, y: np.ndarray, s1: np.ndarray, s2: np.ndarray, n_boot: int, seed: int) -> dict:
    out = {}
    for kind in sorted(k for k in df["kind"].unique() if k):
        m = ((df["label"] == 0) | (df["kind"] == kind)).to_numpy()
        n_art = int((df.loc[m, "label"] == 1).sum())
        if df.loc[m, "pid"].nunique() >= 5 and n_art >= 20:
            r = paired_patient_bootstrap(pids[m], y[m], s1[m], s2[m], n_boot, seed)
            out[kind] = {**_result_dict(r), "n_artifact": n_art}
    return out


def evaluate(df, n_boot: int, seed: int) -> dict:
    y, pids = df["label"].to_numpy(), df["pid"].to_numpy()
    fixed = paired_patient_bootstrap(pids, y, 1 - df["v1_total"].to_numpy(), 1 - df["v2_score"].to_numpy(), n_boot, seed)
    s1, _ = grouped_cv_scores(df[list(V1_FEATURES)].to_numpy(float), y, pids, seed=seed)
    s2, _ = grouped_cv_scores(df[list(V2_FEATURES)].to_numpy(float), y, pids, seed=seed)
    learned = paired_patient_bootstrap(pids, y, s1, s2, n_boot, seed)
    win = df[df["win_label"] >= 0].drop_duplicates(["rec", "window"])
    window = paired_patient_bootstrap(
        win["pid"].to_numpy(), win["win_label"].to_numpy(),
        1 - win["v1_window"].to_numpy(), 1 - win["v2_window"].to_numpy(), n_boot, seed,
    )
    return {
        "n_rows": int(len(df)), "n_artifact": int(y.sum()),
        "n_patients": int(df["pid"].nunique()), "n_recordings": int(df["rec"].nunique()),
        "channel_fixed": _result_dict(fixed),
        "channel_learned": _result_dict(learned),
        "per_kind_oof": _per_kind(df, pids, y, s1, s2, n_boot, seed),
        "window_fixed": {**_result_dict(window), "n_windows": int(len(win))},
        "keep_r1": bool(learned.diff >= KEEP_R1_MIN_GAIN),
        "keep_r1_ci_lower": bool(learned.diff_ci[0] >= KEEP_R1_MIN_GAIN),
        "drop_rule": f"keep R1 iff learned channel AUC(v2) - AUC(v1) >= {KEEP_R1_MIN_GAIN} (point estimate)",
    }


def parse_rsync_listing(text: str) -> dict:
    """{relative path: size in bytes} from an ``rsync --list-only`` listing (files only)."""
    sizes = {}
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) == 5 and parts[0].startswith("-"):
            sizes[parts[4].strip()] = int(parts[1].replace(",", ""))
    return sizes


def complete_edfs(root: Path, sizes: dict) -> List[Path]:
    """EDFs that exist locally with exactly the size the server lists (fully downloaded)."""
    out = []
    for p in sorted((root / "edf").glob("*/*.edf")):
        rel = p.relative_to(root).as_posix()
        if rel in sizes and p.stat().st_size == sizes[rel]:
            out.append(p)
    return out


def rec_seed(rec_name: str, base: int) -> int:
    """Subsampling seed from the recording name, so results do not depend on run order."""
    import hashlib

    return int(hashlib.sha256(f"{base}:{rec_name}".encode()).hexdigest()[:8], 16)


def _extract_all(root: Path, cache: Path, keep_clean: float, limit: int, workers: int, seed: int,
                 sizes: Optional[dict] = None, resume: bool = False) -> None:
    from concurrent.futures import ProcessPoolExecutor

    import pandas as pd

    edfs = complete_edfs(root, sizes) if sizes else sorted((root / "edf").glob("*/*.edf"))
    previous = pd.DataFrame()
    if resume and cache.exists():
        previous = pd.read_csv(cache)
        done = set(previous["rec"].astype(str))
        edfs = [e for e in edfs if e.stem not in done]
        print(f"resume: {len(done)} recordings already cached, {len(edfs)} to extract", flush=True)
    edfs = edfs[: limit or None]
    if not edfs:
        if previous.empty:
            raise SystemExit(f"no EDF files under {root / 'edf'}")
        return
    jobs = [(str(e), str(root), keep_clean, rec_seed(e.stem, seed)) for e in edfs]
    rows: list = []
    log: list = []
    with ProcessPoolExecutor(workers) as pool:
        for i, out in enumerate(pool.map(safe_extract, jobs), 1):
            rows.extend(out.pop("rows"))
            log.append(out)
            note = f" ERROR {out['error']}" if out["error"] else ""
            print(f"[{i}/{len(jobs)}] {out['rec']} rows={len(rows)}{note}", flush=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([previous, pd.DataFrame(rows)], ignore_index=True).to_csv(cache, index=False)
    log_path = cache.with_suffix(".log.json")
    if resume and log_path.exists():
        # failed recordings are not in the cache, so they are retried; keep the latest entry
        merged = {r["rec"]: r for r in json.loads(log_path.read_text(encoding="utf-8"))["recordings"]}
        merged.update({r["rec"]: r for r in log})
        log = list(merged.values())
    n_events = sum(r["n_events"] for r in log)
    n_unmatched = sum(r["n_unmatched"] for r in log)
    report = {
        "n_recordings": len(log), "n_errors": sum(bool(r["error"]) for r in log),
        "n_events": n_events, "n_unmatched_events": n_unmatched, "recordings": log,
    }
    cache.with_suffix(".log.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"errors={report['n_errors']} unmatched events={n_unmatched}/{n_events}", flush=True)
    if n_events and n_unmatched / n_events > MAX_UNMATCHED_SHARE:
        raise SystemExit(
            f"{n_unmatched}/{n_events} annotation channels match no montage label: labels would be wrong. "
            f"See {cache.with_suffix('.log.json')}."
        )


def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tuar-root", default="F:/tuh_data/tuar")
    ap.add_argument("--cache", default=str(ROOT / "results" / "tuar_sqi_features.csv"))
    ap.add_argument("--out", default=str(ROOT / "results" / "tuar_sqi_eval.json"))
    ap.add_argument("--calibration", default=str(ROOT / "results" / "sqi_v2_calibration.json"))
    ap.add_argument("--keep-clean", type=float, default=0.25, help="share of clean channel-windows kept (0 = all)")
    ap.add_argument("--limit", type=int, default=0, help="only the first N recordings (smoke test)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-only", action="store_true")
    ap.add_argument("--sizes", help="rsync --list-only listing: extract only fully downloaded EDFs")
    ap.add_argument("--resume", action="store_true", help="keep the cache and extract only new recordings")
    ap.add_argument("--extract-only", action="store_true", help="update the cache without evaluating")
    args = ap.parse_args()

    cache = Path(args.cache)
    if not args.eval_only:
        sizes = parse_rsync_listing(Path(args.sizes).read_text(encoding="utf-8")) if args.sizes else None
        _extract_all(Path(args.tuar_root), cache, args.keep_clean, args.limit, args.workers, args.seed,
                     sizes=sizes, resume=args.resume)
        if args.extract_only:
            return
    df = pd.read_csv(cache)
    df["kind"] = df["kind"].fillna("")
    df = df[df["label"] >= 0].reset_index(drop=True)
    result = calibrate_then_evaluate(df, Path(args.calibration), args.n_boot, args.seed)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def _patient_mean_ci(pids: np.ndarray, values: np.ndarray, n_boot: int, seed: int) -> Tuple[float, float]:
    """95% CI of a mean over windows, resampling patients."""
    rng = np.random.default_rng(seed)
    groups = [np.flatnonzero(pids == p) for p in np.unique(pids)]
    if not groups:
        return float("nan"), float("nan")
    means = [
        float(values[np.concatenate([groups[k] for k in rng.integers(0, len(groups), len(groups))])].mean())
        for _ in range(n_boot)
    ]
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def _localization_report(test, n_boot: int, seed: int) -> dict:
    """E8 for v2 (calibrated) and v1 on the same windows, with patient-bootstrap CIs."""
    v2, v1 = localization(test, "v2_score"), localization(test, "v1_total")
    out: dict = {"n_windows": v2["n_windows"], "chance": v2["chance"]}
    if not v2["n_windows"]:
        return out
    pids = v2["_pids"]
    for name, loc in (("v2", v2), ("v1", v1)):
        out[name] = {
            "hit_rate": loc["hit_rate"],
            "hit_minus_chance_ci95": list(_patient_mean_ci(pids, loc["_hits"] - loc["_chances"], n_boot, seed)),
        }
    out["v2_minus_v1_ci95"] = list(_patient_mean_ci(pids, v2["_hits"] - v1["_hits"], n_boot, seed))
    return out


def calibrate_then_evaluate(df, calibration_path: Path, n_boot: int, seed: int) -> dict:
    """Fit the drift ramp on the calibration half, freeze it to disk, evaluate on the test half."""
    import sqi_v2

    calib_pids, test_pids = split_patients(df["pid"].unique())
    ramp = calibrate_drift_ramp(df[df["pid"].isin(calib_pids)])
    frozen = {
        "drift_ramp": list(ramp),
        "fitted_on": "TUAR v3.0.1 calibration half",
        "split_salt": SPLIT_SALT, "quantile": DRIFT_QUANTILE,
        "n_calib_patients": len(calib_pids), "n_test_patients": len(test_pids),
    }
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(json.dumps(frozen, indent=2), encoding="utf-8")

    test = df[df["pid"].isin(test_pids)].reset_index(drop=True)
    default_fixed = paired_patient_bootstrap(
        test["pid"].to_numpy(), test["label"].to_numpy(),
        1 - test["v1_total"].to_numpy(), 1 - test["v2_score"].to_numpy(), n_boot, seed,
    )
    scores, reasons = rescore_with_reasons(
        test, sqi_v2.config_from_dict({"drift_ramp": list(ramp), "line_freq": TUH_LINE_FREQ})
    )
    test = test.assign(v2_score=scores, v2_reason=reasons)
    result = evaluate(test, n_boot, seed)
    artifacts = test[test["label"] == 1]
    return {
        **result,
        "reason_accuracy_e7": reason_accuracy(artifacts["kind"].to_numpy(), artifacts["v2_reason"].to_numpy()),
        "localization_e8": _localization_report(test, n_boot, seed),
        "evaluated_on": "TUAR test half (patients disjoint from calibration)",
        "calibration": frozen,
        "channel_fixed_default_config": _result_dict(default_fixed),
        "note_window_fixed": "window-level v2 uses the default (uncalibrated) config from extraction",
    }


if __name__ == "__main__":
    main()
