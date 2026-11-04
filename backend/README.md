# MediFront AI Backend

## Supabase authentication

The FastAPI backend uses the existing Supabase Auth project. It verifies each
bearer token by requesting the current user from Supabase Auth, then reads the
profile through Supabase's Data API with that same user's token. The profile
read therefore uses the authenticated user's database/RLS context.

The backend follows the profile contract already used by the Next.js app:
`profiles.id`, `full_name`, `phone`, and `role`. Roles come from that database
profile (`patient`, `doctor`, `receptionist`, or `admin`); request data and JWT
user metadata are not used to choose a role. This backend provides no role
assignment endpoint. Keep the database policy that prevents users from
changing their own role in place.

### Environment

If `backend/.env` does not already exist, copy `.env.example` to `.env`. If it
already exists, keep it and verify the required variables below without
replacing its values:

- `SUPABASE_URL`: the project's URL. The existing frontend calls this
  `NEXT_PUBLIC_SUPABASE_URL`.
- `SUPABASE_PUBLISHABLE_KEY`: the project's publishable key. The existing
  frontend calls this `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. For projects that
  still use the legacy anon key, `SUPABASE_ANON_KEY` is also accepted.
- `FRONTEND_ORIGIN`: optional comma-separated browser origins; it defaults to
  `http://localhost:3000`.

The publishable/anon key is used for Auth and Data API requests. Do not put a
service-role or secret key in this configuration, and never expose one to the
frontend. Keep `.env` out of version control.

### Run and test

From `backend/`, start the API with:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env
```

Open `http://localhost:8000/docs` for the Swagger UI. Sign in through the
existing frontend/Supabase Auth flow and provide that session's access token
as a bearer token:

```text
GET http://localhost:8000/api/v1/auth/me
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
```

For example, with curl:

```sh
curl -H "Authorization: Bearer <SUPABASE_ACCESS_TOKEN>" \
  http://localhost:8000/api/v1/auth/me
```

The endpoint returns the verified Auth user ID and the caller-visible profile.
Missing, invalid, and expired tokens return HTTP 401. A missing or RLS-invisible
profile returns 404; an explicit profile access denial or unsupported role
returns 403. Role checks for future protected endpoints are reusable with
`Depends(require_roles(UserRole.DOCTOR))` (and the other `UserRole` values).

Run the backend's standard-library test suite from `backend/` with:

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

## Appointment API

All appointment endpoints require a Supabase bearer token:

- `POST /api/v1/appointments`: patients only. The body accepts `doctor_id`,
  `appointment_date`, `appointment_time`, and optional nullable `reason`.
  The backend supplies `patient_id`, `id`, `status` (`scheduled`), and
  `created_at`.
- `GET /api/v1/appointments` and `GET /api/v1/appointments/{appointment_id}`:
  patients see their own rows, doctors see rows assigned to them, and
  receptionists/admins see all rows.
- `PATCH /api/v1/appointments/{appointment_id}/cancel`: patients may cancel
  their own appointment; receptionists/admins may cancel any. Repeated
  cancellation returns 409.
- `PATCH /api/v1/appointments/{appointment_id}/status`: receptionists/admins
  only; valid statuses are `scheduled`, `confirmed`, `cancelled`, and
  `completed`.

Bookings reject date/time values that have passed, validate that `doctor_id`
belongs to a doctor profile, and check 30-minute overlaps for both patient and
doctor. Date/time values are interpreted in the backend host's local timezone;
set the host timezone to the hospital timezone. Database exclusion constraints
provide the atomic overlap guarantee for concurrent bookings.

The appointment service sends the caller's bearer token with every Supabase
Data API and RPC request, so those operations execute under the caller's
database role and RLS context. It does not use a service-role key. Because
profiles are visible only to their owner, doctor validation uses the
`patient_can_book_with_doctor` SECURITY DEFINER function. It checks that the
caller is the named patient and that the target profile has the doctor role,
returns only a boolean, fixes `search_path`, and grants execution only to
`authenticated`; it does not grant profile reads.

The repository contains no earlier SQL definitions for appointment or profile
policies. The migration adds named role-scoped appointment policies and leaves
unrelated policies in place. Existing restrictive policies can continue to
narrow access. Review the live `pg_policies` entries before applying the
migration if the Supabase project has policies not represented in this repo.

Apply [20261105_appointments_constraints.sql](../database/migrations/20261105_appointments_constraints.sql)
to the Supabase database before using the API. It adds no columns. It checks
for unsupported statuses and existing active overlaps before adding the
constraints and policies.
