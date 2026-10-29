"""APScheduler weekly report cron — started in FastAPI lifespan."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from ..config import get_settings
from ..database import SessionLocal
from ..models import Patient
from .report_service import generate_and_save

logger = logging.getLogger("neuratriage.scheduler")

_scheduler: BackgroundScheduler | None = None


def _send_weekly_reports() -> None:
    """Job: generate + email reports for all patients. Runs every Monday 07:00."""
    logger.info("Weekly report job started")
    # Previous Monday (7 days ago from this Monday)
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 7)

    db = SessionLocal()
    try:
        patients = db.execute(select(Patient)).scalars().all()
        for patient in patients:
            try:
                report = generate_and_save(db, patient.id, week_start, send_email=True)
                logger.info(
                    "Report %s generated for patient %s — status: %s",
                    report.id, patient.id, report.status,
                )
            except Exception as exc:
                logger.error("Report failed for patient %s: %s", patient.id, exc)
    finally:
        db.close()
    logger.info("Weekly report job finished")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    settings = get_settings()
    _scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")
    _scheduler.add_job(
        _send_weekly_reports,
        CronTrigger(
            day_of_week=settings.weekly_report_dow,
            hour=settings.weekly_report_hour,
            minute=0,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id="weekly_reports",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — weekly reports every %s at %02d:00 Asia/Ho_Chi_Minh",
        settings.weekly_report_dow,
        settings.weekly_report_hour,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
