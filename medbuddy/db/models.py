"""ORM models for the six MedBuddy tables (see CLAUDE.md → DB tables planned).

One WhatsApp number == one patient (no multi-tenant auth, per scope).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    wa_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120), default=None)
    age: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    image_ref: Mapped[str | None] = mapped_column(String(255), default=None)
    raw_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="prescriptions")
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan"
    )


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(ForeignKey("prescriptions.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))  # as written on the script
    generic: Mapped[str | None] = mapped_column(String(120), default=None)
    dosage: Mapped[str | None] = mapped_column(String(60), default=None)
    frequency: Mapped[str | None] = mapped_column(String(60), default=None)
    duration: Mapped[str | None] = mapped_column(String(60), default=None)
    matched: Mapped[bool] = mapped_column(default=False)  # grounding gate (see schemas.py)

    prescription: Mapped[Prescription] = relationship(back_populates="medications")


class Interaction(Base):
    """A flagged drug-drug interaction for one patient (audit trail of what we warned about)."""

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    drug_a: Mapped[str] = mapped_column(String(120))
    drug_b: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(20))  # minor | moderate | major
    description: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    medication_id: Mapped[int | None] = mapped_column(ForeignKey("medications.id"), default=None)
    scheduled_for: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|sent|acked|missed
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)


class AdherenceLog(Base):
    __tablename__ = "adherence_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id"), default=None)
    response: Mapped[str] = mapped_column(String(20))  # taken | missed | snooze
    logged_at: Mapped[datetime] = mapped_column(default=_utcnow)
