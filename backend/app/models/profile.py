"""Application profile records keyed by the existing Supabase Auth UUID."""

from uuid import UUID as PythonUUID

from sqlalchemy import CheckConstraint, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ProfileModel(Base):
    """Authorization profile; role is read only from this Neon record."""

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "role IN ('patient', 'doctor', 'receptionist', 'admin')",
            name="ck_profiles_role",
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'patient'")
    )
