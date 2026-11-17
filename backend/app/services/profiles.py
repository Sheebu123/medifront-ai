"""Neon profile lookup and safe first-login provisioning."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import ProfileModel
from app.schemas.auth import Profile


class ProfileDatabaseUnavailable(Exception):
    """Neon could not load or provision the authenticated user's profile."""


def _profile_value(value: str | None) -> str | None:
    """Keep optional Auth presentation fields as trimmed strings only."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


async def get_or_create_profile(
    session: AsyncSession,
    user_id: UUID,
    *,
    full_name: str | None,
    phone: str | None,
) -> Profile:
    """Load the Neon role or create a first-login patient profile.

    Only the verified Auth UUID and non-authoritative contact fields are used.
    The role is always initialized as patient and is never read from Auth metadata.
    """
    try:
        profile = await session.get(ProfileModel, user_id)
        if profile is None:
            profile = ProfileModel(
                id=user_id,
                full_name=_profile_value(full_name),
                phone=_profile_value(phone),
                role="patient",
            )
            session.add(profile)
            try:
                await session.flush()
                await session.commit()
            except IntegrityError:
                # Another request may have created the row after our initial read.
                await session.rollback()
                profile = await session.get(ProfileModel, user_id)
                if profile is None:
                    raise ProfileDatabaseUnavailable from None
        return Profile.model_validate(profile)
    except ProfileDatabaseUnavailable:
        raise
    except SQLAlchemyError:
        await session.rollback()
        raise ProfileDatabaseUnavailable from None
