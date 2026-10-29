"""Static frontend assets must always be revalidated.

The app has no build step: `app.html` and the `shared/*.js` + `app/*.jsx` bundles
are served straight off disk and must stay in lockstep. Without an explicit
Cache-Control the browser applies heuristic caching, so it can serve a NEW
app.html against a STALE i18n.js -- which crashes the app with
"Cannot read properties of undefined (reading 'title')" because `t.demo` is
missing. `no-cache` still allows a 304 via ETag; it only forbids using a cached
copy without asking.

Run: .venv/Scripts/python.exe -m pytest backend/tests/test_static_cache.py -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


ASSETS = ["/app.html", "/shared/i18n.js", "/app/screen-demo.jsx"]


@pytest.mark.unit
@pytest.mark.parametrize("path", ASSETS)
def test_frontend_assets_are_served(path: str) -> None:
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 200, path


@pytest.mark.unit
@pytest.mark.parametrize("path", ASSETS)
def test_frontend_assets_must_revalidate(path: str) -> None:
    with TestClient(app) as client:
        r = client.get(path)
    cache_control = r.headers.get("cache-control", "")
    assert "no-cache" in cache_control, (path, cache_control)


@pytest.mark.unit
def test_assets_still_support_etag_revalidation() -> None:
    """no-cache must not mean no-store: a 304 round trip should still work."""
    with TestClient(app) as client:
        first = client.get("/shared/i18n.js")
        etag = first.headers.get("etag")
        assert etag, "static files should carry an ETag"
        second = client.get("/shared/i18n.js", headers={"If-None-Match": etag})
    assert second.status_code == 304
