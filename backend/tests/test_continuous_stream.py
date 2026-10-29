"""Continuous playback for visual demos: stitched recordings + looped replay.

Two ways to keep the waveform alive indefinitely:
  1. `scripts/build_continuous_case.py` concatenates several recordings into one
     long file, crossfading the joins so the trace has no visible step.
  2. The WS replay path can loop a file instead of ending at `replay_done`.

Run: .venv/Scripts/python.exe -m pytest backend/tests/test_continuous_stream.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# backend/tests/ -> backend/ -> repo root -> scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_continuous_case import Recording, concat_recordings  # noqa: E402


def _rec(rows=2, samples=512, fs=256.0, channels=None, value=1.0):
    data = np.full((rows, samples), value, dtype=float)
    return Recording(
        data=data,
        channels=channels or [f"CH{i + 1}" for i in range(rows)],
        fs=fs,
        name=f"rec-{value}",
    )


@pytest.mark.unit
def test_concat_joins_recordings_end_to_end():
    a, b = _rec(value=1.0), _rec(value=2.0)

    out = concat_recordings([a, b], crossfade_sec=0.0)

    assert out.data.shape == (2, 1024)
    assert out.channels == a.channels
    assert out.fs == 256.0


@pytest.mark.unit
def test_crossfade_removes_the_step_at_the_join():
    """A hard cut leaves a visible jump; the crossfade must smooth it."""
    a, b = _rec(value=0.0), _rec(value=10.0)

    hard = concat_recordings([a, b], crossfade_sec=0.0)
    faded = concat_recordings([a, b], crossfade_sec=0.5)

    assert np.abs(np.diff(hard.data[0])).max() == pytest.approx(10.0)
    # 0.5s at 256 Hz = 128 blend samples, so each step is ~10/128
    assert np.abs(np.diff(faded.data[0])).max() < 1.0


@pytest.mark.unit
def test_crossfade_shortens_the_total_length_by_the_overlap():
    a, b = _rec(samples=512), _rec(samples=512)

    out = concat_recordings([a, b], crossfade_sec=0.5)

    assert out.data.shape[1] == 512 + 512 - 128


@pytest.mark.unit
def test_records_where_every_segment_came_from():
    a, b = _rec(value=1.0), _rec(value=2.0)

    out = concat_recordings([a, b], crossfade_sec=0.0)

    assert [s["name"] for s in out.sources] == ["rec-1.0", "rec-2.0"]
    assert out.sources[0]["start_sec"] == 0.0
    assert out.sources[1]["start_sec"] == pytest.approx(2.0)


@pytest.mark.unit
def test_refuses_mismatched_sample_rates():
    with pytest.raises(ValueError, match="sample rate"):
        concat_recordings([_rec(fs=256.0), _rec(fs=128.0)], crossfade_sec=0.0)


@pytest.mark.unit
def test_refuses_mismatched_channel_sets():
    a = _rec(channels=["AF3", "AF4"])
    b = _rec(channels=["C3", "C4"])
    with pytest.raises(ValueError, match="channel"):
        concat_recordings([a, b], crossfade_sec=0.0)


@pytest.mark.unit
def test_reorders_channels_to_match_the_first_recording():
    a = _rec(rows=2, channels=["AF3", "AF4"])
    b = Recording(
        data=np.vstack([np.full(512, 9.0), np.full(512, 8.0)]),
        channels=["AF4", "AF3"],
        fs=256.0,
        name="swapped",
    )

    out = concat_recordings([a, b], crossfade_sec=0.0)

    assert out.channels == ["AF3", "AF4"]
    # AF3 row must carry the 8.0 values from the swapped recording
    assert out.data[0, -1] == pytest.approx(8.0)


@pytest.mark.unit
def test_needs_at_least_one_recording():
    with pytest.raises(ValueError):
        concat_recordings([], crossfade_sec=0.0)
