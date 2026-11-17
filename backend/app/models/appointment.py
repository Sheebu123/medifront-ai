"""Appointment ORM model and database-enforced booking invariants."""

from datetime import date, datetime, time
from uuid import UUID as PythonUUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.elements import TextClause

from app.db.base import Base


_ACTIVE_WINDOW: TextClause = text(
    "tsrange(appointment_date + appointment_time, "
    "appointment_date + appointment_time + interval '30 minutes', '[)')"
)
_ACTIVE_STATUSES = text("status IN ('scheduled', 'confirmed')")


class AppointmentModel(Base):
    """Appointment record with fixed 30-minute active slot conflicts."""

    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'cancelled', 'completed')",
            name="ck_appointments_status",
        ),
        ExcludeConstraint(
            ("patient_id", "="),
            (_ACTIVE_WINDOW, "&&"),
            where=_ACTIVE_STATUSES,
            name="ex_appointments_patient_no_overlap",
        ),
        ExcludeConstraint(
            ("doctor_id", "="),
            (_ACTIVE_WINDOW, "&&"),
            where=_ACTIVE_STATUSES,
            name="ex_appointments_doctor_no_overlap",
        ),
        Index(
            "ix_appointments_patient_schedule",
            "patient_id",
            "appointment_date",
            "appointment_time",
        ),
        Index(
            "ix_appointments_doctor_schedule",
            "doctor_id",
            "appointment_date",
            "appointment_time",
        ),
        Index("ix_appointments_status", "status"),
    )

    id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    patient_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "profiles.id",
            ondelete="RESTRICT",
            name="fk_appointments_patient_id_profiles",
        ),
        nullable=False,
    )
    doctor_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "profiles.id",
            ondelete="RESTRICT",
            name="fk_appointments_doctor_id_profiles",
        ),
        nullable=False,
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False)
    appointment_time: Mapped[time] = mapped_column(Time(timezone=False), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'scheduled'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
