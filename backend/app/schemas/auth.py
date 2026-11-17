"""Authentication and profile response models."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserRole(str, Enum):
    """Roles currently recognized by the MediFront frontend."""

    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class AuthenticatedUser(BaseModel):
    """Supabase-verified identity plus optional presentation fields for onboarding."""

    user_id: UUID
    profile_full_name: str | None = Field(default=None, exclude=True, repr=False)
    profile_phone: str | None = Field(default=None, exclude=True, repr=False)


class Profile(BaseModel):
    """The profile fields already consumed by the Next.js frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str | None
    phone: str | None
    role: UserRole


class AuthMeResponse(BaseModel):
    """Verified Auth identity plus the corresponding database profile."""

    user_id: UUID
    profile: Profile
