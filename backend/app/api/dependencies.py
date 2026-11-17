"""Reusable authentication and database-backed role authorization dependencies."""

import logging
from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import SupabaseConfigurationError
from app.db.session import get_db_session
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.supabase_auth import (
    SupabaseInvalidToken,
    SupabaseServiceUnavailable,
    verify_supabase_access_token,
)
from app.services.profiles import ProfileDatabaseUnavailable, get_or_create_profile

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="SupabaseBearer")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid Supabase bearer token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_authenticated_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedUser:
    """Require a bearer token and verify it against the Supabase Auth server."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        auth_user = await verify_supabase_access_token(credentials.credentials)
    except SupabaseInvalidToken:
        raise _unauthorized() from None
    except SupabaseConfigurationError as error:
        logger.error(
            "Supabase Auth configuration is unavailable (%s)",
            type(error).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is temporarily unavailable.",
        ) from None
    except SupabaseServiceUnavailable:
        logger.warning("Supabase Auth could not verify the bearer token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is temporarily unavailable.",
        ) from None

    try:
        user_id = UUID(str(auth_user.get("id", "")))
    except (ValueError, TypeError, AttributeError):
        raise _unauthorized() from None

    return AuthenticatedUser(
        user_id=user_id,
        profile_full_name=_metadata_string(auth_user, "full_name"),
        profile_phone=_metadata_string(auth_user, "phone"),
    )


def _metadata_string(auth_user: dict[str, object], key: str) -> str | None:
    """Read optional contact data; role metadata is deliberately never used."""
    metadata = auth_user.get("user_metadata")
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value if isinstance(value, str) else None


async def get_current_profile(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Profile:
    """Load the caller's Neon profile, creating only a default patient if absent."""
    try:
        profile = await get_or_create_profile(
            session,
            user.user_id,
            full_name=user.profile_full_name,
            phone=user.profile_phone,
        )
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user's profile is incomplete or has an unsupported role.",
        ) from None
    except ProfileDatabaseUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The profile database is temporarily unavailable.",
        ) from None

    if profile.id != user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The profile does not belong to the authenticated user.",
        )
    return profile


def require_roles(*allowed_roles: UserRole) -> Callable[..., Profile]:
    """Build a dependency that authorizes listed roles; admins retain frontend parity."""
    if not allowed_roles:
        raise ValueError("require_roles needs at least one allowed role")
    allowed = frozenset(allowed_roles)

    async def authorize_profile(
        profile: Annotated[Profile, Depends(get_current_profile)],
    ) -> Profile:
        if profile.role != UserRole.ADMIN and profile.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your profile role is not authorized for this resource.",
            )
        return profile

    return authorize_profile
