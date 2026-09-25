"""Small data-access helpers so tools/agent code doesn't hand-write queries."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from medbuddy.db.models import Medication, Patient, Prescription


def get_or_create_patient(session: Session, wa_number: str) -> Patient:
    patient = session.scalar(select(Patient).where(Patient.wa_number == wa_number))
    if patient is None:
        patient = Patient(wa_number=wa_number)
        session.add(patient)
        session.flush()  # assign id without committing
    return patient


def set_profile(session: Session, patient: Patient, name: str | None, age: int | None) -> Patient:
    if name is not None:
        patient.name = name
    if age is not None:
        patient.age = age
    session.flush()
    return patient


def save_prescription(
    session: Session,
    patient_id: int,
    *,
    raw_text: str | None,
    medications: list[dict],
    image_ref: str | None = None,
) -> Prescription:
    """Persist a prescription plus its medications.

    `medications` items may carry: name, generic, dosage, frequency, duration, matched.
    """
    rx = Prescription(patient_id=patient_id, raw_text=raw_text, image_ref=image_ref)
    session.add(rx)
    session.flush()
    for m in medications:
        session.add(
            Medication(
                prescription_id=rx.id,
                name=m["name"],
                generic=m.get("generic"),
                dosage=m.get("dosage"),
                frequency=m.get("frequency"),
                duration=m.get("duration"),
                matched=bool(m.get("matched", False)),
            )
        )
    session.flush()
    return rx


def latest_medications(session: Session, patient_id: int) -> list[Medication]:
    """Medications from a patient's most recent prescription (what 'my meds' means)."""
    rx = session.scalar(
        select(Prescription)
        .where(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
        .limit(1)
    )
    if rx is None:
        return []
    return list(
        session.scalars(select(Medication).where(Medication.prescription_id == rx.id))
    )
