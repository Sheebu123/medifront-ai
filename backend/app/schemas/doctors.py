"""Schemas for doctor directory listings."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DoctorResponse(BaseModel):
    """Publicly visible doctor profile information for scheduling."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None
    phone: str | None = None
