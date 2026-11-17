"""Appointment API and Neon service tests using mocked sessions."""

import json
import unittest
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_authenticated_user, get_current_profile
from app.db.session import get_db_session
from app.main import app
from app.models.appointment import AppointmentModel
from app.models.profile import ProfileModel
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatus,
)
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.appointments import (
    AppointmentConflict,
    AppointmentInPast,
    InvalidDoctor,
    InvalidPatient,
    create_appointment,
    list_appointments,
    update_appointment_status,
)


async def asgi_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Send one JSON ASGI request to the FastAPI application."""
    messages: list[dict[str, Any]] = []
    sent_request = False
    request_body = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = []
    if body is not None:
        headers.extend(
            [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(request_body)).encode("ascii")),
            ]
        )

    async def receive() -> dict[str, Any]:
        nonlocal sent_request
        if not sent_request:
            sent_request = True
            return {"type": "http.request", "body": request_body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "state": {},
        },
        receive,
        send,
    )

    status_code = next(
        message["status"]
        for message in messages
        if message["type"] == "http.response.start"
    )
    response_body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status_code, json.loads(response_body) if response_body else None


def sample_appointment(
    *,
    patient_id: UUID | None = None,
    doctor_id: UUID | None = None,
    status: AppointmentStatus = AppointmentStatus.SCHEDULED,
) -> AppointmentResponse:
    return AppointmentResponse(
        id=uuid4(),
        patient_id=patient_id or uuid4(),
        doctor_id=doctor_id or uuid4(),
        appointment_date=date.today() + timedelta(days=10),
        appointment_time=time(10, 30),
        reason="Consultation",
        status=status,
        created_at=datetime.now(UTC),
    )


class AppointmentApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()
        self.doctor_id = uuid4()
        self.session = object()
        self.user = AuthenticatedUser(user_id=self.user_id)
        self.profile = Profile(
            id=self.user_id,
            full_name="Test User",
            phone=None,
            role=UserRole.PATIENT,
        )
        app.dependency_overrides[get_authenticated_user] = lambda: self.user
        app.dependency_overrides[get_current_profile] = lambda: self.profile
        app.dependency_overrides[get_db_session] = lambda: self.session

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_patient_create_derives_patient_id_from_identity(self) -> None:
        expected = sample_appointment(patient_id=self.user_id, doctor_id=self.doctor_id)
        request_body = {
            "doctor_id": str(self.doctor_id),
            "appointment_date": (date.today() + timedelta(days=10)).isoformat(),
            "appointment_time": "10:30",
            "reason": "Consultation",
        }
        with patch(
            "app.api.appointments.create_appointment",
            new=AsyncMock(return_value=expected),
        ) as create:
            status_code, response = await asgi_request(
                "POST", "/api/v1/appointments", request_body
            )

        self.assertEqual(status_code, 201)
        self.assertEqual(response["patient_id"], str(self.user_id))
        create.assert_awaited_once()
        self.assertEqual(create.await_args.args[1], self.user_id)
        self.assertEqual(create.await_args.args[2].doctor_id, self.doctor_id)

    async def test_create_rejects_client_supplied_patient_id(self) -> None:
        request_body = {
            "patient_id": str(uuid4()),
            "doctor_id": str(self.doctor_id),
            "appointment_date": (date.today() + timedelta(days=10)).isoformat(),
            "appointment_time": "10:30",
        }
        with patch("app.api.appointments.create_appointment", new=AsyncMock()) as create:
            status_code, _ = await asgi_request(
                "POST", "/api/v1/appointments", request_body
            )

        self.assertEqual(status_code, 422)
        create.assert_not_awaited()

    async def test_only_patients_can_book(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.DOCTOR})
        with patch("app.api.appointments.create_appointment", new=AsyncMock()) as create:
            status_code, _ = await asgi_request(
                "POST",
                "/api/v1/appointments",
                {
                    "doctor_id": str(self.doctor_id),
                    "appointment_date": (date.today() + timedelta(days=10)).isoformat(),
                    "appointment_time": "10:30",
                },
            )

        self.assertEqual(status_code, 403)
        create.assert_not_awaited()

    async def test_list_scopes_patient_and_doctor_and_allows_staff_all(self) -> None:
        cases = [
            (UserRole.PATIENT, self.user_id),
            (UserRole.DOCTOR, self.user_id),
            (UserRole.RECEPTIONIST, self.user_id),
            (UserRole.ADMIN, self.user_id),
        ]
        for role, expected_user_id in cases:
            with self.subTest(role=role.value):
                self.profile = self.profile.model_copy(update={"role": role})
                with patch(
                    "app.api.appointments.list_appointments",
                    new=AsyncMock(return_value=[]),
                ) as list_request:
                    status_code, result = await asgi_request(
                        "GET", "/api/v1/appointments"
                    )

                self.assertEqual(status_code, 200)
                self.assertEqual(result, [])
                list_request.assert_awaited_once_with(
                    self.session, role, expected_user_id
                )

    async def test_detail_lookup_uses_verified_role_and_identity(self) -> None:
        appointment = sample_appointment(patient_id=self.user_id)
        with patch(
            "app.api.appointments.get_appointment",
            new=AsyncMock(return_value=appointment),
        ) as get_request:
            status_code, response = await asgi_request(
                "GET", f"/api/v1/appointments/{appointment.id}"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(response["id"], str(appointment.id))
        get_request.assert_awaited_once_with(
            self.session, appointment.id, UserRole.PATIENT, self.user_id
        )

    async def test_patient_can_cancel_own_appointment(self) -> None:
        appointment = sample_appointment(patient_id=self.user_id)
        with patch(
            "app.api.appointments.update_appointment_status",
            new=AsyncMock(
                return_value=appointment.model_copy(
                    update={"status": AppointmentStatus.CANCELLED}
                )
            ),
        ) as update:
            status_code, response = await asgi_request(
                "PATCH", f"/api/v1/appointments/{appointment.id}/cancel"
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(response["status"], "cancelled")
        self.assertEqual(
            update.await_args.args,
            (
                self.session,
                appointment.id,
                UserRole.PATIENT,
                self.user_id,
                AppointmentStatus.CANCELLED,
            ),
        )
        self.assertTrue(update.await_args.kwargs["cancellation"])

    async def test_doctor_cannot_cancel_or_update_status(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.DOCTOR})
        appointment_id = uuid4()
        with patch("app.api.appointments.update_appointment_status", new=AsyncMock()) as update:
            cancel_status, _ = await asgi_request(
                "PATCH", f"/api/v1/appointments/{appointment_id}/cancel"
            )
            status_status, _ = await asgi_request(
                "PATCH",
                f"/api/v1/appointments/{appointment_id}/status",
                {"status": "confirmed"},
            )

        self.assertEqual(cancel_status, 403)
        self.assertEqual(status_status, 403)
        update.assert_not_awaited()

    async def test_only_staff_can_update_status(self) -> None:
        appointment_id = uuid4()
        for role in (UserRole.RECEPTIONIST, UserRole.ADMIN):
            with self.subTest(role=role.value):
                self.profile = self.profile.model_copy(update={"role": role})
                updated = sample_appointment(status=AppointmentStatus.CONFIRMED)
                with patch(
                    "app.api.appointments.update_appointment_status",
                    new=AsyncMock(return_value=updated),
                ) as update:
                    status_code, response = await asgi_request(
                        "PATCH",
                        f"/api/v1/appointments/{appointment_id}/status",
                        {"status": "confirmed"},
                    )

                self.assertEqual(status_code, 200)
                self.assertEqual(response["status"], "confirmed")
                self.assertEqual(update.await_args.args[2:4], (role, self.user_id))

    async def test_status_must_be_one_of_supported_values(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.ADMIN})
        with patch(
            "app.api.appointments.update_appointment_status", new=AsyncMock()
        ) as update:
            status_code, _ = await asgi_request(
                "PATCH",
                f"/api/v1/appointments/{uuid4()}/status",
                {"status": "waiting"},
            )

        self.assertEqual(status_code, 422)
        update.assert_not_awaited()

    async def test_database_booking_conflicts_return_409(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.PATIENT})
        with patch(
            "app.api.appointments.create_appointment",
            new=AsyncMock(side_effect=AppointmentConflict),
        ):
            status_code, response = await asgi_request(
                "POST",
                "/api/v1/appointments",
                {
                    "doctor_id": str(self.doctor_id),
                    "appointment_date": (date.today() + timedelta(days=10)).isoformat(),
                    "appointment_time": "10:30",
                },
            )

        self.assertEqual(status_code, 409)
        self.assertIn("conflicts", response["detail"])


class AppointmentServiceTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self) -> AsyncMock:
        session = MagicMock()
        session.get = AsyncMock()
        session.scalar = AsyncMock()
        session.scalars = AsyncMock()
        session.scalars.return_value = MagicMock()
        session.scalars.return_value.all.return_value = []
        session.execute = AsyncMock()
        session.execute.return_value = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    async def test_booking_rejects_past_date_before_database_access(self) -> None:
        session = self.make_session()
        request = AppointmentCreate(
            doctor_id=uuid4(),
            appointment_date=date.today() - timedelta(days=1),
            appointment_time=time(10),
        )

        with self.assertRaises(AppointmentInPast):
            await create_appointment(session, uuid4(), request)
        session.scalars.assert_not_awaited()

    async def test_booking_checks_patient_and_doctor_roles_in_neon(self) -> None:
        session = self.make_session()
        patient_id, doctor_id = uuid4(), uuid4()
        session.scalars.return_value.all.return_value = [
            ProfileModel(id=patient_id, role="patient"),
            ProfileModel(id=doctor_id, role="doctor"),
        ]

        async def flush_and_set_created_at() -> None:
            inserted = session.add.call_args.args[0]
            inserted.created_at = datetime.now(UTC)

        session.flush.side_effect = flush_and_set_created_at
        request = AppointmentCreate(
            doctor_id=doctor_id,
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
            reason="Consultation",
        )

        result = await create_appointment(session, patient_id, request)

        self.assertEqual(result.patient_id, patient_id)
        self.assertEqual(result.doctor_id, doctor_id)
        self.assertEqual(result.status, AppointmentStatus.SCHEDULED)
        session.commit.assert_awaited_once()

    async def test_booking_rejects_non_doctor_profile(self) -> None:
        session = self.make_session()
        patient_id, doctor_id = uuid4(), uuid4()
        session.scalars.return_value.all.return_value = [
            ProfileModel(id=patient_id, role="patient"),
            ProfileModel(id=doctor_id, role="patient"),
        ]
        request = AppointmentCreate(
            doctor_id=doctor_id,
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
        )

        with self.assertRaises(InvalidDoctor):
            await create_appointment(session, patient_id, request)

        session.add.assert_not_called()

    async def test_booking_rejects_non_patient_profile(self) -> None:
        session = self.make_session()
        patient_id, doctor_id = uuid4(), uuid4()
        session.scalars.return_value.all.return_value = [
            ProfileModel(id=patient_id, role="doctor"),
            ProfileModel(id=doctor_id, role="doctor"),
        ]
        request = AppointmentCreate(
            doctor_id=doctor_id,
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
        )

        with self.assertRaises(InvalidPatient):
            await create_appointment(session, patient_id, request)

        session.add.assert_not_called()

    async def test_exclusion_constraint_conflict_becomes_domain_conflict(self) -> None:
        session = self.make_session()
        patient_id, doctor_id = uuid4(), uuid4()
        session.scalars.return_value.all.return_value = [
            ProfileModel(id=patient_id, role="patient"),
            ProfileModel(id=doctor_id, role="doctor"),
        ]
        session.flush.side_effect = IntegrityError("insert", {}, Exception("overlap"))
        request = AppointmentCreate(
            doctor_id=doctor_id,
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
        )

        with self.assertRaises(AppointmentConflict):
            await create_appointment(session, patient_id, request)
        session.rollback.assert_awaited_once()

    async def test_list_query_is_scoped_by_patient_role(self) -> None:
        session = self.make_session()
        session.scalars.return_value.all.return_value = []

        await list_appointments(session, UserRole.PATIENT, uuid4())

        query = session.scalars.await_args.args[0]
        sql = str(query.compile(dialect=postgresql.dialect()))
        self.assertIn("appointments.patient_id =", sql)
        self.assertNotIn("appointments.doctor_id =", sql)

    async def test_cancellation_rejects_completed_appointment(self) -> None:
        session = self.make_session()
        appointment = sample_appointment(status=AppointmentStatus.COMPLETED)
        with patch(
            "app.services.appointments.get_appointment",
            new=AsyncMock(return_value=appointment),
        ):
            with self.assertRaises(AppointmentConflict):
                await update_appointment_status(
                    session,
                    appointment.id,
                    UserRole.PATIENT,
                    appointment.patient_id,
                    AppointmentStatus.CANCELLED,
                    cancellation=True,
                )

        session.execute.assert_not_awaited()

    async def test_status_update_is_conditional_on_current_status(self) -> None:
        session = self.make_session()
        current = sample_appointment(status=AppointmentStatus.SCHEDULED)
        updated = AppointmentModel(
            id=current.id,
            patient_id=current.patient_id,
            doctor_id=current.doctor_id,
            appointment_date=current.appointment_date,
            appointment_time=current.appointment_time,
            reason=current.reason,
            status="confirmed",
            created_at=current.created_at,
        )
        session.execute.return_value.scalar_one_or_none.return_value = updated
        with patch(
            "app.services.appointments.get_appointment",
            new=AsyncMock(return_value=current),
        ):
            response = await update_appointment_status(
                session,
                current.id,
                UserRole.ADMIN,
                uuid4(),
                AppointmentStatus.CONFIRMED,
            )

        self.assertEqual(response.status, AppointmentStatus.CONFIRMED)
        statement = session.execute.await_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("appointments.status =", sql)
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
