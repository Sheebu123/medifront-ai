# MediFront AI — Production Deployment Guide

This guide details the verified production deployment procedures for MediFront AI.

---

## 1. Architecture Overview

- **Frontend**: Next.js 16 (App Router) on **Vercel**.
- **Backend**: FastAPI with Python on **Render**.
- **Database**: Neon Serverless PostgreSQL (`profiles` and `appointments`).
- **Authentication**: Supabase Auth (token verification on FastAPI; cookie sessions on Next.js).

---

## 2. Frontend Deployment (Vercel)

### Root Directory & Build Settings
- **Root Directory**: `frontend` (set in Vercel project settings or automatically picked up via `frontend/vercel.json`).
- **Framework Preset**: `Next.js`
- **Build Command**: `pnpm run build` (runs `next build --webpack`)
- **Install Command**: `pnpm install`

### Required Environment Variables on Vercel
| Variable | Description | Example / Note |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Project URL | `https://xxxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Supabase Public / Publishable key | `sb_publishable_...` |
| `NEXT_PUBLIC_FASTAPI_BASE_URL` | Render FastAPI Backend URL | `https://medifront-ai-backend.onrender.com` |
| `FASTAPI_BASE_URL` | (Optional) Server-to-server URL | `https://medifront-ai-backend.onrender.com` |

---

## 3. Backend Deployment (Render)

### Service Specification
A ready-to-use Render Blueprint is provided in `render.yaml`.
- **Environment**: Python
- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Check Path**: `/health`

### Required Environment Variables on Render
| Variable | Description | Security Note |
|---|---|---|
| `DATABASE_URL` | Neon pooled PostgreSQL URL | `postgresql://...@...-pooler.../...?sslmode=require` |
| `DATABASE_URL_UNPOOLED` | Neon direct PostgreSQL URL | Required for migrations; do not use pooler host |
| `SUPABASE_URL` | Supabase Project URL | e.g. `https://xxxx.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase Publishable / Anon key | Never supply service-role secret |
| `FRONTEND_ORIGIN` | Allowed CORS origins | `https://your-medifront-app.vercel.app` |

### Database Migration Strategy
Alembic schema migrations must always run against `DATABASE_URL_UNPOOLED`:
```bash
alembic upgrade head
```
The migration `20261106_0001` is forward-only to prevent destructive table loss. Existing records in Neon are preserved.

---

## 4. Verification Checkpoints

1. **Backend Health**: `GET https://<render-host>/health` returns `{"status": "healthy"}`.
2. **API Documentation**: `GET https://<render-host>/docs` displays interactive OpenAPI docs.
3. **Frontend Dashboard**: Log in at `https://<vercel-host>/login`. Successfully redirects to role-specific dashboard (`/patient/dashboard`, `/doctor/dashboard`, etc.).
4. **Appointment Workflow**: Book and manage appointments via Neon PostgreSQL backed endpoints.
