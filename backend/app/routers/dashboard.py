"""GET /api/dashboard/summary — KPI tiles + active bed list for the dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..auth import DemoUser
from ..database import get_db
from ..deps import get_current_user
from ..envelope import ok
from ..models import Alert, EEGSession
from ..services.session_manager import get_session_manager


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _format_duration(start: datetime, end: Optional[datetime]) -> str:
    def as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    delta = (as_utc(end) if end else datetime.now(timezone.utc)) - as_utc(start)
    secs = max(0, int(delta.total_seconds()))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    since_today = now - timedelta(hours=24)

    active_ids = set(get_session_manager().list_active_sessions())
    active_sessions_all = db.execute(
        select(EEGSession)
        .options(selectinload(EEGSession.patient))
        .where(EEGSession.ended_at.is_(None))
        .order_by(EEGSession.started_at.desc())
    ).scalars().all()
    # Rows can be left open if the dev server/tunnel is killed. The dashboard
    # should show streams active in this process, not stale historical rows.
    active_sessions = [s for s in active_sessions_all if s.id in active_ids]

    alerts_today = db.execute(
        select(func.count(Alert.id)).where(Alert.created_at >= since_today)
    ).scalar_one()

    by_class_rows = db.execute(
        select(Alert.alert_class, func.count(Alert.id))
        .where(Alert.created_at >= since_today)
        .group_by(Alert.alert_class)
    ).all()
    alerts_by_class = {cls: count for cls, count in by_class_rows}

    open_alerts = db.execute(
        select(func.count(Alert.id)).where(
            Alert.acknowledged.is_(False),
            Alert.dismissed.is_(False),
        )
    ).scalar_one()

    # Median seconds from alert creation to acknowledgement (last 200 acked alerts)
    acked_rows = db.execute(
        select(Alert.created_at, Alert.acknowledged_at)
        .where(Alert.acknowledged.is_(True), Alert.acknowledged_at.isnot(None))
        .order_by(Alert.acknowledged_at.desc())
        .limit(200)
    ).all()
    median_ttd_sec: Optional[float] = None
    if acked_rows:
        deltas = sorted(
            (row.acknowledged_at - row.created_at).total_seconds()
            for row in acked_rows
            if row.acknowledged_at and row.created_at
        )
        if deltas:
            mid = len(deltas) // 2
            median_ttd_sec = deltas[mid] if len(deltas) % 2 else (deltas[mid - 1] + deltas[mid]) / 2

    beds: list[dict] = []
    for s in active_sessions:
        latest_alert = db.execute(
            select(Alert)
            .where(Alert.session_id == s.id)
            .order_by(Alert.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        dominant = None
        prob = None
        if latest_alert and latest_alert.probabilities_smooth:
            try:
                ps = list(latest_alert.probabilities_smooth)
                names = ["NS", "IS"]
                binary_ps = ps[:2]
                idx = max(range(len(binary_ps)), key=lambda i: binary_ps[i])
                dominant = names[idx] if idx < len(names) else None
                total = float(sum(binary_ps)) or 1.0
                prob = float(binary_ps[idx]) / total
            except (TypeError, ValueError):
                pass

        patient = s.patient
        beds.append(
            {
                "session_id": s.id,
                "patient_id": s.patient_id,
                "patient_name": patient.full_name if patient else None,
                "bed": patient.bed if patient else None,
                "duration": _format_duration(s.started_at, s.ended_at),
                "sqi": s.sqi_mean,
                "alert_count": s.alert_count,
                "dominant": dominant,
                "prob": prob,
                "alert_class": latest_alert.alert_class if latest_alert else None,
                "status": (
                    "open"
                    if latest_alert
                    and not latest_alert.acknowledged
                    and not latest_alert.dismissed
                    else "monitor"
                ),
            }
        )

    return ok(
        {
            "active_session_count": len(active_sessions),
            "alerts_today": alerts_today,
            "alerts_by_class": alerts_by_class,
            "open_alerts": open_alerts,
            "median_time_to_decision_sec": median_ttd_sec,
            "beds": beds,
        }
    )
