"""Authentication and profile response models."""

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr


class UserRole(str, Enum):
    """Roles currently recognized by the MediFront frontend."""

    PATIENT = "patient"
    DOCTOR = "doctor"
    RECEPTIONIST = "receptionist"
    ADMIN = "admin"


class AuthenticatedUser(BaseModel):
    """Supabase-verified identity and request token for RLS-scoped reads."""

    user_id: UUID
    access_token: SecretStr = Field(exclude=True, repr=False)


class Profile(BaseModel):
    """The profile fields already consumed by the Next.js frontend."""

    id: UUID
    full_name: str | None
    phone: str | None
    role: UserRole


class AuthMeResponse(BaseModel):
    """Verified Auth identity plus the corresponding database profile."""

    user_id: UUID
    profile: Profile
