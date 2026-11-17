"""Pre-registered ship criteria for the advisory eye-movement reason (docs/paper_outline.md s.7)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import eye_reason_eval as V  # noqa: E402

GOOD = {
    "eyem_correct_before": 0.06, "eyem_correct_after": 0.30,
    "clean_eye_rate": 0.05, "e7_correct_among_flagged": 0.70,
    "eye_share": {"IS": 0.02, "NS": 0.03, "TUSL_slow": 0.10, "TUSL_bckg": 0.12},
}


@pytest.mark.unit
def test_all_criteria_met_ships() -> None:
    v = V.verdict(GOOD)
    assert v["ship"] is True and all(v["criteria"].values())


@pytest.mark.unit
@pytest.mark.parametrize(
    "patch, failed",
    [
        ({"eyem_correct_after": 0.06}, "a_eyem_improves"),
        ({"clean_eye_rate": 0.071}, "b_clean_rate_le_7pct"),
        ({"e7_correct_among_flagged": 0.689}, "c_e7_not_down_2pts"),
        ({"eye_share": {"IS": 0.05, "NS": 0.03, "TUSL_slow": 0.10, "TUSL_bckg": 0.12}}, "d_is_le_ns"),
        ({"eye_share": {"IS": 0.02, "NS": 0.03, "TUSL_slow": 0.13, "TUSL_bckg": 0.12}}, "d_slow_le_bckg"),
    ],
)
def test_any_failed_criterion_blocks_shipping(patch: dict, failed: str) -> None:
    v = V.verdict({**GOOD, **patch})
    assert v["ship"] is False
    assert v["criteria"][failed] is False


@pytest.mark.unit
def test_eye_fires_independently_of_reason_order() -> None:
    import numpy as np
    import pandas as pd

    df = pd.DataFrame({"delta_ratio": [0.95, 0.95, 0.5, np.nan], "alpha_peak": [-0.3, 0.4, -0.3, -0.3]})
    assert V.eye_fires(df).tolist() == [True, False, False, False]
