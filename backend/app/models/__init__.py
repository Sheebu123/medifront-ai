"""ORM models and metadata registration."""

from app.models.appointment import AppointmentModel
from app.models.profile import ProfileModel

__all__ = ["AppointmentModel", "ProfileModel"]
