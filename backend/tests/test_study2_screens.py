"""Study 2 output screens (docs/user_study_protocol.md section 2.3): wordings and HTML."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import study2_screens as S  # noqa: E402


@pytest.mark.unit
def test_one_screen_per_output_and_wording() -> None:
    assert set(S.SCREENS) == {"alert", "reassure", "nd_plain", "nd_action_quality", "nd_action_ambiguous"}


@pytest.mark.unit
def test_plain_wording_is_the_protocol_sentence_and_gives_no_reason() -> None:
    s = S.SCREENS["nd_plain"]
    assert s.headline == "Không đủ chắc chắn để đưa ra kết quả."
    assert s.reason is None and s.action is None


@pytest.mark.unit
@pytest.mark.parametrize("key", ["nd_action_quality", "nd_action_ambiguous"])
def test_action_wording_says_not_normal_and_keeps_the_pathway(key: str) -> None:
    s = S.SCREENS[key]
    assert s.headline.startswith("Chưa xác định — không có nghĩa là bình thường.")
    assert "Tiếp tục quy trình stroke chuẩn." in s.action
    assert s.reason


@pytest.mark.unit
def test_only_the_quality_reason_suggests_re_measuring() -> None:
    assert "đo lại" in S.SCREENS["nd_action_quality"].action
    assert "đo lại" not in S.SCREENS["nd_action_ambiguous"].action


@pytest.mark.unit
@pytest.mark.parametrize("key", sorted(S.SCREENS))
def test_no_screen_shows_a_probability(key: str) -> None:
    html = S.render(S.SCREENS[key])
    assert "%" not in html  # Bondi et al. 2022: no probabilities on the deferral screen


@pytest.mark.unit
def test_render_escapes_text() -> None:
    screen = S.Screen(state="x", headline="<b>a</b>", tone="neutral")
    assert "<b>a</b>" not in S.render(screen) and "&lt;b&gt;" in S.render(screen)
