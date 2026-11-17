# MediFront AI Backend

FastAPI uses Supabase Auth only to verify access tokens. Application profiles
and appointments are stored in Neon PostgreSQL. The API reads roles from Neon;
it does not authorize from client input or Supabase user metadata.

## Environment

Copy `.env.example` to `.env` only if `backend/.env` does not already exist.
Keep existing local values and add the required database URL without replacing
credentials. Never commit `.env` or expose a database URL to the frontend.

- `DATABASE_URL`: Neon pooled PostgreSQL URL for application traffic. SQLAlchemy
  normalizes standard `postgresql://` URLs to psycopg 3.
- `DATABASE_URL_UNPOOLED`: direct Neon URL required for Alembic migrations;
  Alembic refuses the pooled application URL.
- `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` (or legacy
  `SUPABASE_ANON_KEY`): used only to verify the Supabase Auth access token.
- `FRONTEND_ORIGIN`: optional comma-separated browser origins; defaults to
  `http://localhost:3000`.

## Database setup

Install dependencies from `backend/`:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the schema migration only after `DATABASE_URL_UNPOOLED` points at the
intended Neon branch and a reviewed backup/cutover plan exists:

```powershell
.\venv\Scripts\alembic.exe upgrade head
```

The initial migration creates `profiles` and `appointments`, enables
`btree_gist`, and adds role/status checks, foreign keys, indexes, and 30-minute
exclusion constraints for active patient and doctor appointments. The
migration is forward-only to avoid accidental data deletion. It does not read,
modify, or migrate the old Supabase application tables.

Existing profiles and appointments need a separate, verified backfill before
production cutover. Backfill roles from the trusted existing profile records;
do not use JWT/user metadata or client requests to assign roles. For a new
Supabase Auth identity, the first authenticated API request creates a Neon
profile with the verified Auth UUID and `patient` role. Promoting an account to
doctor, receptionist, or admin is an operator-only Neon database operation.
For a controlled role change, a Neon project operator verifies the user's
Supabase Auth UUID out of band, then applies an audited update in the Neon SQL
editor, for example:

```sql
UPDATE public.profiles
SET role = 'doctor'
WHERE id = '<verified-supabase-auth-uuid>'
RETURNING id, role;
```

Use the corresponding approved role value and restrict Neon project access to
trusted operators. There is intentionally no public role-assignment endpoint.

## Run and test

From `backend/`:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --env-file .env
```

Swagger UI is at `http://localhost:8000/docs`. Send the existing Supabase
session access token as a Bearer token. The `GET /api/v1/auth/me` response
contains the verified Auth UUID and the corresponding Neon profile.

Run the backend suite from `backend/`:

```powershell
.\venv\Scripts\python.exe -m unittest discover -v
```

## Appointment API

- `POST /api/v1/appointments`: patients only; `patient_id` comes from the
  verified Supabase identity. The body accepts `doctor_id`,
  `appointment_date`, `appointment_time`, and optional nullable `reason`.
- `GET /api/v1/appointments` and `GET /api/v1/appointments/{appointment_id}`:
  patients see their own rows, doctors see rows assigned to them, and
  receptionists/admins see all rows.
- `PATCH /api/v1/appointments/{appointment_id}/cancel`: patients may cancel
  their own scheduled/confirmed appointment; receptionists/admins may cancel
  any scheduled/confirmed appointment.
- `PATCH /api/v1/appointments/{appointment_id}/status`: receptionists/admins
  only; statuses are `scheduled`, `confirmed`, `cancelled`, and `completed`.

The application checks role and appointment access in FastAPI. The database
constraints provide the atomic guarantee against overlapping 30-minute active
bookings, including concurrent requests.
