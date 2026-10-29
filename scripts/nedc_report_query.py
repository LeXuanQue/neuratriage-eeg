#!/usr/bin/env python
"""Select TUH EEG reports that affirm an ischemic stroke / infarct.

NEDC no longer distributes reports; they run a submitted script on the anonymised
reports and return the matching file names. Usage on their side::

    python nedc_report_query.py <file.list>

``file.list`` holds one report path per line. Matching paths are printed to stdout,
one per line (that is all NEDC reports back); problems go to stderr.

Constraints: standard library only (NEDC requirement) and no syntax newer than
Python 3.7, because we do not know which interpreter they run.

This is a *weak* labeller. Nobody reads the reports, so precision must be estimated
on a small hand-labelled sample before the matches are used as "ischemic stroke".
"""
from __future__ import annotations

import os
import re
import sys

# Cue lists consumed by ``is_affirmed``. Lower-case, matched against a lower-cased clause.
NEGATION_CUES = (
    "no ", "not ", "without", "negative for", "denies", "denied", "absence of",
    "absent", "free of", "ruled out",
)
UNCERTAINTY_CUES = (
    "rule out", "r/o", "evaluate for", "evaluation for", "eval for", "assess for",
    "concern for", "possible", "probable", "suspected", "suspicion", "question of",
    "?", " versus ", " vs ", "differential",
)
HISTORY_CUES = (
    "history of", "h/o", "hx of", "prior", "previous", "remote", "chronic",
    "past ", "s/p", "status post",
)
# Words after which a cue earlier in the clause no longer applies.
SCOPE_BREAKERS = (" but ", " however", " although", " except", " yet ")
# Doubt that follows the term: "infarct was ruled out", "stroke unlikely".
POST_CUES = (
    "ruled out", "excluded", "not seen", "not identified", "not evident",
    "not present", "unlikely", " versus ", " vs ", "?",
)

_ISCHEMIC_CUE = re.compile(r"ischemi|infarct|\b(?:mca|ica|pca|aca)\b")
_ARTERY = (
    r"(?:mca|ica|pca|aca|middle cerebral artery|internal carotid artery"
    r"|posterior cerebral artery|anterior cerebral artery)"
)
_STROKE_TERMS = (
    re.compile(r"\binfarct(?:s|ion|ions|ed)?\b"),
    re.compile(r"\bischemic\s+(?:stroke|infarct\w*|event|lesion|cva)\b"),
    # "stroke-like episodes" (seizure/MELAS context) is not a stroke.
    re.compile(r"\b(?:cva|strokes?)\b(?!-like)"),
    re.compile(r"\b" + _ARTERY + r"\b[^.;]{0,40}?\b(?:occlusion|occluded|thromb\w*|embol\w*)"),
)
_CLAUSE_SPLIT = re.compile(r"[.;\n]+")
# "old infarct" is historical, but "67 year old man" is not.
_OLD_FINDING = re.compile(
    r"(?<!year )(?<!years )(?<!month )(?<!months )(?<!week )(?<!day )\bold\b"
)
_NON_WORD = re.compile(r"[^a-z0-9/?]+")


def split_clauses(text: str) -> list[str]:
    """Lower-case ``text`` and split it into non-empty clauses."""
    return [c.strip() for c in _CLAUSE_SPLIT.split(text.lower()) if c.strip()]


def is_affirmed(clause: str, term_start: int) -> bool:
    """True if the stroke term at ``term_start`` is asserted as a *current* finding.

    ``clause`` is lower-cased. Return False when the term is negated, only suspected,
    or historical, using the cue tuples above.
    """
    # Only text before the term can negate it; a breaker ("but", "however") ends the
    # scope of any cue that came earlier in the clause.
    scope = " " + _NON_WORD.sub(" ", clause[:term_start])
    cut = max((scope.rfind(b) + len(b) for b in SCOPE_BREAKERS if b in scope), default=0)
    scope = " " + scope[cut:]
    cues = NEGATION_CUES + UNCERTAINTY_CUES + HISTORY_CUES
    if any(_cue_in(scope, cue) for cue in cues):
        return False
    if _OLD_FINDING.search(scope):
        return False
    after = " " + _NON_WORD.sub(" ", clause[term_start:])
    end = min((after.find(b) for b in SCOPE_BREAKERS if b in after), default=len(after))
    return not any(_cue_in(after[:end], cue) for cue in POST_CUES)


def _cue_in(scope: str, cue: str) -> bool:
    """Match ``cue`` at a word start, so "no " does not fire inside "casino "."""
    return (" " + cue if cue[0].isalpha() else cue) in scope


def _terms_in(clause: str) -> list[int]:
    """Start offsets of stroke terms in ``clause`` (empty for hemorrhage-only clauses)."""
    if "hemorrhag" in clause and not _ISCHEMIC_CUE.search(clause):
        return []
    return [m.start() for term in _STROKE_TERMS for m in term.finditer(clause)]


def report_matches(text: str) -> bool:
    """True if any clause of the report affirms an ischemic stroke / infarct."""
    for clause in split_clauses(text):
        if any(is_affirmed(clause, start) for start in _terms_in(clause)):
            return True
    return False


def _read_report(path: str) -> str:
    with open(path, "rb") as handle:
        return handle.read().decode("utf8", errors="replace")


def run(list_path: str, root: str = ".") -> tuple[list[str], list[tuple[str, str]]]:
    """Return (matching names in list order, [(name, error message), ...])."""
    matches: list[str] = []
    errors: list[tuple[str, str]] = []
    with open(list_path, "r", encoding="utf8") as handle:
        names = [line.rstrip("\n") for line in handle if line.strip()]
    for name in names:
        try:
            if report_matches(_read_report(os.path.join(root, name))):
                matches.append(name)
        except OSError as exc:
            errors.append((name, str(exc)))
    return matches, errors


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.stderr.write("usage: nedc_report_query.py <file.list>\n")
        return 2
    matches, errors = run(argv[1])
    for name in matches:
        sys.stdout.write(name + "\n")
    for name, message in errors:
        sys.stderr.write("ERROR %s: %s\n" % (name, message))
    sys.stderr.write("matched %d, errors %d\n" % (len(matches), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
