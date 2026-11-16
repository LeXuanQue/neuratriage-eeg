"""Pure helpers of scripts/latency_bench.py (E4)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import latency_bench as L  # noqa: E402


@pytest.mark.unit
def test_summarize_ms_reports_percentiles_in_milliseconds() -> None:
    s = L.summarize_ms([0.001 * i for i in range(1, 101)])  # 1..100 ms, given in seconds
    assert s["n"] == 100
    assert s["mean_ms"] == pytest.approx(50.5)
    assert s["p50_ms"] == pytest.approx(50.5)
    assert s["p95_ms"] == pytest.approx(95.05)
    assert s["max_ms"] == pytest.approx(100.0)


@pytest.mark.unit
def test_summarize_ms_handles_no_samples() -> None:
    assert L.summarize_ms([]) == {"n": 0}


@pytest.mark.unit
def test_realtime_factor_is_processing_time_over_chunk_time() -> None:
    assert L.realtime_factor(p95_ms=25.0, chunk_sec=0.5) == pytest.approx(0.05)
