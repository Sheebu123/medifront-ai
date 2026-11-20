export type AppointmentStatus = 'scheduled' | 'confirmed' | 'cancelled' | 'completed'

export type Appointment = {
  id: string
  patient_id: string
  doctor_id: string
  appointment_date: string
  appointment_time: string
  reason: string | null
  status: AppointmentStatus
  created_at: string
}

export type AppointmentCreateInput = {
  doctor_id: string
  appointment_date: string
  appointment_time: string
  reason: string | null
}

export type AppointmentRole = 'patient' | 'doctor' | 'receptionist' | 'admin'

export type Doctor = {
  id: string
  full_name: string | null
  phone: string | null
}
