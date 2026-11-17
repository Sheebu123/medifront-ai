"""Create Neon application profiles and appointments.

Revision ID: 20261106_0001
Revises:
Create Date: 2026-11-06
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint, UUID

revision: str = "20261106_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE_WINDOW = sa.text(
    "tsrange(appointment_date + appointment_time, "
    "appointment_date + appointment_time + interval '30 minutes', '[)')"
)
_ACTIVE_STATUSES = sa.text("status IN ('scheduled', 'confirmed')")


def upgrade() -> None:
    """Create the new schema without altering the legacy Supabase database."""
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "profiles",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default=sa.text("'patient'"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('patient', 'doctor', 'receptionist', 'admin')",
            name="ck_profiles_role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
    )

    op.create_table(
        "appointments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("patient_id", UUID(as_uuid=True), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.Time(timezone=False), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'scheduled'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'confirmed', 'cancelled', 'completed')",
            name="ck_appointments_status",
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["profiles.id"],
            ondelete="RESTRICT",
            name="fk_appointments_doctor_id_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["profiles.id"],
            ondelete="RESTRICT",
            name="fk_appointments_patient_id_profiles",
        ),
        ExcludeConstraint(
            ("patient_id", "="),
            (_ACTIVE_WINDOW, "&&"),
            where=_ACTIVE_STATUSES,
            using="gist",
            name="ex_appointments_patient_no_overlap",
        ),
        ExcludeConstraint(
            ("doctor_id", "="),
            (_ACTIVE_WINDOW, "&&"),
            where=_ACTIVE_STATUSES,
            using="gist",
            name="ex_appointments_doctor_no_overlap",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_appointments"),
    )
    op.create_index(
        "ix_appointments_patient_schedule",
        "appointments",
        ["patient_id", "appointment_date", "appointment_time"],
    )
    op.create_index(
        "ix_appointments_doctor_schedule",
        "appointments",
        ["doctor_id", "appointment_date", "appointment_time"],
    )
    op.create_index("ix_appointments_status", "appointments", ["status"])


def downgrade() -> None:
    """Refuse an automatic rollback that would delete migrated application data."""
    raise RuntimeError(
        "This initial Neon schema migration is forward-only; use a reviewed backup and rollback plan."
    )
