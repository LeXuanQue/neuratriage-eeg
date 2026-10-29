"""Alert endpoints (Master Prompt §6.3 alerts subsection)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import DemoUser
from ..database import get_db
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..models import Alert, EEGSession, Patient


router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _alert_to_out(a: Alert, patient: Optional[Patient] = None) -> dict:
    return {
        "id": a.id,
        "session_id": a.session_id,
        "patient_id": a.patient_id,
        "patient_name": patient.full_name if patient else None,
        "patient_bed": patient.bed if patient else None,
        "timestamp_sec": a.timestamp_sec,
        "alert_class": a.alert_class,
        "status": a.status,
        "probabilities_smooth": a.probabilities_smooth,
        "sqi_total": a.sqi_total,
        "acknowledged": a.acknowledged,
        "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at,
        "dismissed": a.dismissed,
        "created_at": a.created_at,
    }


@router.get("")
def list_alerts(
    since_hours: float = Query(24.0, ge=0, le=24 * 365),
    alert_class: Optional[str] = Query(None),
    only_open: bool = Query(False),
    patient_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    stmt = (
        select(Alert)
        .where(Alert.created_at >= cutoff)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    if alert_class:
        stmt = stmt.where(Alert.alert_class == alert_class)
    if only_open:
        stmt = stmt.where(Alert.acknowledged.is_(False), Alert.dismissed.is_(False))
    if patient_id:
        stmt = stmt.where(Alert.patient_id == patient_id)

    alerts = db.execute(stmt).scalars().all()

    patient_ids = {a.patient_id for a in alerts if a.patient_id}
    patients_by_id: dict[str, Patient] = {}
    if patient_ids:
        rows = (
            db.execute(select(Patient).where(Patient.id.in_(patient_ids)))
            .scalars()
            .all()
        )
        patients_by_id = {p.id: p for p in rows}

    return ok([_alert_to_out(a, patients_by_id.get(a.patient_id)) for a in alerts])


class AckBody(BaseModel):
    note: Optional[str] = None


class AssignPatientBody(BaseModel):
    patient_id: str
    scope: Literal["alert", "session"] = "session"


def _get_alert_or_404(db: Session, alert_id: str) -> Alert:
    alert = db.execute(select(Alert).where(Alert.id == alert_id)).scalar_one_or_none()
    if not alert:
        raise EnvelopeError(f"Alert {alert_id} not found", "ALERT_NOT_FOUND", 404)
    return alert


@router.post("/{alert_id}/ack")
def ack_alert(
    alert_id: str,
    body: AckBody = Body(default_factory=AckBody),
    db: Session = Depends(get_db),
    user: DemoUser = Depends(get_current_user),
):
    alert = _get_alert_or_404(db, alert_id)
    alert.acknowledged = True
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return ok(_alert_to_out(alert))


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    user: DemoUser = Depends(get_current_user),
):
    alert = _get_alert_or_404(db, alert_id)
    alert.dismissed = True
    alert.acknowledged_by = user.id
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return ok(_alert_to_out(alert))


@router.post("/{alert_id}/assign-patient")
def assign_patient_to_alert(
    alert_id: str,
    body: AssignPatientBody,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    alert = _get_alert_or_404(db, alert_id)
    patient = (
        db.execute(select(Patient).where(Patient.id == body.patient_id))
        .scalar_one_or_none()
    )
    if not patient:
        raise EnvelopeError(
            f"Patient {body.patient_id} not found", "PATIENT_NOT_FOUND", 404
        )

    updated_alerts = 1
    if body.scope == "session":
        rows = (
            db.execute(select(Alert).where(Alert.session_id == alert.session_id))
            .scalars()
            .all()
        )
        updated_alerts = len(rows)
        for row in rows:
            row.patient_id = patient.id

        session_row = (
            db.execute(select(EEGSession).where(EEGSession.id == alert.session_id))
            .scalar_one_or_none()
        )
        if session_row:
            session_row.patient_id = patient.id
    else:
        alert.patient_id = patient.id

    db.commit()
    db.refresh(alert)
    return ok(
        {
            "alert": _alert_to_out(alert, patient),
            "patient": {"id": patient.id, "full_name": patient.full_name, "bed": patient.bed},
            "scope": body.scope,
            "updated_alerts": updated_alerts,
        }
    )
