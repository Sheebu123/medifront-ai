"""Doctor directory endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_user
from app.db.session import get_db_session
from app.schemas.auth import AuthenticatedUser
from app.schemas.doctors import DoctorResponse
from app.services.doctors import DoctorDataUnavailable, list_doctors

router = APIRouter(prefix="/api/v1", tags=["doctors"])


@router.get("/doctors", response_model=list[DoctorResponse])
async def read_doctors(
    _: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DoctorResponse]:
    """Return verified doctor profiles for appointment scheduling."""
    try:
        return await list_doctors(session)
    except DoctorDataUnavailable:
        raise HTTPException(
            status_code=503,
            detail="The doctor directory is temporarily unavailable.",
        ) from None
