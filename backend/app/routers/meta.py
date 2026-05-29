"""GET /api/health, GET /api/disclaimer (port from api/index.py:148-161)."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import get_settings
from ..envelope import ok


router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    s = get_settings()
    return ok({"status": "ok", "app": s.app_name, "version": s.app_version})


@router.get("/disclaimer")
def disclaimer():
    return ok(
        {
            "text": (
                "For research use only. Not validated for clinical diagnosis. "
                "Always consult a qualified physician for any medical decisions."
            ),
            "version": "1.0",
        }
    )
