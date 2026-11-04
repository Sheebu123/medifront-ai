"""Authentication-related API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_authenticated_user, get_current_profile
from app.schemas.auth import AuthMeResponse, AuthenticatedUser, Profile

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me", response_model=AuthMeResponse)
async def read_current_user(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> AuthMeResponse:
    """Return the verified Supabase identity and its caller-visible profile."""
    return AuthMeResponse(user_id=user.user_id, profile=profile)
