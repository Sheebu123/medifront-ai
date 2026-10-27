import type { UserRole } from '@/lib/auth/server'

import { createClient } from '@/lib/supabase/server'

export type Appointment = {
  id: string
  patient_id: string
  doctor_id: string
  appointment_date: string
  appointment_time: string
  reason: string | null
  status: string
  created_at: string
}

const appointmentFields =
  'id, patient_id, doctor_id, appointment_date, appointment_time, reason, status, created_at'

export async function getAppointmentsForUser(
  role: UserRole,
  userId: string,
): Promise<Appointment[]> {
  if (role !== 'patient' && role !== 'doctor') {
    throw new Error(`Appointment queries are not enabled for the ${role} role yet.`)
  }

  const supabase = await createClient()
  const query = supabase.from('appointments').select(appointmentFields)
  const scopedQuery = role === 'patient'
    ? query.eq('patient_id', userId)
    : query.eq('doctor_id', userId)
  const { data, error } = await scopedQuery

  if (error) {
    throw new Error(`Unable to load appointments: ${error.message}`)
  }

  return (data ?? []) as Appointment[]
}
