"""Study 2 output screens: what the EEG system shows in each vignette (protocol section 2.3).

Five screens, rendered as HTML and captured as PNG for the survey:

* ``alert`` and ``reassure``: the two confident outputs;
* ``nd_plain``: No-Decision, plain wording (group F-P);
* ``nd_action_quality`` / ``nd_action_ambiguous``: No-Decision, actionable wording (group F-A),
  with the reason the system gives (signal quality vs. a result between the two thresholds).

Both No-Decision wordings share layout and colour, so the groups differ only in the words.
No screen shows a probability (Bondi et al. 2022). The wordings are drafts until the
clinical advisor and a bilingual reviewer approve them (protocol 2.3).

Usage::

    .venv/Scripts/python.exe scripts/study2_screens.py   # writes docs/study2/screens/*.html|png
"""
from __future__ import annotations

import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "study2" / "screens"

ND_ACTION_HEAD = "Chưa xác định — không có nghĩa là bình thường."
KEEP_PATHWAY = "Tiếp tục quy trình stroke chuẩn."


@dataclass(frozen=True)
class Screen:
    state: str  # chip text
    headline: str
    tone: str  # alert | reassure | neutral
    action: Optional[str] = None
    reason: Optional[str] = None


SCREENS: Mapping[str, Screen] = {
    "alert": Screen(
        state="Báo động",
        headline="EEG gợi ý đột quỵ.",
        tone="alert",
        action="Cân nhắc kích hoạt quy trình stroke và chuyển tới trung tâm đột quỵ.",
    ),
    "reassure": Screen(
        state="Yên tâm",
        headline="EEG không gợi ý đột quỵ.",
        tone="reassure",
        action="Đánh giá lâm sàng vẫn là căn cứ chính.",
    ),
    "nd_plain": Screen(
        state="Chưa xác định",
        headline="Không đủ chắc chắn để đưa ra kết quả.",
        tone="neutral",
    ),
    "nd_action_quality": Screen(
        state="Chưa xác định",
        headline=ND_ACTION_HEAD + " Tín hiệu hiện tại chưa đủ để loại trừ stroke.",
        tone="neutral",
        action=KEEP_PATHWAY + " Có thể đo lại sau khi chỉnh điện cực AF4.",
        reason="Chất lượng tín hiệu chưa đủ (điện cực AF4).",
    ),
    "nd_action_ambiguous": Screen(
        state="Chưa xác định",
        headline=ND_ACTION_HEAD + " Tín hiệu hiện tại chưa đủ để loại trừ stroke.",
        tone="neutral",
        action=KEEP_PATHWAY,
        reason="Tín hiệu tốt, nhưng kết quả nằm giữa hai ngưỡng quyết định.",
    ),
}

_TONE = {  # (accent, chip background); text colours are fixed ink tokens
    "alert": ("#c2410c", "#fff1e8"),
    "reassure": ("#15803d", "#ecfdf3"),
    "neutral": ("#1d4ed8", "#eef4ff"),
}

_CSS = """
body{margin:0;background:#f6f6f4;font-family:Inter,'Segoe UI',Roboto,Arial,sans-serif;color:#141413}
.card{box-sizing:border-box;width:720px;margin:24px;padding:22px 26px;background:#fff;
  border:1px solid #e4e3df;border-left:6px solid var(--accent);border-radius:10px}
.top{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.title{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#52514e}
.chip{font-size:13px;font-weight:600;color:var(--accent);background:var(--chip);
  border:1px solid var(--accent);border-radius:999px;padding:3px 12px}
.meta{margin-left:auto;font-size:12px;color:#6b6a66}
.head{font-size:20px;font-weight:650;line-height:1.35;margin:0 0 10px}
.action{font-size:16px;line-height:1.5;margin:0 0 8px}
.reason{font-size:14px;color:#52514e;margin:0}
"""


def render(screen: Screen) -> str:
    """Standalone HTML for one screen (all text escaped)."""
    accent, chip = _TONE.get(screen.tone, _TONE["neutral"])
    e = html.escape
    parts = [
        f'<div class="card" style="--accent:{accent};--chip:{chip}">',
        '<div class="top"><span class="title">Kết quả EEG</span>',
        f'<span class="chip">{e(screen.state)}</span>',
        '<span class="meta">Băng đô 2 kênh · đo 90 giây</span></div>',
        f'<p class="head">{e(screen.headline)}</p>',
    ]
    if screen.action:
        parts.append(f'<p class="action">{e(screen.action)}</p>')
    if screen.reason:
        parts.append(f'<p class="reason">Lý do: {e(screen.reason)}</p>')
    parts.append("</div>")
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8">'
            f"<style>{_CSS}</style></head><body>{''.join(parts)}</body></html>")


def main() -> None:
    from playwright.sync_api import sync_playwright

    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")  # the installed Edge; no browser download
        page = browser.new_page(viewport={"width": 780, "height": 400}, device_scale_factor=2)
        for key, screen in SCREENS.items():
            path = OUT / f"{key}.html"
            path.write_text(render(screen), encoding="utf-8")
            page.goto(path.as_uri())
            page.locator(".card").screenshot(path=str(OUT / f"{key}.png"))
            print("wrote", OUT / f"{key}.png")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
