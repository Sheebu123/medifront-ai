"""HTTP error classification tests for Supabase Auth token verification."""

import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from app.services.supabase_auth import (
    SupabaseInvalidToken,
    SupabaseServiceUnavailable,
    _request_json,
)


def make_http_error(status_code: int) -> HTTPError:
    return HTTPError(
        url="https://example.supabase.co/auth/v1/user",
        code=status_code,
        msg="upstream response",
        hdrs=None,
        fp=None,
    )


class SupabaseAuthRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        from urllib.request import Request

        self.request = Request("https://example.supabase.co/auth/v1/user")

    def test_unauthorized_response_is_classified_as_invalid_token(self) -> None:
        with patch(
            "app.services.supabase_auth.urlopen",
            side_effect=make_http_error(401),
        ):
            with self.assertRaises(SupabaseInvalidToken):
                _request_json(self.request)

    def test_bad_request_is_service_failure_not_invalid_token(self) -> None:
        with patch(
            "app.services.supabase_auth.urlopen",
            side_effect=make_http_error(400),
        ):
            with self.assertRaises(SupabaseServiceUnavailable):
                _request_json(self.request)

    def test_forbidden_response_is_service_failure_not_invalid_token(self) -> None:
        with patch(
            "app.services.supabase_auth.urlopen",
            side_effect=make_http_error(403),
        ):
            with self.assertRaises(SupabaseServiceUnavailable):
                _request_json(self.request)

    def test_upstream_server_error_is_service_failure(self) -> None:
        with patch(
            "app.services.supabase_auth.urlopen",
            side_effect=make_http_error(503),
        ):
            with self.assertRaises(SupabaseServiceUnavailable):
                _request_json(self.request)


if __name__ == "__main__":
    unittest.main()
