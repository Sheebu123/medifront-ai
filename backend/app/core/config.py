"""Application metadata and environment-backed settings."""

import os
from urllib.parse import urlsplit


class SupabaseConfigurationError(RuntimeError):
    """Raised when required Supabase connection settings are missing or invalid."""

APP_TITLE = "MediFront AI Backend"
APP_DESCRIPTION = (
    "Backend API foundation for the MediFront AI intelligent hospital receptionist."
)
API_VERSION = "0.1.0"

DEFAULT_FRONTEND_ORIGIN = "http://localhost:3000"


def get_cors_origins() -> list[str]:
    """Return configured frontend origins, defaulting to local Next.js."""
    configured_origins = os.getenv("FRONTEND_ORIGIN", DEFAULT_FRONTEND_ORIGIN)
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


def get_supabase_url() -> str:
    """Return the Supabase project URL from the backend environment."""
    value = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SupabaseConfigurationError("SUPABASE_URL is missing or invalid")
    return value


def get_supabase_api_key() -> str:
    """Return a publishable/anon key, never a service-role credential."""
    value = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or ""
    ).strip()
    if not value:
        raise SupabaseConfigurationError(
            "Set SUPABASE_PUBLISHABLE_KEY (or SUPABASE_ANON_KEY) in the backend environment"
        )
    return value
