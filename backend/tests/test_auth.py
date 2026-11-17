"""Supabase token verification and Neon-backed role dependency tests."""

import json
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.api.dependencies import get_authenticated_user, get_current_profile, require_roles
from app.core.config import SupabaseConfigurationError
from app.main import app
from app.schemas.auth import AuthenticatedUser, Profile, UserRole
from app.services.supabase_auth import SupabaseInvalidToken, SupabaseServiceUnavailable


async def asgi_get(
    path: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Send one in-process ASGI GET request and decode its JSON response."""
    messages: list[dict[str, Any]] = []
    request_sent = False
    encoded_headers = [
        (name.lower().encode("ascii"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": encoded_headers,
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
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status_code, json.loads(body)


class AuthEndpointTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    async def test_me_rejects_missing_bearer_token(self) -> None:
        status_code, body = await asgi_get("/api/v1/auth/me")

        self.assertEqual(status_code, 401)
        self.assertEqual(body["detail"], "A valid Supabase bearer token is required.")

    async def test_me_rejects_invalid_bearer_token(self) -> None:
        with patch(
            "app.api.dependencies.verify_supabase_access_token",
            new=AsyncMock(side_effect=SupabaseInvalidToken),
        ):
            status_code, _ = await asgi_get(
                "/api/v1/auth/me",
                {"Authorization": "Bearer invalid-token"},
            )

        self.assertEqual(status_code, 401)

    async def test_me_returns_503_when_supabase_service_is_unavailable(self) -> None:
        with patch(
            "app.api.dependencies.verify_supabase_access_token",
            new=AsyncMock(side_effect=SupabaseServiceUnavailable),
        ):
            status_code, _ = await asgi_get(
                "/api/v1/auth/me",
                {"Authorization": "Bearer test-access-token"},
            )

        self.assertEqual(status_code, 503)

    async def test_me_returns_503_when_supabase_configuration_is_missing(self) -> None:
        with patch(
            "app.api.dependencies.verify_supabase_access_token",
            new=AsyncMock(side_effect=SupabaseConfigurationError("missing config")),
        ):
            status_code, _ = await asgi_get(
                "/api/v1/auth/me",
                {"Authorization": "Bearer test-access-token"},
            )

        self.assertEqual(status_code, 503)

    async def test_me_returns_auth_user_and_neon_profile(self) -> None:
        user_id = uuid4()
        profile = Profile(
            id=user_id,
            full_name="MediFront Test User",
            phone=None,
            role=UserRole.PATIENT,
        )
        app.dependency_overrides[get_current_profile] = lambda: profile
        with patch(
            "app.api.dependencies.verify_supabase_access_token",
            new=AsyncMock(return_value={"id": str(user_id)}),
        ):
            status_code, body = await asgi_get(
                "/api/v1/auth/me",
                {"Authorization": "Bearer test-access-token"},
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(body["user_id"], str(user_id))
        self.assertEqual(body["profile"]["id"], str(user_id))
        self.assertEqual(body["profile"]["role"], "patient")

    async def test_verified_auth_metadata_cannot_assign_role(self) -> None:
        user_id = uuid4()
        with patch(
            "app.api.dependencies.verify_supabase_access_token",
            new=AsyncMock(
                return_value={
                    "id": str(user_id),
                    "user_metadata": {
                        "full_name": "Test Patient",
                        "phone": "555-0100",
                        "role": "admin",
                    },
                }
            ),
        ):
            user = await get_authenticated_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
            )

        self.assertEqual(user.user_id, user_id)
        self.assertEqual(user.profile_full_name, "Test Patient")
        self.assertEqual(user.profile_phone, "555-0100")
        self.assertFalse(hasattr(user, "role"))

    async def test_unsupported_database_role_is_forbidden(self) -> None:
        invalid_profile_error: ValidationError | None = None
        try:
            Profile.model_validate(
                {"id": str(uuid4()), "full_name": None, "phone": None, "role": "owner"}
            )
        except ValidationError as error:
            invalid_profile_error = error
        else:
            self.fail("unsupported profile role should fail validation")

        with patch(
            "app.api.dependencies.get_or_create_profile",
            new=AsyncMock(side_effect=invalid_profile_error),
        ):
            with self.assertRaises(HTTPException) as error:
                await get_current_profile(
                    AuthenticatedUser(user_id=uuid4()),
                    AsyncMock(),
                )

        self.assertEqual(error.exception.status_code, 403)


class RoleAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    def make_profile(self, role: UserRole) -> Profile:
        return Profile(
            id=uuid4(),
            full_name="Role Test User",
            phone=None,
            role=role,
        )

    async def test_each_supported_role_can_be_required(self) -> None:
        for role in UserRole:
            with self.subTest(role=role.value):
                profile = self.make_profile(role)
                authorized = await require_roles(role)(profile)
                self.assertEqual(authorized.role, role)

    async def test_nonmatching_role_is_forbidden(self) -> None:
        profile = self.make_profile(UserRole.PATIENT)

        with self.assertRaises(HTTPException) as error:
            await require_roles(UserRole.DOCTOR)(profile)

        self.assertEqual(error.exception.status_code, 403)

    async def test_admin_can_access_role_protected_resources(self) -> None:
        profile = self.make_profile(UserRole.ADMIN)

        authorized = await require_roles(UserRole.DOCTOR)(profile)

        self.assertEqual(authorized.role, UserRole.ADMIN)


if __name__ == "__main__":
    unittest.main()
