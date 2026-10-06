"""Convert the TUH EEG Slowing Corpus (TUSL) into the project's npz+manifest format.

Goal
----
Produce a SAME-RIG labeled feature table so the ischemic-vs-non-stroke acquisition
confound (clinical rig == label) can be broken. TUSL recordings all come from the
single TUH clinical EEG system, so a slowing-vs-background task on them carries no
cross-cohort site signature. `01_tcp_ar` EDFs store referential channels
("EEG C3-REF" ...) that canonicalize straight onto the training montage
(`DEFAULT_CHANNELS`), so the extracted features are directly comparable.

Task framing (honest)
----------------------
  positive (1) = `slow`  -- focal/generalized slowing, an EEG proxy for a lesion
  negative (0) = `bckg`  -- complex background (non-slowing)
  `seiz` segments are excluded by default (different phenomenon, not a lesion proxy).

This is "focal-abnormality vs background on one rig", NOT "ischemic stroke". It is a
mechanistic sanity check that the entropy/MFDFA pipeline sees real pathology, not a
site fingerprint.

Pipeline
--------
  1. `tusl_to_npz.py --scan-only`  -> viability report (runs without EDFs; needs only
     the `.tse_agg` annotation files that rsync already fetched).
  2. `tusl_to_npz.py`              -> writes per-segment npz + `manifest_tuh.csv`
     (requires the EDFs to be downloaded).
  3. `build_feature_table.py --manifest dataset_tuh/manifest_tuh.csv \
        --out dataset_tuh/feature_table_tuh.csv`     (existing script, no changes).
  4. `diagnose_source_confound.py --combined-csv dataset_tuh/feature_table_tuh.csv`
     -> same-rig macro-F1 / AUC. Patient ids are `tuh_*` so the source rule already
     tags them `tuh_samerig`.

Usage
-----
  .venv/Scripts/python.exe scripts/tusl_to_npz.py --scan-only
  .venv/Scripts/python.exe scripts/tusl_to_npz.py \
      --tusl-root F:/tuh_data/tusl --out-dir dataset_tuh
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_BACKEND = str(ROOT / "backend")

# Default same-rig two-class mapping. seiz -> excluded (None).
POSITIVE_LABELS = {"slow"}
NEGATIVE_LABELS = {"bckg"}


@dataclass(frozen=True)
class Segment:
    """One term-based annotation: [start, stop) seconds with a class label."""
    start_sec: float
    stop_sec: float
    label: str


def parse_tse_agg(text: str) -> list[Segment]:
    """Parse a `.tse`/`.tse_agg` file body into segments.

    Format (after a `version = ...` header and blank lines):
        294.0000 304.0000 slow 1.0000
    Fields: start_sec stop_sec label probability. Malformed lines are skipped.
    """
    segments: list[Segment] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("version") or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            start = float(parts[0])
            stop = float(parts[1])
        except ValueError:
            continue
        if stop <= start:
            continue
        segments.append(Segment(start, stop, parts[2].lower()))
    return segments


def label_for(seg_label: str) -> int | None:
    """Map a segment label to 1 (positive), 0 (negative), or None (excluded)."""
    if seg_label in POSITIVE_LABELS:
        return 1
    if seg_label in NEGATIVE_LABELS:
        return 0
    return None


def patient_code_from_path(edf_or_ann: Path, tusl_root: Path) -> str:
    """Return the TUSL patient code (e.g. 'aaaaaaju') from a file under edf/<code>/..."""
    rel = edf_or_ann.resolve().relative_to((tusl_root / "edf").resolve())
    return rel.parts[0]


def iter_agg_annotations(tusl_root: Path):
    """Yield (tse_agg_path, edf_path, patient_code) for every aggregated annotation.

    The EDF may or may not exist yet; callers that only need labels can ignore it.
    """
    edf_root = tusl_root / "edf"
    for agg in sorted(edf_root.rglob("*.tse_agg")):
        edf_path = agg.with_suffix(".edf")
        yield agg, edf_path, patient_code_from_path(agg, tusl_root)


def scan(tusl_root: Path) -> dict:
    """Walk the annotation tree and summarise class balance and patient coverage."""
    from collections import Counter, defaultdict

    per_patient: dict[str, Counter] = defaultdict(Counter)
    total = Counter()
    n_agg = 0
    n_edf_present = 0
    for agg, edf_path, code in iter_agg_annotations(tusl_root):
        n_agg += 1
        if edf_path.exists():
            n_edf_present += 1
        for seg in parse_tse_agg(agg.read_text(encoding="utf-8", errors="ignore")):
            lab = label_for(seg.label)
            if lab is None:
                total[seg.label + " (excluded)"] += 1
                continue
            key = "pos(slow)" if lab == 1 else "neg(bckg)"
            per_patient[code][key] += 1
            total[key] += 1

    patients_with_both = sum(
        1 for c in per_patient.values() if c["pos(slow)"] > 0 and c["neg(bckg)"] > 0
    )
    return {
        "tusl_root": str(tusl_root),
        "n_agg_files": n_agg,
        "n_edf_present": n_edf_present,
        "n_patients_labeled": len(per_patient),
        "patients_with_both_classes": patients_with_both,
        "segment_totals": dict(total),
        "per_patient": {k: dict(v) for k, v in sorted(per_patient.items())},
    }


def _write_segment_npz(raw, seg: Segment, out_path: Path) -> float:
    """Slice `raw` (an mne Raw) to [start, stop) and save an npz. Returns fs."""
    import numpy as np

    fs = float(raw.info["sfreq"])
    start_i = int(round(seg.start_sec * fs))
    stop_i = int(round(seg.stop_sec * fs))
    data = raw.get_data(start=start_i, stop=stop_i)  # (n_ch, n_samples)
    channels = list(raw.ch_names)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, data=data.astype("float32"),
                        channels=np.array(channels), fs=fs)
    return fs


def convert(tusl_root: Path, out_dir: Path) -> Path:
    """Read EDFs + annotations, write per-segment npz and a manifest CSV."""
    import mne
    import pandas as pd

    mne.set_log_level("ERROR")
    npz_dir = out_dir / "npz"
    rows: list[dict] = []
    n_missing_edf = 0

    for agg, edf_path, code in iter_agg_annotations(tusl_root):
        if not edf_path.exists():
            n_missing_edf += 1
            continue
        segments = [s for s in parse_tse_agg(agg.read_text(encoding="utf-8",
                                                            errors="ignore"))
                    if label_for(s.label) is not None]
        if not segments:
            continue
        raw = mne.io.read_raw_edf(edf_path, preload=True, verbose="ERROR")
        stem = edf_path.stem
        for i, seg in enumerate(segments):
            npz_path = npz_dir / code / f"{stem}_seg{i:02d}.npz"
            fs = _write_segment_npz(raw, seg, npz_path)
            rows.append({
                "patient_id": f"tuh_{code}",
                "label": label_for(seg.label),
                "path": str(npz_path),
                "fs": fs,
            })

    if not rows:
        raise SystemExit(
            f"No segments written. EDFs missing for all {n_missing_edf} annotation "
            f"files under {tusl_root/'edf'} -- download the TUSL EDFs first "
            f"(see docs/tuh_samerig.md)."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest_tuh.csv"
    pd.DataFrame(rows).to_csv(manifest_path, index=False)
    n_pos = sum(r["label"] == 1 for r in rows)
    n_neg = sum(r["label"] == 0 for r in rows)
    print(f"Wrote {len(rows)} segment rows ({n_pos} slow / {n_neg} bckg) "
          f"across {len({r['patient_id'] for r in rows})} patients")
    print(f"Manifest -> {manifest_path}")
    return manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tusl-root", default="F:/tuh_data/tusl",
                        help="TUSL corpus root (contains edf/ and AAREADME.txt)")
    parser.add_argument("--out-dir", default=str(ROOT / "dataset_tuh"))
    parser.add_argument("--scan-only", action="store_true",
                        help="Report class balance from annotations; do not read EDFs")
    args = parser.parse_args()

    tusl_root = Path(args.tusl_root)
    if not (tusl_root / "edf").exists():
        print(f"ERROR: {tusl_root/'edf'} not found.", file=sys.stderr)
        sys.exit(1)

    if args.scan_only:
        import json
        report = scan(tusl_root)
        summary = {k: v for k, v in report.items() if k != "per_patient"}
        print(json.dumps(summary, indent=2))
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "tusl_scan.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nFull per-patient breakdown -> {out_dir/'tusl_scan.json'}")
        return

    sys.path.insert(0, _BACKEND)
    convert(tusl_root, Path(args.out_dir))


if __name__ == "__main__":
    main()
