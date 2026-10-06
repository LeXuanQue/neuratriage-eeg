"""Convert the two extra sources for the leave-source-out experiment to pipeline npz.

  Oslo ds003775 (OpenNeuro)   : healthy adults, BioSemi 64 ch, 4 min eyes-closed rest
                                -> one npz per subject, patient_id "os-XXX", label non-stroke
  Tianjin 30509165 (figshare) : 24 chronic stroke (15 IS + 9 HS; per-subject type NOT
                                published), Neuracle 64 ch, run "pre_01" only
                                -> one npz per rest segment (event "1" .. next event),
                                   patient_id "tj-XX", label "ischemic" = stroke class

Output npz = {data (18, n) float32 uV, channels, fs=256} + manifest_<source>.csv
(patient_id,label,path,fs), the same schema as the existing datasets.

Usage (experiment venv on F:, it has mne):
  F:/eeg_extra/.venv_dl/Scripts/python.exe scripts/convert_multisource.py \
      --oslo-dir F:/eeg_extra/oslo_ds003775 --tianjin-dir F:/eeg_extra/tianjin_30509165/raw \
      --out-root F:/eeg_extra/npz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from eeg_stroke_pipeline import (  # noqa: E402
    DEFAULT_CHANNELS,
    canonicalize_channel_name,
    reorder_to_target_channels,
)

TARGET_FS = 256.0


def rest_segments(types: Sequence[str], onsets_s: Sequence[float], fs: float, n_samples: int,
                  min_sec: float = 4.0) -> list[tuple[int, int]]:
    """(start, end) sample ranges from each rest onset ('1') to the next real event."""
    events = [(str(t), float(o)) for t, o in zip(types, onsets_s) if str(t) != "boundary"]
    segs = []
    for i, (kind, onset) in enumerate(events):
        if kind != "1":
            continue
        start = int(round(onset * fs))
        end = int(round(events[i + 1][1] * fs)) if i + 1 < len(events) else n_samples
        if end - start >= min_sec * fs:
            segs.append((start, end))
    return segs


def pick_target_channels(data: np.ndarray, labels: Sequence[str]) -> tuple[np.ndarray, list[str]]:
    """Reorder to the 18-ch training montage; missing channels come back as NaN rows."""
    have = {canonicalize_channel_name(c) for c in labels}
    missing = [c for c in DEFAULT_CHANNELS if canonicalize_channel_name(c) not in have]
    return reorder_to_target_channels(data, list(labels), DEFAULT_CHANNELS), missing


def uv_scale(edf_units: Sequence[str], bids_units: Sequence[str] | None) -> float:
    """Factor turning mne's get_data() into microvolts.

    mne converts recognised EDF units to volts. When the header unit is missing
    ('n/a', as in ds003775) it returns the stored numbers unchanged; BIDS
    channels.tsv then tells us they are already microvolts.
    """
    header_has_unit = any(str(u).strip().lower() not in ("", "n/a", "na") for u in edf_units)
    if not header_has_unit and bids_units and all(str(u).strip().lower() in ("uv", "µv", "microv") for u in bids_units):
        return 1.0
    return 1e6


def fix_edf_start_time(src: Path, dst: Path) -> Path:
    """Copy an EDF, clamping an invalid header start time (e.g. second = 60) to a legal clock.

    Bytes 176-183 hold 'hh.mm.ss'; mne refuses to open the file otherwise. Signal data
    and every other header byte are copied unchanged.
    """
    blob = bytearray(src.read_bytes())
    parts = blob[176:184].decode("ascii", "replace").split(".")
    limits = (23, 59, 59)
    clock = [min(int(p), lim) if p.strip().isdigit() else 0 for p, lim in zip(parts, limits)]
    blob[176:184] = ".".join(f"{v:02d}" for v in clock).encode("ascii")
    dst.write_bytes(bytes(blob))
    return dst


def _save(out: Path, data: np.ndarray) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, data=data.astype(np.float32), channels=np.array(DEFAULT_CHANNELS), fs=TARGET_FS)


def _to_256(raw) -> None:  # noqa: ANN001  (mne Raw)
    if abs(raw.info["sfreq"] - TARGET_FS) > 1e-6:
        raw.resample(TARGET_FS, verbose="ERROR")


def convert_oslo(src: Path, out_root: Path) -> list[str]:
    import mne
    rows = []
    for edf in sorted(src.glob("sub-*_eeg.edf")):
        try:
            raw = mne.io.read_raw_edf(edf, preload=True, verbose="ERROR")
        except ValueError as err:                          # malformed start time in the header
            print(f"  {edf.name}: {err} -> reading a copy with a fixed start time")
            tmp = fix_edf_start_time(edf, out_root / f"_tmp_{edf.name}")
            raw = mne.io.read_raw_edf(tmp, preload=True, verbose="ERROR")
            tmp.unlink()
        tsv = edf.with_name(edf.name.replace("_eeg.edf", "_channels.tsv"))
        bids_units = pd.read_csv(tsv, sep="\t")["units"].tolist() if tsv.exists() else None
        scale = uv_scale(list(raw._orig_units.values()), bids_units)
        _to_256(raw)
        data, missing = pick_target_channels(raw.get_data() * scale, raw.ch_names)
        if missing:
            print(f"  skip {edf.name}: missing {missing}")
            continue
        sid = edf.name.split("_")[0].replace("sub-", "")
        out = out_root / "oslo" / f"os-{sid}.npz"
        _save(out, data)
        rows.append(f"os-{sid},non-stroke,{out},{TARGET_FS}")
    return rows


def convert_tianjin(src: Path, out_root: Path) -> list[str]:
    import mne
    rows = []
    for setf in sorted(src.glob("sub-*/pre/*_pre_01_original.set")):
        # The .set headers hold non-UTF8 strings; the default codec fails with
        # "buffer is too small for requested array".
        raw = mne.io.read_raw_eeglab(setf, preload=True, uint16_codec="latin1", verbose="ERROR")
        ann = raw.annotations
        _to_256(raw)
        data, missing = pick_target_channels(raw.get_data() * 1e6, raw.ch_names)
        if missing:
            print(f"  skip {setf.name}: missing {missing}")
            continue
        sid = setf.name.split("_")[0].replace("sub-", "")
        segs = rest_segments(list(ann.description), list(ann.onset), TARGET_FS, data.shape[1])
        for k, (a, b) in enumerate(segs):
            out = out_root / "tianjin" / f"tj-{sid}_rest{k:02d}.npz"
            _save(out, data[:, a:b])
            rows.append(f"tj-{sid},ischemic,{out},{TARGET_FS}")
        print(f"  tj-{sid}: {len(segs)} rest segments")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oslo-dir", type=Path)
    ap.add_argument("--tianjin-dir", type=Path)
    ap.add_argument("--out-root", type=Path, required=True)
    args = ap.parse_args()
    header = "patient_id,label,path,fs"
    for name, src, fn in (("oslo", args.oslo_dir, convert_oslo), ("tianjin", args.tianjin_dir, convert_tianjin)):
        if src is None:
            continue
        rows = fn(src, args.out_root)
        (args.out_root / f"manifest_{name}.csv").write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
        print(f"{name}: {len(rows)} files, {len({r.split(',')[0] for r in rows})} subjects")


if __name__ == "__main__":
    main()
