import type { User } from '@supabase/supabase-js'
import { redirect } from 'next/navigation'

import { createClient } from '@/lib/supabase/server'

export type UserRole = 'patient' | 'doctor' | 'receptionist' | 'admin'

export type Profile = {
  id: string
  full_name: string | null
  phone: string | null
  role: UserRole
}

export async function getCurrentUser(): Promise<User | null> {
  const supabase = await createClient()
  const { data, error } = await supabase.auth.getUser()

  if (error) {
    return null
  }

  return data.user
}

export async function getCurrentProfile(): Promise<Profile | null> {
  const user = await getCurrentUser()
  if (!user) return null

  const supabase = await createClient()

  // Primary: Retrieve profile from Neon PostgreSQL through FastAPI's verified auth/me
  try {
    const { data: sessionData } = await supabase.auth.getSession()
    const token = sessionData.session?.access_token

    if (token) {
      const baseUrl = (
        process.env.FASTAPI_BASE_URL ||
        process.env.NEXT_PUBLIC_FASTAPI_BASE_URL ||
        'http://127.0.0.1:8000'
      ).replace(/\/+$/, '')

      const response = await fetch(`${baseUrl}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/json',
        },
        cache: 'no-store',
      })

      if (response.ok) {
        const payload = (await response.json()) as { profile?: Profile }
        if (payload?.profile?.role) {
          return payload.profile
        }
      }
    }
  } catch {
    // If FastAPI cannot be reached, continue to safe fallback
  }

  // Secondary fallback: query existing profile record directly
  const { data, error } = await supabase
    .from('profiles')
    .select('id, full_name, phone, role')
    .eq('id', user.id)
    .maybeSingle()

  if (!error && data) {
    return data as Profile
  }

  // Safe default: return patient role for authenticated user
  return {
    id: user.id,
    full_name: (user.user_metadata?.full_name as string) || null,
    phone: (user.user_metadata?.phone as string) || null,
    role: 'patient',
  }
}

export async function requireUser(): Promise<User> {
  const user = await getCurrentUser()
  if (!user) redirect('/login')
  return user
}

export async function requireRole(role: UserRole): Promise<{ user: User; profile: Profile }> {
  const user = await requireUser()
  const profile = await getCurrentProfile()

  if (!profile || (profile.role !== role && profile.role !== 'admin')) {
    redirect('/unauthorized')
  }

  return { user, profile }
}

export async function requireAnyRole(roles: UserRole[]): Promise<{ user: User; profile: Profile }> {
  const user = await requireUser()
  const profile = await getCurrentProfile()

  if (!profile || (profile.role !== 'admin' && !roles.includes(profile.role))) {
    redirect('/unauthorized')
  }

  return { user, profile }
}