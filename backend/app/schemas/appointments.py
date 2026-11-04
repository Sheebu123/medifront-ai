"""Pydantic schemas for appointment requests and responses."""

from datetime import date, datetime, time
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AppointmentCreate(BaseModel):
    """Fields a patient may provide when booking an appointment."""

    model_config = ConfigDict(extra="forbid")

    doctor_id: UUID
    appointment_date: date
    appointment_time: time
    reason: str | None = None

    @field_validator("appointment_time")
    @classmethod
    def reject_timezone_on_time(cls, value: time) -> time:
        """The database column is a local SQL TIME without a timezone."""
        if value.tzinfo is not None and value.utcoffset() is not None:
            raise ValueError("appointment_time must not include a timezone")
        return value


class AppointmentStatusUpdate(BaseModel):
    """A status change requested by an authorized staff member."""

    model_config = ConfigDict(extra="forbid")

    status: AppointmentStatus


class AppointmentResponse(BaseModel):
    """The complete appointment row exposed by the current schema."""

    id: UUID
    patient_id: UUID
    doctor_id: UUID
    appointment_date: date
    appointment_time: time
    reason: str | None
    status: AppointmentStatus
    created_at: datetime


class AppointmentSlot(BaseModel):
    """Minimum fields needed to detect a 30-minute booking overlap."""

    appointment_date: date
    appointment_time: time
    status: AppointmentStatus
