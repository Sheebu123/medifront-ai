"""Doctor directory service backed by Neon PostgreSQL."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import ProfileModel
from app.schemas.auth import UserRole
from app.schemas.doctors import DoctorResponse


class DoctorServiceError(Exception):
    """Base class for doctor service errors."""


class DoctorDataUnavailable(DoctorServiceError):
    """Neon could not complete a doctor query."""


async def list_doctors(session: AsyncSession) -> list[DoctorResponse]:
    """Return all verified doctor profiles ordered by name."""
    try:
        query = (
            select(ProfileModel)
            .where(ProfileModel.role == UserRole.DOCTOR.value)
            .order_by(ProfileModel.full_name.nulls_last(), ProfileModel.id)
        )
        rows = (await session.scalars(query)).all()
        return [DoctorResponse.model_validate(row) for row in rows]
    except SQLAlchemyError:
        raise DoctorDataUnavailable from None
