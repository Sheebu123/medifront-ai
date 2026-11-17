'use client'

import { createClient } from '@/lib/supabase/client'
import type { Appointment, AppointmentCreateInput } from '@/lib/appointments/types'

export class FastApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'FastApiError'
  }
}

function getFastApiBaseUrl(): string {
  const configuredUrl = process.env.NEXT_PUBLIC_FASTAPI_BASE_URL?.trim()
  if (!configuredUrl) {
    throw new FastApiError(
      'FastAPI is not configured. Set NEXT_PUBLIC_FASTAPI_BASE_URL in frontend/.env.local.',
      0,
    )
  }

  return configuredUrl.replace(/\/+$/, '')
}

async function parseResponse<T>(response: Response): Promise<T> {
  const responseText = await response.text()
  let payload: unknown = null

  if (responseText) {
    try {
      payload = JSON.parse(responseText)
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload !== null && 'detail' in payload
        ? (payload as { detail?: unknown }).detail
        : null
    const validationMessages = Array.isArray(detail)
      ? detail
          .map((issue) =>
            typeof issue === 'object' && issue !== null && 'msg' in issue
              ? (issue as { msg?: unknown }).msg
              : null,
          )
          .filter((message): message is string => typeof message === 'string')
          .join(' ')
      : ''
    const message =
      typeof detail === 'string'
        ? detail
        : validationMessages ||
          (response.status === 401
            ? 'Your session has expired. Please sign in again.'
            : `The backend request failed (${response.status}).`)
    throw new FastApiError(message, response.status)
  }

  return payload as T
}

async function sendWithToken(
  path: string,
  accessToken: string,
  init: RequestInit,
): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${accessToken}`)
  headers.set('Accept', 'application/json')
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const url = `${getFastApiBaseUrl()}/api/v1${path}`
  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers,
      cache: 'no-store',
    })
  } catch {
    throw new FastApiError(
      'Could not reach the MediFront backend. Check that FastAPI is running and the URL is correct.',
      0,
    )
  }

  return response
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createClient()
  const { data, error } = await supabase.auth.getSession()
  if (error) {
    throw new FastApiError('Could not read your Supabase session. Please sign in again.', 401)
  }
  if (!data.session) {
    throw new FastApiError('Please sign in before using appointments.', 401)
  }

  let response = await sendWithToken(path, data.session.access_token, init)
  if (response.status === 401) {
    const { data: refreshed, error: refreshError } = await supabase.auth.refreshSession()
    if (!refreshError && refreshed.session) {
      response = await sendWithToken(path, refreshed.session.access_token, init)
    }
  }

  return parseResponse<T>(response)
}

export function getAppointments(): Promise<Appointment[]> {
  return request<Appointment[]>('/appointments', { method: 'GET' })
}

export function createAppointment(input: AppointmentCreateInput): Promise<Appointment> {
  return request<Appointment>('/appointments', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export function cancelAppointment(appointmentId: string): Promise<Appointment> {
  return request<Appointment>(`/appointments/${encodeURIComponent(appointmentId)}/cancel`, {
    method: 'PATCH',
  })
}
