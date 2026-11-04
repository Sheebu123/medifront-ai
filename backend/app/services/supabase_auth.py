"""Small async wrapper around Supabase Auth and the caller-scoped Data API."""

import asyncio
import json
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import get_supabase_api_key, get_supabase_url

REQUEST_TIMEOUT_SECONDS = 8
EndpointKind = Literal["auth", "profile"]


class SupabaseInvalidToken(Exception):
    """Supabase Auth rejected the supplied access token."""


class SupabaseProfileNotFound(Exception):
    """The authenticated user's profile row does not exist or is not visible."""


class SupabaseProfileAccessDenied(Exception):
    """Supabase denied access to the caller-scoped profile query."""


class SupabaseServiceUnavailable(Exception):
    """Supabase could not be reached or returned an unusable response."""


def _request_json(request: Request, endpoint: EndpointKind) -> Any:
    """Make a bounded request without logging credentials or response bodies."""
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read()
    except HTTPError as error:
        if endpoint == "auth" and error.code in {400, 401, 403}:
            raise SupabaseInvalidToken from None
        if endpoint == "profile" and error.code in {401, 403}:
            raise SupabaseProfileAccessDenied from None
        raise SupabaseServiceUnavailable from None
    except (URLError, TimeoutError, OSError):
        raise SupabaseServiceUnavailable from None

    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SupabaseServiceUnavailable from None


def _authorization_headers(access_token: str) -> dict[str, str]:
    return {
        "apikey": get_supabase_api_key(),
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


async def verify_supabase_access_token(access_token: str) -> dict[str, Any]:
    """Ask Supabase Auth to verify the token and return its current user record."""
    request = Request(
        f"{get_supabase_url()}/auth/v1/user",
        headers=_authorization_headers(access_token),
        method="GET",
    )
    result = await asyncio.to_thread(_request_json, request, "auth")
    if not isinstance(result, dict):
        raise SupabaseServiceUnavailable
    return result


async def fetch_supabase_profile(user_id: UUID, access_token: str) -> dict[str, Any]:
    """Read only the frontend's profile fields using the user's own RLS context."""
    query = urlencode(
        {
            "select": "id,full_name,phone,role",
            "id": f"eq.{user_id}",
        }
    )
    request = Request(
        f"{get_supabase_url()}/rest/v1/profiles?{query}",
        headers=_authorization_headers(access_token),
        method="GET",
    )
    result = await asyncio.to_thread(_request_json, request, "profile")
    if not isinstance(result, list):
        raise SupabaseServiceUnavailable
    if not result:
        raise SupabaseProfileNotFound
    if len(result) != 1 or not isinstance(result[0], dict):
        raise SupabaseServiceUnavailable
    return result[0]
