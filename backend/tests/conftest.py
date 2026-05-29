"""Pytest configuration — make `app` and `eeg_stroke_pipeline` importable
regardless of how pytest is invoked (root or backend/).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Clear in-memory rate limit buckets before every test so tests are isolated."""
    from app.services.rate_limit import infer_limiter, login_limiter

    login_limiter.reset()
    infer_limiter.reset()
    yield
    login_limiter.reset()
    infer_limiter.reset()
