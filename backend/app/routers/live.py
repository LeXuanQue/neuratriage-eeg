"""GET /api/live - neutral waiting frame.

Realtime model evidence must come from the WebSocket stream or a replay/device
pipeline. This legacy endpoint intentionally does not fabricate probabilities,
patients, device status, SQI, or feature metrics.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Query

from ..envelope import ok


router = APIRouter(prefix="/api", tags=["live"])

CLASS_KEYS = ("NS", "IS", "HS")


@router.get("/live")
def live(scenario: str = Query("HS"), ts: str | None = Query(default=None)):
    s = (scenario or "HS").upper()
    if s not in CLASS_KEYS:
        s = "HS"
    now = time.time()
    return ok(
        {
            "source": "waiting",
            "timestamp_ms": int(now * 1000),
            "scenario": s,
            "mode": s,
            "status": "waiting",
            "dominant": "NS",
            "probabilities": {"NS": 1 / 3, "IS": 1 / 3, "HS": 1 / 3},
            "sqi": None,
            "has_model_event": False,
            "time_to_alert_sec": None,
            "patient": {},
            "device": {
                "name": "No measured source",
                "sample_rate": 256,
                "battery": None,
                "channels": 0,
                "stream": "waiting",
            },
            "history": [
                {"t": i - 79, "NS": 1 / 3, "IS": 1 / 3, "HS": 1 / 3}
                for i in range(80)
            ],
            "features": [],
            "metrics": {},
        }
    )
