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
  const { data, error } = await supabase
    .from('profiles')
    .select('id, full_name, phone, role')
    .eq('id', user.id)
    .maybeSingle()

  if (error || !data) return null

  return data as Profile
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