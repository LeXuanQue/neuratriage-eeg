"""Demo-mode endpoints — guided scenarios that need no real headset.

The frontend uses these to offer a first-time viewer a runnable tour of the
system: pick a scenario, and the Live screen streams the matching stored EEG
case through the normal WebSocket + detector path.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_current_user
from ..envelope import ok
from ..services.demo_scenarios import get_demo_scenario, list_demo_scenarios


router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/scenarios")
def demo_scenarios(_=Depends(get_current_user)):
    return ok(list_demo_scenarios())


@router.get("/scenarios/{scenario_id}")
def demo_scenario(scenario_id: str, _=Depends(get_current_user)):
    scenario = get_demo_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown demo scenario: {scenario_id}",
        )
    return ok(scenario)
