"""FastAPI entry point for the NeuraTriage backend.

Run from the `backend/` directory:
    uvicorn app.main:app --host 127.0.0.1 --port 8501 --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import FRONTEND_DIR, get_settings


class RevalidatingStaticFiles(StaticFiles):
    """Serve the frontend with `Cache-Control: no-cache`.

    There is no build step here: app.html and the shared/*.js + app/*.jsx
    bundles are separate files that must stay in lockstep. With no explicit
    Cache-Control a browser falls back to heuristic caching and can pair a NEW
    app.html with a STALE i18n.js, which blows up as
    "Cannot read properties of undefined" on the first missing translation key.

    `no-cache` does not disable caching — the ETag still yields a cheap 304 —
    it only forbids reusing a copy without asking the server first.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response
from .database import init_db
from .envelope import (
    EnvelopeError,
    envelope_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .routers import alerts as alerts_router
from .routers import auth as auth_router
from .routers import dashboard as dashboard_router
from .routers import demo as demo_router
from .routers import devices as devices_router
from .routers import files as files_router
from .routers import inference as inference_router
from .routers import live as live_router
from .routers import meta as meta_router
from .routers import patients as patients_router
from .routers import research as research_router
from .routers import sessions as sessions_router
from .routers import reports as reports_router
from .services.model_manager import get_manager
from .services.scheduler import start_scheduler, stop_scheduler
from .ws import stream as stream_ws


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
logger = logging.getLogger("neuratriage.main")


_BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
# Permits the current CDN + in-browser Babel architecture (needs unsafe-eval).
# A real build step would let this tighten to nonces and drop unsafe-*.
_PROD_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.is_production and settings.jwt_secret_is_insecure():
        raise RuntimeError(
            "Refusing to start in production: JWT_SECRET is the dev default or "
            "shorter than 32 chars. Set a strong JWT_SECRET env var — generate "
            'one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )
    init_db()
    logger.info("Database tables verified")
    if settings.auto_load_model_on_startup:
        loaded = get_manager().auto_load(settings.candidate_model_paths())
        if loaded:
            logger.info("Auto-loaded model from %s", loaded)
        else:
            logger.warning("No trained model auto-loaded — /api/infer and WS will 503.")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Shutting down NeuraTriage backend")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        for key, value in _BASE_SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
            response.headers.setdefault("Content-Security-Policy", _PROD_CSP)
        return response

    app.add_exception_handler(EnvelopeError, envelope_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(meta_router.router)
    app.include_router(auth_router.router)
    app.include_router(live_router.router)
    app.include_router(files_router.router)
    app.include_router(inference_router.router)
    app.include_router(devices_router.router)
    app.include_router(demo_router.router)
    app.include_router(sessions_router.router)
    app.include_router(patients_router.router)
    app.include_router(alerts_router.router)
    app.include_router(dashboard_router.router)
    app.include_router(reports_router.router)
    app.include_router(research_router.router)
    app.include_router(stream_ws.router)

    if FRONTEND_DIR.is_dir():
        app.mount(
            "/",
            RevalidatingStaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="frontend",
        )
    else:
        logger.warning("Frontend dir not found at %s — static files not mounted", FRONTEND_DIR)

    return app


app = create_app()
