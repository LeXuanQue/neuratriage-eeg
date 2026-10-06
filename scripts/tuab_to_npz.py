"""Convert the TUH EEG Abnormal Corpus (TUAB) into the project's npz+manifest format.

Goal
----
Scale up the same-rig, confound-free evaluation started with TUSL. TUAB is ~15x
larger (2,993 recordings / ~2,383 subjects) and comes from the SAME TUH clinical
EEG system, so a normal-vs-abnormal task on it carries no cross-cohort site
signature -- exactly what is needed to obtain a macro-F1 with real statistical
weight (unlike TUSL's small-N mechanistic check). Like TUSL it uses the
`01_tcp_ar` referential montage ("EEG C3-REF" ...), which canonicalizes straight
onto the training `DEFAULT_CHANNELS`, so features are directly comparable.

Task framing (honest)
----------------------
  positive (1) = `abnormal`  -- a recording flagged pathological by the reading
                               neurologist (a broad pathology proxy, NOT ischemic
                               stroke specifically).
  negative (0) = `normal`    -- a recording read as normal.

This is "abnormal vs normal EEG on one rig". It answers the same question TUSL
does -- does the entropy/MFDFA pipeline track real pathology rather than an
acquisition fingerprint -- but at a scale where the number is defensible.

Label source
------------
TUAB encodes the label in the DIRECTORY PATH (`.../normal/...` vs
`.../abnormal/...`), not in a separate annotation file. The whole recording gets
one label. We therefore crop a fixed, comparable window per recording
(`--skip-sec` seconds in, `--dur-sec` long) rather than slicing annotated
segments. TUH's official train/eval split is ignored: everything is pooled and the
downstream diagnose script does its own patient-level GroupKFold.

Pipeline
--------
  1. `tuab_to_npz.py --scan-only`  -> label balance + subject coverage (needs the
     EDFs on disk; TUAB has no separate annotation files to scan).
  2. `tuab_to_npz.py`              -> per-recording cropped npz + `manifest_tuab.csv`.
  3. `build_feature_table.py --manifest dataset_tuab/manifest_tuab.csv \
        --out dataset_tuab/feature_table_tuab.csv`     (existing script, no changes).
  4. `diagnose_source_confound.py --combined-csv dataset_tuab/feature_table_tuab.csv`
     -> same-rig macro-F1 / AUC. Patient ids are `tuh_*` so the source rule already
     tags them `tuh_samerig`.

Usage
-----
  .venv/Scripts/python.exe scripts/tuab_to_npz.py --scan-only
  .venv/Scripts/python.exe scripts/tuab_to_npz.py \
      --tuab-root F:/tuh_data/tuab --out-dir dataset_tuab --skip-sec 60 --dur-sec 60
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_BACKEND = str(ROOT / "backend")

# Label directory components. NOTE: "abnormal" must be tested as an exact path
# COMPONENT (not a substring) because "normal" is a substring of "abnormal".
POSITIVE_DIR = "abnormal"  # -> 1
NEGATIVE_DIR = "normal"    # -> 0

# Recordings shorter than this (after cropping) are skipped: too short for the
# MFDFA window to produce any feature row.
MIN_SEGMENT_SEC = 8.0


def label_from_path(path_parts) -> int | None:
    """Map an EDF's path components to 1 (abnormal), 0 (normal), or None.

    Matches on exact directory components so that "normal" does not accidentally
    match inside "abnormal".
    """
    lowered = [str(p).lower() for p in path_parts]
    if POSITIVE_DIR in lowered:
        return 1
    if NEGATIVE_DIR in lowered:
        return 0
    return None


def subject_from_edf(edf_path: Path) -> str:
    """Return the TUH subject code from a TUAB EDF filename.

    TUH filenames follow `<subject>_<session>_<token>.edf`, e.g.
    `aaaaaaav_s004_t000.edf` -> `aaaaaaav`.
    """
    return edf_path.stem.split("_")[0]


def iter_edfs(tuab_root: Path):
    """Yield (edf_path, label, subject) for every labeled EDF under the root."""
    for edf in sorted(tuab_root.rglob("*.edf")):
        label = label_from_path(edf.relative_to(tuab_root).parts)
        if label is None:
            continue
        yield edf, label, subject_from_edf(edf)


def scan(tuab_root: Path) -> dict:
    """Summarise label balance and subject coverage across the corpus."""
    from collections import Counter, defaultdict

    per_subject: dict[str, Counter] = defaultdict(Counter)
    total = Counter()
    n_edf = 0
    for _edf, label, subject in iter_edfs(tuab_root):
        n_edf += 1
        key = "pos(abnormal)" if label == 1 else "neg(normal)"
        per_subject[subject][key] += 1
        total[key] += 1

    subjects_with_both = sum(
        1 for c in per_subject.values()
        if c["pos(abnormal)"] > 0 and c["neg(normal)"] > 0
    )
    return {
        "tuab_root": str(tuab_root),
        "n_edf_labeled": n_edf,
        "n_subjects": len(per_subject),
        "subjects_with_both_labels": subjects_with_both,
        "recording_totals": dict(total),
        "per_subject": {k: dict(v) for k, v in sorted(per_subject.items())},
    }


def _write_cropped_npz(raw, skip_sec: float, dur_sec: float,
                       out_path: Path) -> float | None:
    """Crop `raw` to [skip, skip+dur) seconds and save an npz. Returns fs or None.

    If the recording is shorter than `skip_sec`, crop from its start instead. If
    the resulting segment is shorter than MIN_SEGMENT_SEC, skip (return None).
    """
    import numpy as np

    fs = float(raw.info["sfreq"])
    n = int(raw.n_times)
    start_i = int(round(skip_sec * fs))
    if start_i >= n:  # recording shorter than the skip -> take from the start
        start_i = 0
    stop_i = min(int(round((skip_sec + dur_sec) * fs)), n) if start_i else \
        min(int(round(dur_sec * fs)), n)
    if (stop_i - start_i) / fs < MIN_SEGMENT_SEC:
        return None

    data = raw.get_data(start=start_i, stop=stop_i)  # (n_ch, n_samples)
    channels = list(raw.ch_names)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, data=data.astype("float32"),
                        channels=np.array(channels), fs=fs)
    return fs


def convert(tuab_root: Path, out_dir: Path, skip_sec: float,
            dur_sec: float) -> Path:
    """Read each EDF, crop a comparable window, write per-recording npz + manifest."""
    import mne
    import pandas as pd

    mne.set_log_level("ERROR")
    npz_dir = out_dir / "npz"
    rows: list[dict] = []
    n_skipped_short = 0

    for i, (edf, label, subject) in enumerate(iter_edfs(tuab_root)):
        raw = mne.io.read_raw_edf(edf, preload=True, verbose="ERROR")
        npz_path = npz_dir / subject / f"{edf.stem}.npz"
        fs = _write_cropped_npz(raw, skip_sec, dur_sec, npz_path)
        if fs is None:
            n_skipped_short += 1
            continue
        rows.append({
            "patient_id": f"tuh_{subject}",
            "label": label,
            "path": str(npz_path),
            "fs": fs,
        })
        if (i + 1) % 200 == 0:
            print(f"  ...{i + 1} EDFs processed ({len(rows)} written)", flush=True)

    if not rows:
        raise SystemExit(
            f"No recordings written from {tuab_root}. Are the TUAB EDFs downloaded "
            f"and laid out as .../<normal|abnormal>/.../*.edf? "
            f"(see docs/tuh_samerig.md)."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest_tuab.csv"
    pd.DataFrame(rows).to_csv(manifest_path, index=False)
    n_pos = sum(r["label"] == 1 for r in rows)
    n_neg = sum(r["label"] == 0 for r in rows)
    print(f"Wrote {len(rows)} recording rows ({n_pos} abnormal / {n_neg} normal) "
          f"across {len({r['patient_id'] for r in rows})} subjects "
          f"({n_skipped_short} skipped: too short)")
    print(f"Manifest -> {manifest_path}")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tuab-root", default="F:/tuh_data/tuab",
                        help="TUAB corpus root (contains edf/ with normal|abnormal)")
    parser.add_argument("--out-dir", default=str(ROOT / "dataset_tuab"))
    parser.add_argument("--skip-sec", type=float, default=60.0,
                        help="Seconds to skip at recording start (setup artifacts)")
    parser.add_argument("--dur-sec", type=float, default=60.0,
                        help="Seconds of signal to keep per recording")
    parser.add_argument("--scan-only", action="store_true",
                        help="Report label balance from paths; do not read signals")
    args = parser.parse_args()

    tuab_root = Path(args.tuab_root)
    if not tuab_root.exists():
        print(f"ERROR: {tuab_root} not found.", file=sys.stderr)
        sys.exit(1)

    if args.scan_only:
        import json
        report = scan(tuab_root)
        summary = {k: v for k, v in report.items() if k != "per_subject"}
        print(json.dumps(summary, indent=2))
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "tuab_scan.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nFull per-subject breakdown -> {out_dir/'tuab_scan.json'}")
        return

    sys.path.insert(0, _BACKEND)
    convert(tuab_root, Path(args.out_dir), args.skip_sec, args.dur_sec)


if __name__ == "__main__":
    main()
