"""Reusable authentication and database-backed role authorization dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import SecretStr, ValidationError

from app.core.config import SupabaseConfigurationError
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.supabase_auth import (
    SupabaseInvalidToken,
    SupabaseProfileAccessDenied,
    SupabaseProfileNotFound,
    SupabaseServiceUnavailable,
    fetch_supabase_profile,
    verify_supabase_access_token,
)

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
    except (SupabaseConfigurationError, SupabaseServiceUnavailable):
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
        access_token=SecretStr(credentials.credentials),
    )


async def get_current_profile(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
) -> Profile:
    """Load the current user's profile through RLS using their verified token."""
    try:
        data = await fetch_supabase_profile(
            user.user_id,
            user.access_token.get_secret_value(),
        )
    except SupabaseProfileNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No visible profile exists for this user.",
        ) from None
    except SupabaseProfileAccessDenied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The profile is not accessible to this user.",
        ) from None
    except (SupabaseConfigurationError, SupabaseServiceUnavailable):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase profile service is temporarily unavailable.",
        ) from None

    try:
        profile = Profile.model_validate(data)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user's profile is incomplete or has an unsupported role.",
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
