"""Tests for scripts/nedc_report_query.py (the script NEDC runs on TUH EEG reports).

All report sentences below are synthetic: we have no TUH reports locally, so these
encode the *rule* we want, not observed report wording. Before trusting the rule on
real reports, estimate its precision on a small hand-labelled sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from nedc_report_query import is_affirmed, report_matches, run  # noqa: E402

AFFIRMED = [
    "Acute left MCA infarct.",
    "CLINICAL HISTORY: 67 year old man with acute ischemic stroke, right MCA occlusion.",
    "Impression: abnormal EEG consistent with a left hemispheric infarction.",
    "Ischemic stroke with hemorrhagic transformation.",
    "No seizures, but acute infarct in the left MCA territory.",
    "Patient presented with CVA and right sided weakness.",
]

NEGATED = [
    "No evidence of infarct.",
    "Negative for stroke.",
    "Without acute infarction on imaging.",
    "No infarct or hemorrhage.",
    "Denies stroke symptoms.",
]

UNCERTAIN = [
    "Rule out stroke.",
    "Evaluate for stroke.",
    "Concern for stroke.",
    "Possible CVA.",
    "R/O infarct.",
    "Stroke-like episodes in the setting of MELAS.",
]

# The doubt comes AFTER the term here, so a "look only before" rule misses it.
NEGATED_AFTER_TERM = [
    "Infarct was ruled out.",
    "Stroke has been excluded.",
    "Infarct not seen on CT.",
    "Stroke unlikely.",
    "Acute infarct versus tumor.",
    "Acute infarct?",
]

HISTORICAL = [
    "History of stroke in 2010.",
    "Prior CVA with residual weakness.",
    "Remote infarct on CT.",
    "Chronic left MCA infarct.",
]

NOT_ISCHEMIC = [
    "Intracerebral hemorrhage, hemorrhagic stroke.",
    "Subarachnoid hemorrhage.",
    "Seizures, rule out epilepsy.",
]


@pytest.mark.parametrize("text", AFFIRMED)
def test_report_matches_when_ischemic_stroke_is_affirmed(text):
    assert report_matches(text) is True


@pytest.mark.parametrize("text", NEGATED)
def test_report_does_not_match_when_stroke_is_negated(text):
    assert report_matches(text) is False


@pytest.mark.parametrize("text", UNCERTAIN)
def test_report_does_not_match_when_stroke_is_only_suspected(text):
    assert report_matches(text) is False


@pytest.mark.parametrize("text", NEGATED_AFTER_TERM)
def test_report_does_not_match_when_doubt_follows_the_term(text):
    assert report_matches(text) is False


def test_doubt_after_a_scope_breaker_does_not_cancel_an_earlier_finding():
    assert report_matches("Acute left MCA infarct, but seizure excluded.") is True


@pytest.mark.parametrize("text", HISTORICAL)
def test_report_does_not_match_when_stroke_is_historical(text):
    assert report_matches(text) is False


@pytest.mark.parametrize("text", NOT_ISCHEMIC)
def test_report_does_not_match_non_ischemic_reports(text):
    assert report_matches(text) is False


def test_is_affirmed_reads_the_clause_around_the_term_position():
    clause = "no seizures but acute infarct in the left mca territory"
    assert is_affirmed(clause, clause.index("infarct")) is True
    assert is_affirmed("no evidence of infarct", len("no evidence of ")) is False


def test_report_matches_any_affirmed_clause_in_a_multiline_report():
    text = "HISTORY: headache.\nIMPRESSION: No hemorrhage. Acute right MCA infarct.\n"
    assert report_matches(text) is True


def test_report_matching_is_case_insensitive():
    assert report_matches("ACUTE ISCHEMIC STROKE") is True
    assert report_matches("NO EVIDENCE OF INFARCT") is False


def test_empty_report_does_not_match():
    assert report_matches("") is False


def test_run_returns_only_matching_files_in_list_order(tmp_path):
    (tmp_path / "a.txt").write_text("Acute ischemic stroke.", encoding="utf8")
    (tmp_path / "b.txt").write_text("No evidence of infarct.", encoding="utf8")
    (tmp_path / "c.txt").write_text("Acute left MCA infarct.", encoding="utf8")
    listing = tmp_path / "x.list"
    listing.write_text("a.txt\nb.txt\nc.txt\n", encoding="utf8")

    matches, errors = run(str(listing), root=str(tmp_path))

    assert matches == ["a.txt", "c.txt"]
    assert errors == []


def test_run_reports_unreadable_files_instead_of_swallowing_them(tmp_path):
    (tmp_path / "ok.txt").write_text("Acute ischemic stroke.", encoding="utf8")
    listing = tmp_path / "x.list"
    listing.write_text("missing.txt\nok.txt\n", encoding="utf8")

    matches, errors = run(str(listing), root=str(tmp_path))

    assert matches == ["ok.txt"]
    assert [name for name, _ in errors] == ["missing.txt"]


def test_run_tolerates_non_utf8_bytes_in_a_report(tmp_path):
    (tmp_path / "latin.txt").write_bytes(b"Acute ischemic stroke \xe9\xe8.")
    listing = tmp_path / "x.list"
    listing.write_text("latin.txt\n", encoding="utf8")

    matches, errors = run(str(listing), root=str(tmp_path))

    assert matches == ["latin.txt"]
    assert errors == []
