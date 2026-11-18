"""getApiBase() in frontend/shared/live-data.js, run under Node with a minimal browser stub.

Regression 2026-11-17: the backend serves the UI on :8501, but getApiBase() always
returned http://127.0.0.1:8501, so opening http://localhost:8501 made every API call
cross-origin and the login failed with a CORS error.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest

LIVE_DATA = Path(__file__).resolve().parents[1] / "frontend" / "shared" / "live-data.js"
NODE = shutil.which("node")

HARNESS = r"""
const fs = require("fs");
const [file, hostname, port, saved, override] = process.argv.slice(1);  // `node -e` has no script path
const store = {};
if (saved !== "__none__") store["neuratriage_api_base"] = saved;
global.window = {};
if (override !== "__none__") global.window.API_BASE_URL = override;
global.location = { hostname, port };
global.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
global.React = { useState: () => [null, () => {}], useEffect: () => {}, useRef: () => ({}) };
eval(fs.readFileSync(file, "utf8"));
process.stdout.write(JSON.stringify(window.LiveData.getApiBase()));
"""


def _api_base(hostname: str, port: str, saved: Optional[str] = None, override: Optional[str] = None) -> str:
    out = subprocess.run(
        [NODE, "-e", HARNESS, str(LIVE_DATA), hostname, port, saved or "__none__", override or "__none__"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


@pytest.mark.unit
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1"])
def test_page_served_by_the_backend_uses_same_origin(host: str) -> None:
    assert _api_base(host, "8501") == ""


@pytest.mark.unit
def test_stale_saved_default_does_not_force_cross_origin() -> None:
    assert _api_base("localhost", "8501", saved="http://127.0.0.1:8501") == ""


@pytest.mark.unit
def test_static_preview_server_still_targets_the_backend() -> None:
    assert _api_base("localhost", "8000") == "http://127.0.0.1:8501"


@pytest.mark.unit
def test_custom_saved_base_and_explicit_override_win() -> None:
    assert _api_base("localhost", "8501", saved="https://api.example.org") == "https://api.example.org"
    assert _api_base("localhost", "8501", override="https://x.example.org") == "https://x.example.org"
