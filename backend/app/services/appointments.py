"""Appointment operations using the caller's Supabase token and RLS policies."""

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.core.config import get_supabase_api_key, get_supabase_url
from app.schemas.appointments import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentSlot,
    AppointmentStatus,
)

APPOINTMENT_FIELDS = (
    "id,patient_id,doctor_id,appointment_date,appointment_time,reason,status,created_at"
)
REQUEST_TIMEOUT_SECONDS = 8
TableMethod = Literal["GET", "POST", "PATCH"]


class AppointmentServiceError(Exception):
    """Base class for expected appointment service errors."""


class AppointmentNotFound(AppointmentServiceError):
    """No appointment visible to this caller matches the requested ID."""


class InvalidDoctor(AppointmentServiceError):
    """The requested doctor ID does not identify a doctor profile."""


class AppointmentInPast(AppointmentServiceError):
    """The requested local date and time have already passed."""


class AppointmentConflict(AppointmentServiceError):
    """An appointment overlaps, or changed during a conditional update."""


class SupabaseDataAccessDenied(AppointmentServiceError):
    """Supabase RLS or table privileges denied the caller-scoped operation."""


class SupabaseDataInvalid(AppointmentServiceError):
    """Supabase rejected request data or a database constraint."""


class SupabaseDataUnavailable(AppointmentServiceError):
    """The Supabase Data API could not complete the request."""


def _request_json_sync(
    method: TableMethod,
    params: dict[str, str],
    access_token: str,
    payload: dict[str, Any] | None,
    prefer: str | None,
) -> Any:
    """Perform one bounded PostgREST request without logging credentials."""
    query = urlencode(params)
    url = f"{get_supabase_url()}/rest/v1/appointments"
    if query:
        url = f"{url}?{query}"

    headers = {
        "apikey": get_supabase_api_key(),
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")
    if prefer:
        headers["Prefer"] = prefer

    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read()
    except HTTPError as error:
        if error.code in {401, 403}:
            raise SupabaseDataAccessDenied from None
        if error.code == 409:
            raise AppointmentConflict from None
        if error.code in {400, 422}:
            raise SupabaseDataInvalid from None
        raise SupabaseDataUnavailable from None
    except (URLError, TimeoutError, OSError):
        raise SupabaseDataUnavailable from None

    try:
        return json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SupabaseDataUnavailable from None


def _request_booking_check_sync(
    access_token: str,
    patient_id: UUID,
    doctor_id: UUID,
) -> bool:
    """Ask the narrow RLS-safe RPC whether this caller may book with a doctor."""
    url = f"{get_supabase_url()}/rest/v1/rpc/patient_can_book_with_doctor"
    payload = {
        "p_patient_id": str(patient_id),
        "p_doctor_id": str(doctor_id),
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": get_supabase_api_key(),
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read()
    except HTTPError as error:
        if error.code in {401, 403}:
            raise SupabaseDataAccessDenied from None
        if error.code in {400, 422}:
            raise SupabaseDataInvalid from None
        raise SupabaseDataUnavailable from None
    except (URLError, TimeoutError, OSError):
        raise SupabaseDataUnavailable from None

    try:
        result = json.loads(response_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SupabaseDataUnavailable from None
    if not isinstance(result, bool):
        raise SupabaseDataUnavailable
    return result


async def verify_doctor_for_patient(
    access_token: str,
    patient_id: UUID,
    doctor_id: UUID,
) -> bool:
    """Validate the doctor via the caller-scoped, profile-RLS-safe RPC."""
    return await asyncio.to_thread(
        _request_booking_check_sync,
        access_token,
        patient_id,
        doctor_id,
    )


async def _request_table(
    method: TableMethod,
    params: dict[str, str],
    access_token: str,
    payload: dict[str, Any] | None = None,
    prefer: str | None = None,
) -> Any:
    return await asyncio.to_thread(
        _request_json_sync,
        method,
        params,
        access_token,
        payload,
        prefer,
    )


def _parse_rows(data: Any) -> list[AppointmentResponse]:
    if not isinstance(data, list):
        raise SupabaseDataUnavailable
    try:
        return [AppointmentResponse.model_validate(row) for row in data]
    except (ValidationError, TypeError):
        raise SupabaseDataUnavailable from None


async def list_appointments(
    access_token: str,
    scope: dict[str, str],
) -> list[AppointmentResponse]:
    data = await _request_table(
        "GET",
        {"select": APPOINTMENT_FIELDS, **scope},
        access_token,
    )
    return _parse_rows(data)


async def get_appointment(
    access_token: str,
    appointment_id: UUID,
    scope: dict[str, str],
) -> AppointmentResponse:
    data = await _request_table(
        "GET",
        {
            "select": APPOINTMENT_FIELDS,
            "id": f"eq.{appointment_id}",
            **scope,
        },
        access_token,
    )
    rows = _parse_rows(data)
    if not rows:
        raise AppointmentNotFound
    if len(rows) != 1:
        raise SupabaseDataUnavailable
    return rows[0]


def _appointment_start(appointment_date: date, appointment_time: time) -> datetime:
    return datetime.combine(appointment_date, appointment_time)


async def create_appointment(
    access_token: str,
    patient_id: UUID,
    request: AppointmentCreate,
) -> AppointmentResponse:
    """Validate a doctor and create an appointment for the authenticated patient."""
    starts_at = _appointment_start(request.appointment_date, request.appointment_time)
    local_now = datetime.now().astimezone().replace(tzinfo=None)
    if starts_at <= local_now:
        raise AppointmentInPast

    if not await verify_doctor_for_patient(access_token, patient_id, request.doctor_id):
        raise InvalidDoctor

    if await find_booking_conflict(
        access_token,
        patient_id,
        request.doctor_id,
        request.appointment_date,
        request.appointment_time,
    ):
        raise AppointmentConflict

    row = {
        "id": str(uuid4()),
        "patient_id": str(patient_id),
        "doctor_id": str(request.doctor_id),
        "appointment_date": request.appointment_date.isoformat(),
        "appointment_time": request.appointment_time.isoformat(),
        "reason": request.reason,
        "status": AppointmentStatus.SCHEDULED.value,
        "created_at": datetime.now(UTC).isoformat(),
    }
    data = await _request_table(
        "POST",
        {"select": APPOINTMENT_FIELDS},
        access_token,
        payload=row,
        prefer="return=representation",
    )
    rows = _parse_rows(data)
    if len(rows) != 1:
        raise SupabaseDataUnavailable
    return rows[0]


async def _appointments_in_date_window(
    access_token: str,
    column: Literal["patient_id", "doctor_id"],
    user_id: UUID,
    first_date: date,
    last_date: date,
) -> list[AppointmentSlot]:
    data = await _request_table(
        "GET",
        {
            "select": "appointment_date,appointment_time,status",
            column: f"eq.{user_id}",
            "and": (
                f"(appointment_date.gte.{first_date},"
                f"appointment_date.lte.{last_date})"
            ),
            "status": "in.(scheduled,confirmed)",
        },
        access_token,
    )
    if not isinstance(data, list):
        raise SupabaseDataUnavailable
    try:
        return [AppointmentSlot.model_validate(row) for row in data]
    except (ValidationError, TypeError):
        raise SupabaseDataUnavailable from None


async def find_booking_conflict(
    access_token: str,
    patient_id: UUID,
    doctor_id: UUID,
    appointment_date: date,
    appointment_time: time,
) -> bool:
    """Check visible active slots; database exclusion constraints close race windows."""
    starts_at = _appointment_start(appointment_date, appointment_time)
    ends_at = starts_at + timedelta(minutes=30)
    first_date = (starts_at - timedelta(minutes=30)).date()
    last_date = ends_at.date()

    checks: list[tuple[Literal["patient_id", "doctor_id"], UUID]] = [
        ("patient_id", patient_id),
        ("doctor_id", doctor_id),
    ]
    for column, user_id in checks:
        rows = await _appointments_in_date_window(
            access_token,
            column,
            user_id,
            first_date,
            last_date,
        )
        for appointment in rows:
            existing_start = _appointment_start(
                appointment.appointment_date,
                appointment.appointment_time,
            )
            existing_end = existing_start + timedelta(minutes=30)
            if existing_start < ends_at and existing_end > starts_at:
                return True
    return False


async def update_appointment_status(
    access_token: str,
    appointment_id: UUID,
    scope: dict[str, str],
    new_status: AppointmentStatus,
    *,
    cancellation: bool = False,
) -> AppointmentResponse:
    """Update status conditionally so concurrent status changes are detected."""
    current = await get_appointment(access_token, appointment_id, scope)
    if cancellation and current.status not in {
        AppointmentStatus.SCHEDULED,
        AppointmentStatus.CONFIRMED,
    }:
        raise AppointmentConflict

    data = await _request_table(
        "PATCH",
        {
            "id": f"eq.{appointment_id}",
            "status": f"eq.{current.status.value}",
            **scope,
        },
        access_token,
        payload={"status": new_status.value},
        prefer="return=representation",
    )
    rows = _parse_rows(data)
    if not rows:
        raise AppointmentConflict
    if len(rows) != 1:
        raise SupabaseDataUnavailable
    return rows[0]
