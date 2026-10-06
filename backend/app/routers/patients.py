"""Patient + EmergencyContact CRUD (Master Prompt §6.3)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import DemoUser
from ..database import get_db
from ..deps import get_current_user
from ..envelope import EnvelopeError, ok
from ..models import EmergencyContact, Patient


router = APIRouter(prefix="/api/patients", tags=["patients"])


# ── Schemas ──────────────────────────────────────────────────────────────


class ContactIn(BaseModel):
    name: str
    relationship_label: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notify_on_alert: bool = True
    notify_weekly_report: bool = True


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    relationship_label: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notify_on_alert: Optional[bool] = None
    notify_weekly_report: Optional[bool] = None


class PatientIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=160)
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = Field(None, max_length=8)
    mrn: Optional[str] = Field(None, max_length=64)
    bed: Optional[str] = Field(None, max_length=32)
    onset_minutes: Optional[int] = None
    diagnosis_history: Optional[Any] = None
    doctor_id: Optional[str] = None
    notes: Optional[str] = None


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = None
    mrn: Optional[str] = None
    bed: Optional[str] = None
    onset_minutes: Optional[int] = None
    diagnosis_history: Optional[Any] = None
    doctor_id: Optional[str] = None
    notes: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────────


def _contact_to_out(c: EmergencyContact) -> dict:
    return {
        "id": c.id,
        "patient_id": c.patient_id,
        "name": c.name,
        "relationship_label": c.relationship_label,
        "phone": c.phone,
        "email": c.email,
        "notify_on_alert": c.notify_on_alert,
        "notify_weekly_report": c.notify_weekly_report,
        "created_at": c.created_at,
    }


def _patient_to_out(p: Patient) -> dict:
    return {
        "id": p.id,
        "full_name": p.full_name,
        "date_of_birth": p.date_of_birth,
        "gender": p.gender,
        "mrn": p.mrn,
        "bed": p.bed,
        "onset_minutes": p.onset_minutes,
        "diagnosis_history": p.diagnosis_history,
        "doctor_id": p.doctor_id,
        "notes": p.notes,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "contacts": [_contact_to_out(c) for c in (p.contacts or [])],
    }


def _get_patient_or_404(db: Session, patient_id: str) -> Patient:
    stmt = (
        select(Patient)
        .options(selectinload(Patient.contacts))
        .where(Patient.id == patient_id)
    )
    patient = db.execute(stmt).scalar_one_or_none()
    if not patient:
        raise EnvelopeError(f"Patient {patient_id} not found", "PATIENT_NOT_FOUND", 404)
    return patient


# ── Patient CRUD ─────────────────────────────────────────────────────────


@router.get("")
def list_patients(
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    stmt = (
        select(Patient)
        .options(selectinload(Patient.contacts))
        .order_by(Patient.created_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return ok([_patient_to_out(p) for p in rows])


@router.post("")
def create_patient(
    body: PatientIn = Body(...),
    db: Session = Depends(get_db),
    user: DemoUser = Depends(get_current_user),
):
    payload = body.model_dump()
    if not payload.get("doctor_id"):
        payload["doctor_id"] = user.id
    if payload.get("mrn"):
        existing = db.execute(
            select(Patient).where(Patient.mrn == payload["mrn"])
        ).scalar_one_or_none()
        if existing:
            raise EnvelopeError(
                f"MRN '{payload['mrn']}' already exists", "MRN_TAKEN", 409
            )
    patient = Patient(**payload)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return ok(_patient_to_out(patient), status_code=201)


@router.get("/{patient_id}")
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    return ok(_patient_to_out(_get_patient_or_404(db, patient_id)))


@router.put("/{patient_id}")
def update_patient(
    patient_id: str,
    body: PatientUpdate = Body(...),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    patient = _get_patient_or_404(db, patient_id)
    diff = body.model_dump(exclude_unset=True)
    for field, value in diff.items():
        setattr(patient, field, value)
    db.commit()
    db.refresh(patient)
    return ok(_patient_to_out(patient))


@router.delete("/{patient_id}")
def delete_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    patient = _get_patient_or_404(db, patient_id)
    db.delete(patient)
    db.commit()
    return ok({"deleted": patient_id})


# ── Contacts ─────────────────────────────────────────────────────────────


@router.get("/{patient_id}/contacts")
def list_contacts(
    patient_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    patient = _get_patient_or_404(db, patient_id)
    return ok([_contact_to_out(c) for c in patient.contacts])


@router.post("/{patient_id}/contacts")
def add_contact(
    patient_id: str,
    body: ContactIn = Body(...),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    _get_patient_or_404(db, patient_id)
    contact = EmergencyContact(patient_id=patient_id, **body.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ok(_contact_to_out(contact), status_code=201)


@router.put("/{patient_id}/contacts/{contact_id}")
def update_contact(
    patient_id: str,
    contact_id: str,
    body: ContactUpdate = Body(...),
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    contact = db.execute(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id,
            EmergencyContact.patient_id == patient_id,
        )
    ).scalar_one_or_none()
    if not contact:
        raise EnvelopeError("Contact not found", "CONTACT_NOT_FOUND", 404)
    diff = body.model_dump(exclude_unset=True)
    for field, value in diff.items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return ok(_contact_to_out(contact))


@router.delete("/{patient_id}/contacts/{contact_id}")
def delete_contact(
    patient_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    _: DemoUser = Depends(get_current_user),
):
    contact = db.execute(
        select(EmergencyContact).where(
            EmergencyContact.id == contact_id,
            EmergencyContact.patient_id == patient_id,
        )
    ).scalar_one_or_none()
    if not contact:
        raise EnvelopeError("Contact not found", "CONTACT_NOT_FOUND", 404)
    db.delete(contact)
    db.commit()
    return ok({"deleted": contact_id})
