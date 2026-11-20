"""Unit and API tests for doctor directory endpoints."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api.dependencies import get_authenticated_user, get_db_session
from app.main import app
from app.models.profile import ProfileModel
from app.schemas.auth import AuthenticatedUser, UserRole
from app.schemas.doctors import DoctorResponse
from app.services.doctors import DoctorDataUnavailable, list_doctors
from tests.test_appointments import asgi_request


class DoctorServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_doctors_queries_only_doctor_profiles(self) -> None:
        doc1 = ProfileModel(
            id=uuid4(),
            full_name="Dr. Sarah Connor",
            phone="1234567890",
            role=UserRole.DOCTOR.value,
        )
        doc2 = ProfileModel(
            id=uuid4(),
            full_name="Dr. James Wilson",
            phone=None,
            role=UserRole.DOCTOR.value,
        )
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [doc1, doc2]
        session = AsyncMock()
        session.scalars.return_value = scalars_mock

        result = await list_doctors(session)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].full_name, "Dr. Sarah Connor")
        self.assertEqual(result[1].full_name, "Dr. James Wilson")


class DoctorApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.user_id = uuid4()
        self.user = AuthenticatedUser(user_id=self.user_id)
        self.session = object()
        app.dependency_overrides[get_authenticated_user] = lambda: self.user
        app.dependency_overrides[get_db_session] = lambda: self.session

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_read_doctors_returns_doctor_list(self) -> None:
        doc_id = uuid4()
        doctor = DoctorResponse(id=doc_id, full_name="Dr. Gregory House", phone=None)
        with patch("app.api.doctors.list_doctors", new=AsyncMock(return_value=[doctor])):
            status_code, data = await asgi_request("GET", "/api/v1/doctors")

        self.assertEqual(status_code, 200)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], str(doc_id))
        self.assertEqual(data[0]["full_name"], "Dr. Gregory House")

    async def test_read_doctors_handles_service_unavailable(self) -> None:
        with patch(
            "app.api.doctors.list_doctors",
            new=AsyncMock(side_effect=DoctorDataUnavailable),
        ):
            status_code, data = await asgi_request("GET", "/api/v1/doctors")

        self.assertEqual(status_code, 503)
        self.assertIn("temporarily unavailable", data["detail"])
