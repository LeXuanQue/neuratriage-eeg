"""Unit tests for inference response helpers.

Guards the JSON-validity fix: when every window is SQI-gated, the per-column
aggregates are NaN, which must not leak into the JSON response as the invalid
``NaN`` token.
"""
from __future__ import annotations

from app.routers.inference import _num


def test_num_passes_finite_values() -> None:
    assert _num(0.512) == 0.512
    assert _num(0) == 0.0
    assert _num("1.5") == 1.5


def test_num_maps_nan_inf_none_to_default() -> None:
    assert _num(float("nan")) is None
    assert _num(float("inf")) is None
    assert _num(float("-inf")) is None
    assert _num(None) is None
    assert _num("not-a-number") is None


def test_num_honours_explicit_default() -> None:
    assert _num(float("nan"), 0.0) == 0.0
    assert _num(None, 0.0) == 0.0
