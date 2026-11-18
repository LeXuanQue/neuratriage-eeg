"""Pure helpers of scripts/headband_case_study.py (E5: SQI v1 vs v2 on the real headband log)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import headband_case_study as H  # noqa: E402


def _frame(header: int, value: int) -> str:
    return (bytes([header]) + f"{value:08d}".encode() + b"\n").hex().upper()


@pytest.mark.unit
def test_parse_log_splits_samples_by_header_and_ignores_other_sensors() -> None:
    rows = [_frame(0x24, 10), _frame(0x27, 999), _frame(0x26, 20), _frame(0x24, 11), _frame(0x26, 21)]
    out = H.parse_log(rows)
    np.testing.assert_array_equal(out["AF3"], [10.0, 11.0])
    np.testing.assert_array_equal(out["AF4"], [20.0, 21.0])


@pytest.mark.unit
def test_parse_log_skips_malformed_rows() -> None:
    rows = ["", "zz", None, _frame(0x24, 5)]
    out = H.parse_log(rows)
    np.testing.assert_array_equal(out["AF3"], [5.0])
    assert out["AF4"].size == 0


@pytest.mark.unit
def test_aligned_truncates_to_the_shorter_channel() -> None:
    x = H.aligned({"AF3": np.arange(5.0), "AF4": np.arange(3.0)})
    assert x.shape == (2, 3)
