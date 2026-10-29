"""Unit tests for the pure parsing helpers in ``scripts/tusl_to_npz.py``.

Covers ``parse_tse_agg`` (``.tse_agg`` annotation parsing rules) and
``label_for`` (the same-rig slow/bckg/exclude class mapping). These functions
are the only pure, EDF-free surface of the TUSL converter, so they are unit
tested in isolation. The module lives under the repo ``scripts/`` dir, which the
shared ``conftest.py`` does not add to ``sys.path`` (it only adds ``backend/``),
so this file inserts ``scripts/`` itself — mirroring how ``conftest`` locates
``backend`` relative to ``__file__``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/tests/ -> backend/ -> repo root -> scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from tusl_to_npz import Segment, label_for, parse_tse_agg  # noqa: E402


def test_parses_realistic_multiline_body_into_expected_segments() -> None:
    # Arrange
    body = (
        "version = tse_v1.0.0\n"
        "\n"
        "294.0000 304.0000 slow 1.0000\n"
        "304.0000 320.5000 bckg 1.0000\n"
        "320.5000 331.0000 seiz 0.9000\n"
        "331.0000 350.0000 slow 1.0000\n"
    )

    # Act
    segments = parse_tse_agg(body)

    # Assert
    assert len(segments) == 4
    assert segments == [
        Segment(294.0, 304.0, "slow"),
        Segment(304.0, 320.5, "bckg"),
        Segment(320.5, 331.0, "seiz"),
        Segment(331.0, 350.0, "slow"),
    ]


def test_header_and_blank_lines_are_skipped() -> None:
    # Arrange
    body = (
        "version = tse_v1.0.0\n"
        "\n"
        "   \n"
        "# a comment line\n"
        "0.0000 10.0000 bckg 1.0000\n"
    )

    # Act
    segments = parse_tse_agg(body)

    # Assert
    assert segments == [Segment(0.0, 10.0, "bckg")]


def test_malformed_lines_are_skipped() -> None:
    # Arrange: too few fields, then non-numeric start/stop times.
    body = (
        "294.0000 slow\n"                 # only 2 fields
        "abc 304.0000 slow 1.0000\n"      # non-numeric start
        "294.0000 xyz slow 1.0000\n"      # non-numeric stop
        "10.0000 20.0000 slow 1.0000\n"   # the one valid line
    )

    # Act
    segments = parse_tse_agg(body)

    # Assert
    assert segments == [Segment(10.0, 20.0, "slow")]


def test_zero_or_negative_length_segments_are_dropped() -> None:
    # Arrange: stop == start and stop < start must both be dropped.
    body = (
        "50.0000 50.0000 slow 1.0000\n"   # stop == start
        "80.0000 70.0000 bckg 1.0000\n"   # stop < start
        "70.0000 80.0000 bckg 1.0000\n"   # valid
    )

    # Act
    segments = parse_tse_agg(body)

    # Assert
    assert segments == [Segment(70.0, 80.0, "bckg")]


def test_label_is_lowercased() -> None:
    # Arrange
    body = "294.0000 304.0000 SLOW 1.0000\n"

    # Act
    segments = parse_tse_agg(body)

    # Assert
    assert len(segments) == 1
    assert segments[0].label == "slow"


def test_empty_text_yields_no_segments() -> None:
    # Arrange / Act / Assert
    assert parse_tse_agg("") == []


def test_label_for_maps_slow_to_positive() -> None:
    assert label_for("slow") == 1


def test_label_for_maps_bckg_to_negative() -> None:
    assert label_for("bckg") == 0


def test_label_for_excludes_seiz() -> None:
    assert label_for("seiz") is None


def test_label_for_excludes_unknown_label() -> None:
    assert label_for("mysterylabel") is None
