"""Stitch several EEG recordings into one long, continuously playable case.

Why: a demo screen that stops after one recording looks broken. Two fixes exist
-- looping a single file (handled by the WS replay path) and this script, which
concatenates several recordings so the trace stays varied instead of repeating.

The joins are crossfaded, otherwise the boundary between two recordings shows up
as a vertical step in the trace and as a broadband transient in the spectrum --
the detector would score that artefact as real signal.

The output is clearly marked as stitched: it carries a ``stitched`` flag and a
``sources`` table saying which recording each second came from. It is a VISUAL
aid, not a patient: never present a stitched case as one person's recording.

Usage:
  python scripts/build_continuous_case.py --out dataset_npz/continuous_demo.npz \
      dataset_healthy/sub-S001.npz dataset_ischemic/sub-01.npz
  python scripts/build_continuous_case.py --out X.npz --glob "dataset_healthy/*.npz" --limit 4
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


DEFAULT_CROSSFADE_SEC = 0.5


@dataclass
class Recording:
    """One source recording: a (channels, samples) matrix plus its labels."""

    data: np.ndarray
    channels: List[str]
    fs: float
    name: str


@dataclass
class StitchedCase:
    data: np.ndarray
    channels: List[str]
    fs: float
    sources: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return float(self.data.shape[1]) / self.fs if self.fs else 0.0


def load_recording(path: Path) -> Recording:
    """Read an .npz/.npy recording the same way the WS replay path does."""
    loaded = np.load(str(path), allow_pickle=True)
    channels: Optional[List[str]] = None
    fs = 256.0
    try:
        if hasattr(loaded, "files"):
            key = "data" if "data" in loaded.files else (
                "eeg" if "eeg" in loaded.files else loaded.files[0]
            )
            data = np.asarray(loaded[key], dtype=float)
            if "channels" in loaded.files:
                channels = [str(c) for c in loaded["channels"]]
            if "fs" in loaded.files:
                fs = float(loaded["fs"])
        else:
            data = np.asarray(loaded, dtype=float)
    finally:
        if hasattr(loaded, "close"):
            loaded.close()

    if data.ndim == 1:
        data = data[np.newaxis, :]
    if data.ndim != 2:
        raise ValueError(f"{path.name}: expected (channels, samples), got {data.shape}")
    if channels is None or len(channels) != data.shape[0]:
        channels = [f"CH{i + 1}" for i in range(data.shape[0])]
    return Recording(data=data, channels=channels, fs=fs, name=path.stem)


def _aligned(rec: Recording, channels: Sequence[str]) -> np.ndarray:
    """Reorder a recording's rows onto the reference channel order."""
    if list(rec.channels) == list(channels):
        return rec.data
    if set(rec.channels) != set(channels):
        missing = sorted(set(channels) - set(rec.channels))
        extra = sorted(set(rec.channels) - set(channels))
        raise ValueError(
            f"{rec.name}: channel set differs (missing={missing}, unexpected={extra})"
        )
    index = {name: i for i, name in enumerate(rec.channels)}
    return rec.data[[index[name] for name in channels], :]


def concat_recordings(
    recordings: Sequence[Recording],
    crossfade_sec: float = DEFAULT_CROSSFADE_SEC,
) -> StitchedCase:
    """Concatenate recordings into one continuous case, crossfading the joins."""
    if not recordings:
        raise ValueError("Need at least one recording to stitch")

    reference = recordings[0]
    fs = float(reference.fs)
    channels = list(reference.channels)
    for rec in recordings[1:]:
        if float(rec.fs) != fs:
            raise ValueError(
                f"{rec.name}: sample rate {rec.fs} does not match {fs} of {reference.name}"
            )

    blend = max(0, int(round(max(0.0, crossfade_sec) * fs)))
    out = _aligned(reference, channels).astype(float, copy=True)
    sources: List[Dict[str, Any]] = [
        {
            "name": reference.name,
            "start_sec": 0.0,
            "duration_sec": round(out.shape[1] / fs, 3),
        }
    ]

    for rec in recordings[1:]:
        nxt = _aligned(rec, channels).astype(float, copy=False)
        n = min(blend, out.shape[1], nxt.shape[1])
        if n > 0:
            # Linear crossfade: the tail of what we have fades out while the head
            # of the next recording fades in, so the trace has no step.
            ramp = np.linspace(0.0, 1.0, n, endpoint=False)[np.newaxis, :]
            head = out[:, -n:] * (1.0 - ramp) + nxt[:, :n] * ramp
            start_sec = (out.shape[1] - n) / fs
            out = np.concatenate([out[:, :-n], head, nxt[:, n:]], axis=1)
        else:
            start_sec = out.shape[1] / fs
            out = np.concatenate([out, nxt], axis=1)
        sources.append(
            {
                "name": rec.name,
                "start_sec": round(start_sec, 3),
                "duration_sec": round(nxt.shape[1] / fs, 3),
            }
        )

    return StitchedCase(data=out, channels=channels, fs=fs, sources=sources)


def save_case(case: StitchedCase, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        data=case.data.astype(np.float32),
        channels=np.array(case.channels),
        fs=np.float32(case.fs),
        stitched=np.bool_(True),
        sources=np.array(json.dumps(case.sources)),
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="*", help="recording paths, in playback order")
    ap.add_argument("--glob", dest="pattern", help="glob for inputs instead of listing them")
    ap.add_argument("--limit", type=int, default=0, help="use at most N inputs")
    ap.add_argument("--out", required=True, help="output .npz path")
    ap.add_argument("--crossfade-sec", type=float, default=DEFAULT_CROSSFADE_SEC)
    args = ap.parse_args(argv)

    paths = [Path(p) for p in args.inputs]
    if args.pattern:
        paths.extend(Path(p) for p in sorted(glob(args.pattern)))
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        ap.error("no input recordings given")

    recordings = []
    for path in paths:
        rec = load_recording(path)
        print(f"  + {path.name:24} {rec.data.shape[0]:2d}ch  {rec.data.shape[1] / rec.fs:7.1f}s")
        recordings.append(rec)

    case = concat_recordings(recordings, crossfade_sec=args.crossfade_sec)
    save_case(case, Path(args.out))
    print(
        f"\nStitched {len(recordings)} recordings -> {args.out}\n"
        f"  {case.data.shape[0]} channels, {case.duration_sec:.1f}s "
        f"({case.duration_sec / 60:.1f} min), crossfade {args.crossfade_sec}s"
    )
    print("  NOTE: marked stitched=True — a visual aid, not one patient's recording.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
