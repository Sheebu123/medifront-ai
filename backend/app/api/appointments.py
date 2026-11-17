"""Role-scoped appointment management endpoints."""

from collections.abc import Awaitable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_authenticated_user, get_current_profile
from app.db.session import get_db_session
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentStatusUpdate,
)
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.appointments import (
    AppointmentConflict,
    AppointmentDataUnavailable,
    AppointmentInPast,
    AppointmentNotFound,
    InvalidDoctor,
    InvalidPatient,
    create_appointment,
    get_appointment,
    list_appointments,
    update_appointment_status,
)

router = APIRouter(prefix="/api/v1", tags=["appointments"])
T = TypeVar("T")


async def _service_result(operation: Awaitable[T]) -> T:
    """Translate appointment domain errors into stable API responses."""
    try:
        return await operation
    except InvalidPatient:
        raise HTTPException(
            status_code=403,
            detail="Only patients can book appointments.",
        ) from None
    except (InvalidDoctor, AppointmentInPast) as error:
        detail = (
            "doctor_id must identify a doctor profile."
            if isinstance(error, InvalidDoctor)
            else "The appointment date and time must be in the future."
        )
        raise HTTPException(status_code=422, detail=detail) from None
    except AppointmentNotFound:
        raise HTTPException(status_code=404, detail="Appointment not found.") from None
    except AppointmentConflict:
        raise HTTPException(
            status_code=409,
            detail="The appointment conflicts with an existing booking or status change.",
        ) from None
    except AppointmentDataUnavailable:
        raise HTTPException(
            status_code=503,
            detail="The appointment database is temporarily unavailable.",
        ) from None


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    request: AppointmentCreate,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AppointmentResponse:
    """Book an appointment for the authenticated patient only."""
    if profile.role != UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can book appointments.")
    return await _service_result(create_appointment(session, user.user_id, request))


@router.get("/appointments", response_model=list[AppointmentResponse])
async def read_appointments(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AppointmentResponse]:
    """List appointments visible to the caller's role and identity."""
    return await _service_result(list_appointments(session, profile.role, user.user_id))


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def read_appointment(
    appointment_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AppointmentResponse:
    """Get one appointment only when it falls within the caller's scope."""
    return await _service_result(
        get_appointment(session, appointment_id, profile.role, user.user_id)
    )


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
async def cancel_appointment(
    appointment_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AppointmentResponse:
    """Cancel an owned patient appointment or any appointment as staff."""
    if profile.role not in {
        UserRole.PATIENT,
        UserRole.RECEPTIONIST,
        UserRole.ADMIN,
    }:
        raise HTTPException(
            status_code=403,
            detail="Your profile role is not authorized to cancel appointments.",
        )
    return await _service_result(
        update_appointment_status(
            session,
            appointment_id,
            profile.role,
            user.user_id,
            AppointmentStatus.CANCELLED,
            cancellation=True,
        )
    )


@router.patch(
    "/appointments/{appointment_id}/status",
    response_model=AppointmentResponse,
)
async def change_appointment_status(
    appointment_id: UUID,
    request: AppointmentStatusUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AppointmentResponse:
    """Let receptionists and admins set one of the supported statuses."""
    if profile.role not in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        raise HTTPException(
            status_code=403,
            detail="Only receptionists and admins can update appointment statuses.",
        )
    return await _service_result(
        update_appointment_status(
            session,
            appointment_id,
            profile.role,
            user.user_id,
            request.status,
        )
    )
