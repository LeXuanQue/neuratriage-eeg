#!/usr/bin/env python3
"""Capture a real screenshot of the NeuraTriage UI for the UIST paper figure.

Requires the backend running on http://127.0.0.1:8501 and Microsoft Edge
(uses Playwright with channel=msedge so no Chromium download is needed).

Run: .venv/Scripts/python.exe figures/capture_ui.py
Output: figures/fig_ui.png  (and fig_ui_login.png as a fallback view)
"""
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8501/"
EMAIL = "doctor@neuratriage.com"
PW = "demo1234"
OUT = Path(__file__).resolve().parent
VIEWPORT = {"width": 1480, "height": 920}


def _launch(p):
    for channel in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=channel, headless=True)
        except Exception as e:
            print(f"  channel={channel} unavailable: {str(e)[:80]}")
    return p.chromium.launch(headless=True)  # bundled chromium if installed


def main() -> int:
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        # --- login if a password field is present ---
        pw = page.locator("input[type=password]")
        if pw.count() > 0:
            email = page.locator("input[type=email]")
            if email.count() == 0:
                email = page.locator("input[type=text]:visible").first
            email.first.fill(EMAIL)
            pw.first.fill(PW)
            page.screenshot(path=str(OUT / "fig_ui_login.png"))
            btn = page.get_by_role(
                "button", name=re.compile("login|sign in|đăng nhập", re.I))
            if btn.count() > 0:
                btn.first.click()
            else:
                pw.first.press("Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            page.wait_for_timeout(2500)
            print("  logged in")
        else:
            print("  no login form detected (already authed or landing)")

        # --- capture the live triage view (waiting state) ---
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "fig_ui_live.png"))
        print("  saved fig_ui_live.png")

        # --- drive: EEG Analysis -> Replay tab -> Run a case (populates result) ---
        def _click_text(label, timeout=4000):
            loc = page.get_by_text(label, exact=True)
            if loc.count() > 0:
                try:
                    loc.first.click(timeout=timeout)
                    return True
                except Exception as e:
                    print(f"  click '{label}' failed: {str(e)[:60]}")
            return False

        for nav in ("Phân tích EEG", "EEG analysis", "EEG Analysis"):
            if _click_text(nav):
                print(f"  nav -> '{nav}'")
                break
        page.wait_for_timeout(1200)
        for tab in ("Phát lại", "Replay session", "Replay"):
            if _click_text(tab):
                print(f"  tab -> '{tab}'")
                break
        page.wait_for_timeout(1500)

        run = page.get_by_role("button", name=re.compile(r"^(Chạy|Run)$", re.I))
        if run.count() > 0:
            run.first.click()
            print("  clicked Run; waiting for inference...")
            page.wait_for_timeout(8000)  # inference + render
        else:
            print("  no Run button found")

        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "fig_ui.png"))
        print(f"  saved {OUT / 'fig_ui.png'}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
