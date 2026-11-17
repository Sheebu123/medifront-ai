"""Appointment operations backed by Neon PostgreSQL."""

from datetime import date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.appointment import AppointmentModel
from app.models.profile import ProfileModel
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
)
from app.schemas.auth import UserRole


class AppointmentServiceError(Exception):
    """Base class for expected appointment service errors."""


class AppointmentNotFound(AppointmentServiceError):
    """No appointment visible to this caller matches the requested ID."""


class InvalidDoctor(AppointmentServiceError):
    """The requested doctor ID does not identify a doctor profile."""


class InvalidPatient(AppointmentServiceError):
    """The authenticated patient ID does not have a patient profile in Neon."""


class AppointmentInPast(AppointmentServiceError):
    """The requested local date and time have already passed."""


class AppointmentConflict(AppointmentServiceError):
    """A booking overlaps, or a conditional status update lost a race."""


class AppointmentDataUnavailable(AppointmentServiceError):
    """Neon could not complete an appointment database operation."""


def _as_response(row: AppointmentModel) -> AppointmentResponse:
    return AppointmentResponse.model_validate(row)


def _appointment_start(appointment_date: date, appointment_time: time) -> datetime:
    return datetime.combine(appointment_date, appointment_time)


def _authorization_filters(role: UserRole, user_id: UUID) -> list[ColumnElement[bool]]:
    """Return SQL filters from the verified profile and authenticated user ID."""
    if role == UserRole.PATIENT:
        return [AppointmentModel.patient_id == user_id]
    if role == UserRole.DOCTOR:
        return [AppointmentModel.doctor_id == user_id]
    elif role not in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        raise AppointmentDataUnavailable
    return []


def _appointment_query(
    *,
    appointment_id: UUID | None = None,
    role: UserRole,
    user_id: UUID,
):
    """Build an access-scoped query using only the verified profile and user ID."""
    filters = _authorization_filters(role, user_id)
    if appointment_id is not None:
        filters.append(AppointmentModel.id == appointment_id)
    return select(AppointmentModel).where(*filters)


async def list_appointments(
    session: AsyncSession,
    role: UserRole,
    user_id: UUID,
) -> list[AppointmentResponse]:
    """List only rows visible to the caller's verified role and identity."""
    try:
        query = _appointment_query(role=role, user_id=user_id).order_by(
            AppointmentModel.appointment_date,
            AppointmentModel.appointment_time,
        )
        rows = (await session.scalars(query)).all()
        return [_as_response(row) for row in rows]
    except SQLAlchemyError:
        raise AppointmentDataUnavailable from None


async def get_appointment(
    session: AsyncSession,
    appointment_id: UUID,
    role: UserRole,
    user_id: UUID,
) -> AppointmentResponse:
    """Read one appointment only if it matches the caller's database scope."""
    try:
        row = await session.scalar(
            _appointment_query(
                appointment_id=appointment_id,
                role=role,
                user_id=user_id,
            )
        )
    except SQLAlchemyError:
        raise AppointmentDataUnavailable from None
    if row is None:
        raise AppointmentNotFound
    return _as_response(row)


async def _validate_booking_profiles(
    session: AsyncSession,
    patient_id: UUID,
    doctor_id: UUID,
) -> None:
    profiles = (
        await session.scalars(
            select(ProfileModel).where(ProfileModel.id.in_((patient_id, doctor_id)))
        )
    ).all()
    roles = {profile.id: profile.role for profile in profiles}
    if roles.get(patient_id) != UserRole.PATIENT.value:
        raise InvalidPatient
    if roles.get(doctor_id) != UserRole.DOCTOR.value:
        raise InvalidDoctor


async def create_appointment(
    session: AsyncSession,
    patient_id: UUID,
    request: AppointmentCreate,
) -> AppointmentResponse:
    """Validate both profile roles and create the patient's appointment."""
    starts_at = _appointment_start(request.appointment_date, request.appointment_time)
    local_now = datetime.now().astimezone().replace(tzinfo=None)
    if starts_at <= local_now:
        raise AppointmentInPast

    try:
        await _validate_booking_profiles(session, patient_id, request.doctor_id)
        appointment = AppointmentModel(
            id=uuid4(),
            patient_id=patient_id,
            doctor_id=request.doctor_id,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time,
            reason=request.reason,
            status=AppointmentStatus.SCHEDULED.value,
        )
        session.add(appointment)
        await session.flush()
        await session.commit()
        return _as_response(appointment)
    except InvalidDoctor:
        raise
    except IntegrityError:
        await session.rollback()
        # The exclusion constraints are the atomic guard against concurrent bookings.
        raise AppointmentConflict from None
    except SQLAlchemyError:
        await session.rollback()
        raise AppointmentDataUnavailable from None


async def update_appointment_status(
    session: AsyncSession,
    appointment_id: UUID,
    role: UserRole,
    user_id: UUID,
    new_status: AppointmentStatus,
    *,
    cancellation: bool = False,
) -> AppointmentResponse:
    """Update an authorized appointment and translate constraint races safely."""
    if cancellation:
        if role not in {
            UserRole.PATIENT,
            UserRole.RECEPTIONIST,
            UserRole.ADMIN,
        }:
            raise AppointmentNotFound
    elif role not in {UserRole.RECEPTIONIST, UserRole.ADMIN}:
        raise AppointmentNotFound

    current = await get_appointment(session, appointment_id, role, user_id)
    if cancellation and current.status not in {
        AppointmentStatus.SCHEDULED,
        AppointmentStatus.CONFIRMED,
    }:
        raise AppointmentConflict

    try:
        filters = [
            AppointmentModel.id == appointment_id,
            AppointmentModel.status == current.status.value,
            *_authorization_filters(role, user_id),
        ]
        result = await session.execute(
            update(AppointmentModel)
            .where(*filters)
            .values(status=new_status.value)
            .returning(AppointmentModel)
        )
        updated = result.scalar_one_or_none()
        if updated is None:
            await session.rollback()
            raise AppointmentConflict
        await session.flush()
        await session.commit()
        return _as_response(updated)
    except AppointmentConflict:
        raise
    except IntegrityError:
        await session.rollback()
        raise AppointmentConflict from None
    except SQLAlchemyError:
        await session.rollback()
        raise AppointmentDataUnavailable from None
