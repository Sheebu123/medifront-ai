"""Neon configuration, profile provisioning, and PostgreSQL metadata tests."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.schema import CreateTable
from fastapi import HTTPException

from app.core.config import DatabaseConfigurationError, get_database_url
from app.db.base import Base
from app.db.session import get_db_session, get_engine, get_session_factory
from app.models.appointment import AppointmentModel
from app.models.profile import ProfileModel
from app.schemas.auth import UserRole
from app.services.profiles import get_or_create_profile


class DatabaseConfigurationTests(unittest.TestCase):
    def test_normalizes_neon_url_for_psycopg_three(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@db.example/app"}):
            value = get_database_url()

        self.assertTrue(value.startswith("postgresql+psycopg://"))
        self.assertEqual(parse_qsl(urlsplit(value).query), [("sslmode", "require")])

    def test_pooled_url_with_required_ssl_does_not_gain_duplicate_sslmode(self) -> None:
        url = (
            "postgresql://user:pass@db-pooler.example/app"
            "?sslmode=require&channel_binding=require"
        )
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            value = get_database_url()

        query = parse_qsl(urlsplit(value).query)
        self.assertEqual(query.count(("sslmode", "require")), 1)
        self.assertIn(("channel_binding", "require"), query)

    def test_pooled_url_without_ssl_gets_ssl_and_keeps_existing_parameters(self) -> None:
        url = "postgres://user:pass@db-pooler.example/app?channel_binding=require&application_name=api"
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            value = get_database_url()

        self.assertTrue(value.startswith("postgresql+psycopg://"))
        self.assertEqual(
            parse_qsl(urlsplit(value).query),
            [
                ("channel_binding", "require"),
                ("application_name", "api"),
                ("sslmode", "require"),
            ],
        )

    def test_conflicting_and_duplicate_ssl_modes_collapse_to_required(self) -> None:
        url = (
            "postgresql://user:pass@db.example/app"
            "?sslmode=prefer&channel_binding=require&sslmode=disable"
        )
        with patch.dict(os.environ, {"DATABASE_URL": url}):
            value = get_database_url()

        query = parse_qsl(urlsplit(value).query)
        self.assertEqual(query.count(("sslmode", "require")), 1)
        self.assertNotIn(("sslmode", "prefer"), query)
        self.assertNotIn(("sslmode", "disable"), query)
        self.assertIn(("channel_binding", "require"), query)

    def test_migrations_prefer_direct_url(self) -> None:
        env = {
            "DATABASE_URL": "postgresql://user:pass@pooler.example/app",
            "DATABASE_URL_UNPOOLED": "postgresql://user:pass@direct.example/app",
        }
        with patch.dict(os.environ, env):
            value = get_database_url(for_migrations=True)

        self.assertIn("direct.example", value)

    def test_direct_url_requires_ssl_and_preserves_channel_binding(self) -> None:
        env = {
            "DATABASE_URL": "postgresql://user:pass@pooler.example/app?sslmode=disable",
            "DATABASE_URL_UNPOOLED": "postgresql+psycopg://user:pass@direct.example/app?channel_binding=require",
        }
        with patch.dict(os.environ, env):
            value = get_database_url(for_migrations=True)

        self.assertIn("direct.example", value)
        query = parse_qsl(urlsplit(value).query)
        self.assertEqual(query.count(("sslmode", "require")), 1)
        self.assertIn(("channel_binding", "require"), query)

    def test_migrations_require_a_direct_url(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@pooler.example/app"}, clear=True):
            with self.assertRaises(DatabaseConfigurationError):
                get_database_url(for_migrations=True)

    def test_migrations_reject_pooled_url(self) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL_UNPOOLED": "postgresql://user:pass@db-pooler.example/app"},
            clear=True,
        ):
            with self.assertRaises(DatabaseConfigurationError):
                get_database_url(for_migrations=True)

    def test_missing_url_fails_without_disclosing_credentials(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(DatabaseConfigurationError) as error:
                get_database_url()

        self.assertNotIn("postgres", str(error.exception))


class DatabaseDependencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_database_url_returns_service_unavailable(self) -> None:
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as error:
                await get_db_session().__anext__()

        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("DATABASE_URL", str(error.exception.detail))


class ProfileProvisioningTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self) -> MagicMock:
        session = MagicMock()
        session.get = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    async def test_first_login_creates_patient_regardless_of_other_auth_metadata(self) -> None:
        session = self.make_session()
        session.get.return_value = None
        user_id = uuid4()

        profile = await get_or_create_profile(
            session,
            user_id,
            full_name="  New User  ",
            phone=" 555-0123 ",
        )

        inserted = session.add.call_args.args[0]
        self.assertEqual(inserted.id, user_id)
        self.assertEqual(inserted.role, "patient")
        self.assertEqual(inserted.full_name, "New User")
        self.assertEqual(inserted.phone, "555-0123")
        self.assertEqual(profile.role, UserRole.PATIENT)
        session.commit.assert_awaited_once()

    async def test_existing_neon_role_is_preserved(self) -> None:
        session = self.make_session()
        user_id = uuid4()
        session.get.return_value = ProfileModel(
            id=user_id,
            full_name="Doctor",
            phone=None,
            role="doctor",
        )

        profile = await get_or_create_profile(
            session,
            user_id,
            full_name="Untrusted replacement",
            phone="555-0101",
        )

        self.assertEqual(profile.role, UserRole.DOCTOR)
        self.assertEqual(profile.full_name, "Doctor")
        session.add.assert_not_called()


class NeonModelTests(unittest.TestCase):
    def test_tables_have_expected_foreign_keys_indexes_and_checks(self) -> None:
        self.assertEqual(set(Base.metadata.tables), {"profiles", "appointments"})
        appointment = AppointmentModel.__table__
        foreign_keys = {fk.target_fullname for fk in appointment.foreign_keys}
        self.assertEqual(foreign_keys, {"profiles.id"})
        self.assertEqual(
            {index.name for index in appointment.indexes},
            {
                "ix_appointments_patient_schedule",
                "ix_appointments_doctor_schedule",
                "ix_appointments_status",
            },
        )
        self.assertIn("ck_profiles_role", {c.name for c in ProfileModel.__table__.constraints})
        self.assertIn("ck_appointments_status", {c.name for c in appointment.constraints})

    def test_active_appointment_constraints_enforce_thirty_minute_exclusion(self) -> None:
        appointment = AppointmentModel.__table__
        exclusion = {
            constraint.name: str(constraint.where)
            for constraint in appointment.constraints
            if isinstance(constraint, ExcludeConstraint)
        }
        self.assertEqual(
            set(exclusion),
            {
                "ex_appointments_patient_no_overlap",
                "ex_appointments_doctor_no_overlap",
            },
        )
        statement = str(CreateTable(appointment).compile(dialect=postgresql.dialect()))
        self.assertIn("interval '30 minutes'", statement)
        self.assertIn("status IN ('scheduled', 'confirmed')", statement)
        self.assertIn("EXCLUDE USING gist", statement)


if __name__ == "__main__":
    unittest.main()
