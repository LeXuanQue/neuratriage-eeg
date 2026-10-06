"""Unit tests for the pure path/label helpers in ``scripts/tuab_to_npz.py``.

Covers ``label_from_path`` (the normal/abnormal directory-component mapping, whose
one subtle rule is that "normal" must NOT match inside "abnormal") and
``subject_from_edf`` (TUH ``<subject>_<session>_<token>.edf`` code extraction).
These are the only pure, EDF-free surface of the TUAB converter. The module lives
under the repo ``scripts/`` dir, which the shared ``conftest.py`` does not add to
``sys.path`` (it only adds ``backend/``), so this file inserts ``scripts/`` itself
— mirroring ``test_tusl_parse.py``.
"""
from __future__ import annotations

import sys
from pathlib import Path

# backend/tests/ -> backend/ -> repo root -> scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from tuab_to_npz import label_from_path, subject_from_edf  # noqa: E402


# ── label_from_path ──────────────────────────────────────────────────────────

def test_normal_component_maps_to_zero():
    parts = ("edf", "train", "normal", "01_tcp_ar", "aaaaaaav_s004_t000.edf")
    assert label_from_path(parts) == 0


def test_abnormal_component_maps_to_one():
    parts = ("edf", "eval", "abnormal", "01_tcp_ar", "aaaaaaav_s001_t000.edf")
    assert label_from_path(parts) == 1


def test_abnormal_is_not_shadowed_by_normal_substring():
    # "normal" is a substring of "abnormal"; the mapping must not misread it as 0.
    parts = ("abnormal", "aaaaaaav_s001_t000.edf")
    assert label_from_path(parts) == 1


def test_case_insensitive_matching():
    assert label_from_path(("EDF", "Train", "NORMAL", "x.edf")) == 0
    assert label_from_path(("EDF", "Eval", "AbNorMaL", "x.edf")) == 1


def test_unlabeled_path_returns_none():
    parts = ("edf", "train", "01_tcp_ar", "aaaaaaav_s004_t000.edf")
    assert label_from_path(parts) is None


def test_empty_parts_returns_none():
    assert label_from_path(()) is None


# ── subject_from_edf ─────────────────────────────────────────────────────────

def test_subject_from_standard_filename():
    assert subject_from_edf(Path("aaaaaaav_s004_t000.edf")) == "aaaaaaav"


def test_subject_from_nested_path_uses_filename_only():
    p = Path("F:/tuh_data/tuab/edf/train/abnormal/01_tcp_ar/aaaaaaav_s001_t000.edf")
    assert subject_from_edf(p) == "aaaaaaav"


def test_subject_from_filename_without_underscore():
    # No session/token tokens -> the whole stem is the subject code.
    assert subject_from_edf(Path("aaaaaaav.edf")) == "aaaaaaav"
