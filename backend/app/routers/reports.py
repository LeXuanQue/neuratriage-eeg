"""Reports endpoints — Phase 4.

POST /api/reports/generate          on-demand generate + email
GET  /api/reports                   list reports (all or by patient)
GET  /api/reports/{report_id}       single report metadata
GET  /api/reports/{report_id}/pdf   download PDF file
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..models import WeeklyReport
from ..services.report_service import REPORTS_DIR, generate_and_save

logger = logging.getLogger("neuratriage.reports")
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _report_out(r: WeeklyReport) -> dict:
    return {
        "id": r.id,
        "patient_id": r.patient_id,
        "patient_name": r.patient_name,
        "week_start": r.week_start,
        "week_label": r.week_label,
        "session_count": r.session_count,
        "alert_count": r.alert_count,
        "ack_count": r.ack_count,
        "escalation_count": r.escalation_count,
        "sqi_mean": r.sqi_mean,
        "pdf_size_bytes": r.pdf_size_bytes,
        "status": r.status,
        "recipient_emails": r.recipient_emails or [],
        "sent_at": r.sent_at,
        "error_message": r.error_message,
        "created_at": r.created_at,
    }


class GenerateBody(BaseModel):
    patient_id: str
    week_start: str  # "YYYY-MM-DD"
    send_email: bool = True


@router.post("/generate")
def generate_report(
    body: GenerateBody,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    try:
        week_start = date.fromisoformat(body.week_start)
    except ValueError:
        raise EnvelopeError("week_start must be YYYY-MM-DD", "INVALID_DATE", 422)

    try:
        report = generate_and_save(db, body.patient_id, week_start, body.send_email)
    except ValueError as exc:
        raise EnvelopeError(str(exc), "NOT_FOUND", 404)

    return ok(_report_out(report))


@router.get("")
def list_reports(
    patient_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(WeeklyReport).order_by(WeeklyReport.created_at.desc()).limit(limit)
    if patient_id:
        stmt = stmt.where(WeeklyReport.patient_id == patient_id)
    reports = db.execute(stmt).scalars().all()
    return ok([_report_out(r) for r in reports])


@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    report = db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    ).scalar_one_or_none()
    if not report:
        raise EnvelopeError(f"Report {report_id} not found", "NOT_FOUND", 404)
    return ok(_report_out(report))


@router.get("/{report_id}/pdf")
def download_pdf(
    report_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    report = db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    ).scalar_one_or_none()
    if not report:
        raise EnvelopeError(f"Report {report_id} not found", "NOT_FOUND", 404)
    if not report.pdf_path:
        raise EnvelopeError("PDF file not found on disk", "PDF_NOT_FOUND", 404)
    # pdf_path is a DB string; confine it to REPORTS_DIR so a tampered row can
    # never make this endpoint serve an arbitrary file off disk.
    pdf = Path(report.pdf_path).resolve()
    try:
        pdf.relative_to(REPORTS_DIR.resolve())
    except ValueError:
        raise EnvelopeError("PDF path outside reports directory", "PDF_PATH_INVALID", 403)
    if not pdf.is_file():
        raise EnvelopeError("PDF file not found on disk", "PDF_NOT_FOUND", 404)

    safe_name = (report.patient_name or "report").replace(" ", "_")
    safe_week = (report.week_label or "week").replace(" ", "_").replace("/", "-")
    filename = f"neuratriage_{safe_week}_{safe_name}.pdf"
    return FileResponse(path=str(pdf), media_type="application/pdf", filename=filename)
