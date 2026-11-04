"""Appointment API tests using dependency overrides and mocked Supabase calls."""

import json
import unittest
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

from pydantic import SecretStr

from app.api.dependencies import get_authenticated_user, get_current_profile
from app.main import app
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentSlot,
    AppointmentStatus,
)
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.appointments import (
    AppointmentConflict,
    AppointmentInPast,
    InvalidDoctor,
    _appointments_in_date_window,
    create_appointment,
    find_booking_conflict,
    update_appointment_status,
    verify_doctor_for_patient,
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
        self.access_token = "test-token"
        self.user = AuthenticatedUser(
            user_id=self.user_id,
            access_token=SecretStr(self.access_token),
        )
        self.profile = Profile(
            id=self.user_id,
            full_name="Test User",
            phone=None,
            role=UserRole.PATIENT,
        )
        app.dependency_overrides[get_authenticated_user] = lambda: self.user
        app.dependency_overrides[get_current_profile] = lambda: self.profile

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
            (UserRole.PATIENT, {"patient_id": f"eq.{self.user_id}"}),
            (UserRole.DOCTOR, {"doctor_id": f"eq.{self.user_id}"}),
            (UserRole.RECEPTIONIST, {}),
            (UserRole.ADMIN, {}),
        ]
        for role, expected_scope in cases:
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
                list_request.assert_awaited_once_with(self.access_token, expected_scope)

    async def test_detail_lookup_is_scoped_to_patient(self) -> None:
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
        self.assertEqual(
            get_request.await_args.args[2],
            {"patient_id": f"eq.{self.user_id}"},
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
        self.assertEqual(update.await_args.args[2], {"patient_id": f"eq.{self.user_id}"})
        self.assertTrue(update.await_args.kwargs["cancellation"])

    async def test_doctor_cannot_cancel_or_update_status(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.DOCTOR})
        appointment_id = uuid4()
        with (
            patch("app.api.appointments.update_appointment_status", new=AsyncMock()) as update,
        ):
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

    async def test_only_receptionist_and_admin_can_update_status(self) -> None:
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
                self.assertEqual(update.await_args.args[2], {})

    async def test_status_must_be_one_of_confirmed_values(self) -> None:
        self.profile = self.profile.model_copy(update={"role": UserRole.ADMIN})
        with patch("app.api.appointments.update_appointment_status", new=AsyncMock()) as update:
            status_code, _ = await asgi_request(
                "PATCH",
                f"/api/v1/appointments/{uuid4()}/status",
                {"status": "waiting"},
            )

        self.assertEqual(status_code, 422)
        update.assert_not_awaited()


class AppointmentServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_payload_matches_granted_appointment_columns(self) -> None:
        patient_id = uuid4()
        doctor_id = uuid4()
        request = AppointmentCreate(
            doctor_id=doctor_id,
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
            reason="Consultation",
        )
        expected = sample_appointment(patient_id=patient_id, doctor_id=doctor_id)
        with (
            patch(
                "app.services.appointments.verify_doctor_for_patient",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.appointments.find_booking_conflict",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.appointments._request_table",
                new=AsyncMock(return_value=[expected.model_dump(mode="json")]),
            ) as insert,
        ):
            await create_appointment("caller-token", patient_id, request)

        payload = insert.await_args.kwargs["payload"]
        self.assertEqual(
            set(payload),
            {
                "id",
                "patient_id",
                "doctor_id",
                "appointment_date",
                "appointment_time",
                "reason",
                "status",
                "created_at",
            },
        )

    async def test_overlap_check_detects_intersecting_30_minute_slot(self) -> None:
        patient_id = uuid4()
        doctor_id = uuid4()
        appointment_date = date(2099, 5, 12)
        existing = AppointmentSlot(
            appointment_date=appointment_date,
            appointment_time=time(10, 0),
            status=AppointmentStatus.CONFIRMED,
        )
        with patch(
            "app.services.appointments._appointments_in_date_window",
            new=AsyncMock(side_effect=[[existing]]),
        ) as find_slots:
            conflict = await find_booking_conflict(
                "test-token", patient_id, doctor_id, appointment_date, time(10, 15)
            )

        self.assertTrue(conflict)
        self.assertEqual(find_slots.await_args.args[1:3], ("patient_id", patient_id))

    async def test_overlap_check_allows_slots_that_touch_at_30_minute_boundary(self) -> None:
        patient_id = uuid4()
        doctor_id = uuid4()
        appointment_date = date(2099, 5, 12)
        existing = AppointmentSlot(
            appointment_date=appointment_date,
            appointment_time=time(9, 30),
            status=AppointmentStatus.SCHEDULED,
        )
        with patch(
            "app.services.appointments._appointments_in_date_window",
            new=AsyncMock(side_effect=[[existing], []]),
        ):
            conflict = await find_booking_conflict(
                "test-token", patient_id, doctor_id, appointment_date, time(10, 0)
            )

        self.assertFalse(conflict)

    async def test_conflict_lookup_uses_postgrest_date_range_filter(self) -> None:
        with patch(
            "app.services.appointments._request_table",
            new=AsyncMock(return_value=[]),
        ) as request_table:
            rows = await _appointments_in_date_window(
                "test-token",
                "doctor_id",
                uuid4(),
                date(2099, 5, 11),
                date(2099, 5, 12),
            )

        self.assertEqual(rows, [])
        params = request_table.await_args.args[1]
        self.assertEqual(
            params["and"],
            "(appointment_date.gte.2099-05-11,appointment_date.lte.2099-05-12)",
        )

    async def test_booking_rejects_past_date_before_database_access(self) -> None:
        request = AppointmentCreate(
            doctor_id=uuid4(),
            appointment_date=date.today() - timedelta(days=1),
            appointment_time=time(10),
        )

        with self.assertRaises(AppointmentInPast):
            await create_appointment("test-token", uuid4(), request)

    async def test_booking_validates_doctor_profile_role(self) -> None:
        patient_id = uuid4()
        request = AppointmentCreate(
            doctor_id=uuid4(),
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
        )
        with patch(
            "app.services.appointments.verify_doctor_for_patient",
            new=AsyncMock(return_value=False),
        ):
            with self.assertRaises(InvalidDoctor):
                await create_appointment("test-token", patient_id, request)

    async def test_doctor_role_check_uses_caller_scoped_rpc(self) -> None:
        patient_id = uuid4()
        doctor_id = uuid4()
        with patch(
            "app.services.appointments.asyncio.to_thread",
            new=AsyncMock(return_value=True),
        ) as run_in_thread:
            allowed = await verify_doctor_for_patient(
                "caller-token", patient_id, doctor_id
            )

        self.assertTrue(allowed)
        self.assertEqual(
            run_in_thread.await_args.args[1:],
            ("caller-token", patient_id, doctor_id),
        )

    async def test_booking_rejects_detected_overlap_before_insert(self) -> None:
        patient_id = uuid4()
        request = AppointmentCreate(
            doctor_id=uuid4(),
            appointment_date=date.today() + timedelta(days=10),
            appointment_time=time(10),
        )
        with (
            patch(
                "app.services.appointments.verify_doctor_for_patient",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.appointments.find_booking_conflict",
                new=AsyncMock(return_value=True),
            ),
            patch("app.services.appointments._request_table", new=AsyncMock()) as insert,
        ):
            with self.assertRaises(AppointmentConflict):
                await create_appointment("test-token", patient_id, request)

        insert.assert_not_awaited()

    async def test_cancellation_rejects_an_already_cancelled_record(self) -> None:
        appointment = sample_appointment(status=AppointmentStatus.CANCELLED)
        with (
            patch(
                "app.services.appointments.get_appointment",
                new=AsyncMock(return_value=appointment),
            ),
            patch("app.services.appointments._request_table", new=AsyncMock()) as update,
        ):
            with self.assertRaises(AppointmentConflict):
                await update_appointment_status(
                    "test-token",
                    appointment.id,
                    {},
                    AppointmentStatus.CANCELLED,
                    cancellation=True,
                )

        update.assert_not_awaited()

    async def test_status_update_payload_uses_only_granted_status_column(self) -> None:
        current = sample_appointment(status=AppointmentStatus.SCHEDULED)
        updated = current.model_copy(update={"status": AppointmentStatus.CONFIRMED})
        with (
            patch(
                "app.services.appointments.get_appointment",
                new=AsyncMock(return_value=current),
            ),
            patch(
                "app.services.appointments._request_table",
                new=AsyncMock(return_value=[updated.model_dump(mode="json")]),
            ) as update,
        ):
            result = await update_appointment_status(
                "caller-token",
                current.id,
                {},
                AppointmentStatus.CONFIRMED,
            )

        self.assertEqual(result.status, AppointmentStatus.CONFIRMED)
        self.assertEqual(update.await_args.kwargs["payload"], {"status": "confirmed"})


if __name__ == "__main__":
    unittest.main()
