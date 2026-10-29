"""Unit tests for the source-confound diagnostic helpers.

Run: .venv/Scripts/python.exe -m pytest tests/test_source_confound.py -q
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagnose_source_confound import derive_source, source_label_crosstab  # noqa: E402


@pytest.mark.unit
def test_derive_source_maps_known_prefixes() -> None:
    # Arrange
    pids = pd.Series(["sub-01", "sub-50", "ns-S001", "ns-S050", "uclh_p3_big_ich"])
    # Act
    src = derive_source(pids)
    # Assert
    assert src.tolist() == [
        "clinical_ischemic",
        "clinical_ischemic",
        "physionet_nonstroke",
        "physionet_nonstroke",
        "uclh_hemorrhagic",
    ]


@pytest.mark.unit
def test_derive_source_unknown_prefix_is_labelled_other() -> None:
    assert derive_source(pd.Series(["weird-id"])).tolist() == ["other"]


@pytest.mark.unit
def test_crosstab_flags_perfect_confound() -> None:
    # Arrange: source perfectly predicts label
    df = pd.DataFrame(
        {
            "patient_id": ["sub-01", "sub-02", "ns-S001", "ns-S002"],
            "label": [1, 1, 0, 0],
        }
    )
    # Act
    ct, confounded = source_label_crosstab(df)
    # Assert
    assert confounded is True
    assert ct.shape[0] == 2


@pytest.mark.unit
def test_crosstab_not_confounded_when_sources_share_labels() -> None:
    # Same source carries both labels -> not a perfect confound
    df = pd.DataFrame(
        {
            "patient_id": ["sub-01", "sub-02", "sub-03", "sub-04"],
            "label": [1, 0, 1, 0],
        }
    )
    _, confounded = source_label_crosstab(df)
    assert confounded is False
