"""Application metadata and environment-backed settings."""

import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class SupabaseConfigurationError(RuntimeError):
    """Raised when required Supabase connection settings are missing or invalid."""


class DatabaseConfigurationError(RuntimeError):
    """Raised when the application database connection is missing or invalid."""

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


def get_database_url(*, for_migrations: bool = False) -> str:
    """Return a psycopg 3 URL with SSL required and secrets omitted from errors.

    Neon migrations should use the direct connection string when supplied.
    Application traffic normally uses DATABASE_URL, which may be pooled. Other
    query options are retained while any existing sslmode is normalized to one
    ``sslmode=require`` entry.
    """
    if for_migrations:
        value = os.getenv("DATABASE_URL_UNPOOLED", "").strip()
        if not value:
            raise DatabaseConfigurationError(
                "DATABASE_URL_UNPOOLED is required for Alembic migrations"
            )
    else:
        value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise DatabaseConfigurationError("DATABASE_URL is not configured")

    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://") :]
    elif value.startswith("postgresql+psycopg://"):
        pass
    else:
        raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL URL")

    value = _require_sslmode(value)
    if for_migrations:
        hostname = urlsplit(value).hostname or ""
        if hostname.endswith("-pooler") or "-pooler." in hostname:
            raise DatabaseConfigurationError(
                "DATABASE_URL_UNPOOLED must use a direct PostgreSQL connection"
            )
    return value


def _require_sslmode(database_url: str) -> str:
    """Ensure a PostgreSQL URL has exactly one sslmode=require parameter."""
    parsed = urlsplit(database_url)
    query: list[tuple[str, str]] = []
    has_sslmode = False
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() == "sslmode":
            if not has_sslmode:
                query.append(("sslmode", "require"))
                has_sslmode = True
            continue
        query.append((key, value))
    if not has_sslmode:
        query.append(("sslmode", "require"))

    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )
