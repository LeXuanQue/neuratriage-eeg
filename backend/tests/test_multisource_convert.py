"""Tests for scripts/convert_multisource.py (Oslo ds003775 + Tianjin 30509165 -> npz)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import convert_multisource as cm  # noqa: E402


def test_rest_segments_run_from_rest_onset_to_next_event() -> None:
    # '1' = start of rest; '2'/'3' = start of motor imagery (Tianjin events.json).
    types = ["boundary", "1", "2", "1", "3", "1"]
    onsets_s = [0.0, 3.0, 11.6, 19.0, 27.5, 34.5]

    segs = cm.rest_segments(types, onsets_s, fs=250.0, n_samples=int(45.0 * 250))

    assert segs == [(750, 2900), (4750, 6875), (8625, 11250)]   # last rest runs to end of data


def test_rest_segments_drop_too_short_pieces() -> None:
    segs = cm.rest_segments(["1", "2"], [0.0, 3.0], fs=250.0, n_samples=10_000, min_sec=4.0)

    assert segs == []


def test_uv_scale_trusts_bids_units_when_edf_header_has_none() -> None:
    # EDF header unit 'n/a' -> mne assumes volts and returns the stored numbers as-is;
    # the BIDS channels.tsv says they are already microvolts.
    assert cm.uv_scale(["n/a"] * 3, ["uV"] * 3) == 1.0
    # Header with a real unit -> mne already converted to volts -> multiply back.
    assert cm.uv_scale(["uV", "uV"], ["uV", "uV"]) == 1e6
    assert cm.uv_scale(["uV"], None) == 1e6


def test_fix_edf_start_time_rewrites_only_an_invalid_clock(tmp_path: Path) -> None:
    header = bytearray(b" " * 256)
    header[168:176] = b"01.02.17"          # start date
    header[176:184] = b"10.59.60"          # start time with second = 60 (invalid)
    bad = tmp_path / "bad.edf"
    bad.write_bytes(bytes(header) + b"DATA")

    fixed = cm.fix_edf_start_time(bad, tmp_path / "fixed.edf")

    blob = fixed.read_bytes()
    assert blob[176:184] == b"10.59.59" and blob[168:176] == b"01.02.17"
    assert blob[256:] == b"DATA"                            # signal bytes untouched


def test_pick_target_channels_maps_1010_names_and_reports_missing() -> None:
    labels = ["Fp1", "Fp2", "F3", "F4", "F7", "F8", "Fz", "C3", "C4", "Cz",
              "P3", "P4", "T7", "T8", "P7", "P8", "O1", "O2", "Oz"]
    data = np.arange(len(labels))[:, None] * np.ones((1, 10))

    out, missing = cm.pick_target_channels(data, labels)

    assert out.shape == (18, 10) and missing == []
    # T3 is the old name of T7: row for T3 must hold the T7 data (index 12).
    from eeg_stroke_pipeline import DEFAULT_CHANNELS
    assert out[DEFAULT_CHANNELS.index("T3"), 0] == labels.index("T7")
