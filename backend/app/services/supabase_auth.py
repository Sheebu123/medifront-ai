"""Small async wrapper around Supabase Auth and the caller-scoped Data API."""

import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import get_supabase_api_key, get_supabase_url

REQUEST_TIMEOUT_SECONDS = 8
logger = logging.getLogger(__name__)


class SupabaseInvalidToken(Exception):
    """Supabase Auth rejected the supplied access token."""


class SupabaseServiceUnavailable(Exception):
    """Supabase could not be reached or returned an unusable response."""


def _request_json(request: Request) -> Any:
    """Make a bounded request without logging credentials or response bodies."""
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = response.read()
    except HTTPError as error:
        # A 401 is an explicit token rejection. Other client/upstream statuses
        # can indicate API-key or project configuration problems and must not
        # be reported as invalid user credentials.
        if error.code == 401:
            logger.info("Supabase Auth rejected a bearer token (HTTP %d)", error.code)
            raise SupabaseInvalidToken from None
        logger.warning("Supabase Auth returned an upstream HTTP %d", error.code)
        raise SupabaseServiceUnavailable from None
    except (URLError, TimeoutError, OSError) as error:
        logger.warning(
            "Supabase Auth network request failed (%s)", type(error).__name__
        )
        raise SupabaseServiceUnavailable from None

    try:
        return json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        logger.warning(
            "Supabase Auth returned an unusable JSON response (%s)",
            type(error).__name__,
        )
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
    result = await asyncio.to_thread(_request_json, request)
    if not isinstance(result, dict):
        logger.warning("Supabase Auth returned a non-object user response")
        raise SupabaseServiceUnavailable
    return result
