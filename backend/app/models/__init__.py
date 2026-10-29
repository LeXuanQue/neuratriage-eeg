"""SQLAlchemy 2.0 ORM models — single module to keep cross-references trivial.

Spec: NeuraTriage_Backend_Master_Prompt.md §5.

All primary keys are UUID hex strings, generated server-side at insert time so
the WebSocket layer can reuse a `session_id` it has already shown to the
client.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _uuid() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────
# Patient + EmergencyContact
# ─────────────────────────────────────────────────────────────────────────


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    mrn: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    bed: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    onset_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    diagnosis_history: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    doctor_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    contacts: Mapped[List["EmergencyContact"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[List["EEGSession"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )


class EmergencyContact(Base):
    __tablename__ = "emergency_contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    notify_on_alert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_weekly_report: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    patient: Mapped[Patient] = relationship(back_populates="contacts")


# ─────────────────────────────────────────────────────────────────────────
# Device
# ─────────────────────────────────────────────────────────────────────────


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mac_address: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    channels: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    fs: Mapped[float] = mapped_column(Float, default=256.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    patient_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ─────────────────────────────────────────────────────────────────────────
# EEGSession + Alert
# ─────────────────────────────────────────────────────────────────────────


class EEGSession(Base):
    __tablename__ = "eeg_sessions"

    # Primary key is the session_id we hand to the WebSocket — keeping the
    # value identical avoids a join when persisting alerts.
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    patient_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_channels: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    fs: Mapped[float] = mapped_column(Float, default=256.0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_windows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_windows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sqi_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    raw_data_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    patient: Mapped[Optional[Patient]] = relationship(back_populates="sessions")
    alerts: Mapped[List["Alert"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("eeg_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    timestamp_sec: Mapped[float] = mapped_column(Float, nullable=False)
    alert_class: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    probabilities_smooth: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    sqi_total: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    session: Mapped[EEGSession] = relationship(back_populates="alerts")


# ─────────────────────────────────────────────────────────────────────────
# WeeklyReport — tracks generated + sent reports
# ─────────────────────────────────────────────────────────────────────────


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    patient_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)  # "YYYY-MM-DD"
    week_label: Mapped[str] = mapped_column(String(20), nullable=False)  # "W19 · 2026"
    session_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ack_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sqi_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pdf_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    recipient_emails: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )


__all__ = [
    "Base",
    "Patient",
    "EmergencyContact",
    "Device",
    "EEGSession",
    "Alert",
    "WeeklyReport",
]
