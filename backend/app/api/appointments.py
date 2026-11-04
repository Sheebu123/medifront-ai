"""Role-scoped appointment management endpoints."""

from collections.abc import Awaitable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_authenticated_user, get_current_profile
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
    AppointmentStatusUpdate,
)
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.appointments import (
    AppointmentConflict,
    AppointmentInPast,
    AppointmentNotFound,
    InvalidDoctor,
    SupabaseDataAccessDenied,
    SupabaseDataInvalid,
    SupabaseDataUnavailable,
    create_appointment,
    get_appointment,
    list_appointments,
    update_appointment_status,
)
from app.services.supabase_auth import SupabaseProfileAccessDenied, SupabaseServiceUnavailable

router = APIRouter(prefix="/api/v1", tags=["appointments"])
T = TypeVar("T")


async def _service_result(operation: Awaitable[T]) -> T:
    """Translate known Supabase and appointment errors into stable API responses."""
    try:
        return await operation
    except (InvalidDoctor, AppointmentInPast, SupabaseDataInvalid) as error:
        detail = "The appointment request is invalid."
        if isinstance(error, InvalidDoctor):
            detail = "doctor_id must identify a doctor profile."
        elif isinstance(error, AppointmentInPast):
            detail = "The appointment date and time must be in the future."
        raise HTTPException(status_code=422, detail=detail) from None
    except AppointmentNotFound:
        raise HTTPException(status_code=404, detail="Appointment not found.") from None
    except AppointmentConflict:
        raise HTTPException(
            status_code=409,
            detail="The appointment conflicts with an existing booking or status change.",
        ) from None
    except (SupabaseDataAccessDenied, SupabaseProfileAccessDenied):
        raise HTTPException(
            status_code=403,
            detail="Supabase denied access to the requested appointment data.",
        ) from None
    except (SupabaseDataUnavailable, SupabaseServiceUnavailable):
        raise HTTPException(
            status_code=503,
            detail="The appointment service is temporarily unavailable.",
        ) from None


def _read_scope(profile: Profile, user: AuthenticatedUser) -> dict[str, str]:
    if profile.role == UserRole.PATIENT:
        return {"patient_id": f"eq.{user.user_id}"}
    if profile.role == UserRole.DOCTOR:
        return {"doctor_id": f"eq.{user.user_id}"}
    if profile.role in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        return {}
    raise HTTPException(status_code=403, detail="Role is not authorized for appointments.")


def _cancellation_scope(profile: Profile, user: AuthenticatedUser) -> dict[str, str]:
    if profile.role == UserRole.PATIENT:
        return {"patient_id": f"eq.{user.user_id}"}
    if profile.role in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        return {}
    raise HTTPException(status_code=403, detail="Role is not authorized to cancel appointments.")


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    request: AppointmentCreate,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> AppointmentResponse:
    """Book an appointment for the authenticated patient only."""
    if profile.role != UserRole.PATIENT:
        raise HTTPException(status_code=403, detail="Only patients can book appointments.")
    return await _service_result(
        create_appointment(
            user.access_token.get_secret_value(),
            user.user_id,
            request,
        )
    )


@router.get("/appointments", response_model=list[AppointmentResponse])
async def read_appointments(
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> list[AppointmentResponse]:
    """List appointments visible to the caller's role and identity."""
    scope = _read_scope(profile, user)
    return await _service_result(
        list_appointments(user.access_token.get_secret_value(), scope)
    )


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def read_appointment(
    appointment_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> AppointmentResponse:
    """Get one appointment only when it falls within the caller's scope."""
    return await _service_result(
        get_appointment(
            user.access_token.get_secret_value(),
            appointment_id,
            _read_scope(profile, user),
        )
    )


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentResponse,
)
async def cancel_appointment(
    appointment_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_authenticated_user)],
    profile: Annotated[Profile, Depends(get_current_profile)],
) -> AppointmentResponse:
    """Cancel an owned patient appointment or any appointment as staff."""
    return await _service_result(
        update_appointment_status(
            user.access_token.get_secret_value(),
            appointment_id,
            _cancellation_scope(profile, user),
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
) -> AppointmentResponse:
    """Let receptionists and admins set one of the supported statuses."""
    if profile.role not in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        raise HTTPException(
            status_code=403,
            detail="Only receptionists and admins can update appointment statuses.",
        )
    return await _service_result(
        update_appointment_status(
            user.access_token.get_secret_value(),
            appointment_id,
            {},
            request.status,
        )
    )
