'use client'

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { CalendarDays, LoaderCircle, XCircle } from 'lucide-react'

import { FastApiError, cancelAppointment, createAppointment, getAppointments } from '@/lib/api/fastapi'
import type { Appointment, AppointmentCreateInput, AppointmentRole } from '@/lib/appointments/types'

type AppointmentManagementProps = {
  role?: AppointmentRole
}

function getErrorMessage(error: unknown): string {
  if (error instanceof FastApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Something went wrong while updating appointments.'
}

function localDateString(): string {
  const now = new Date()
  const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
  return localNow.toISOString().slice(0, 10)
}

function statusTone(status: Appointment['status']): string {
  if (status === 'cancelled') return 'red'
  if (status === 'completed') return 'green'
  if (status === 'confirmed') return 'blue'
  return 'amber'
}

export default function AppointmentManagement({ role }: AppointmentManagementProps) {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [isLoading, setIsLoading] = useState(Boolean(role))
  const [busyAppointment, setBusyAppointment] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [today, setToday] = useState('')
  const [doctorId, setDoctorId] = useState('')
  const [appointmentDate, setAppointmentDate] = useState('')
  const [appointmentTime, setAppointmentTime] = useState('')
  const [reason, setReason] = useState('')

  const refreshAppointments = useCallback(async () => {
    if (!role) return
    setIsLoading(true)
    try {
      const items = await getAppointments()
      setAppointments(items)
      setError(null)
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setIsLoading(false)
    }
  }, [role])

  useEffect(() => {
    setToday(localDateString())
    void refreshAppointments()
  }, [refreshAppointments])

  async function handleBooking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (role !== 'patient') return

    setBusyAppointment('booking')
    setError(null)
    setSuccess(null)

    const payload: AppointmentCreateInput = {
      doctor_id: doctorId.trim(),
      appointment_date: appointmentDate,
      appointment_time: appointmentTime,
      reason: reason.trim() || null,
    }

    try {
      await createAppointment(payload)
      setSuccess('Your appointment has been booked.')
      setDoctorId('')
      setAppointmentDate('')
      setAppointmentTime('')
      setReason('')
      await refreshAppointments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusyAppointment(null)
    }
  }

  async function handleCancellation(appointment: Appointment) {
    if (role !== 'patient' || busyAppointment) return
    if (!window.confirm('Cancel this appointment?')) return

    setBusyAppointment(appointment.id)
    setError(null)
    setSuccess(null)
    try {
      await cancelAppointment(appointment.id)
      setSuccess('The appointment has been cancelled.')
      await refreshAppointments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusyAppointment(null)
    }
  }

  const sortedAppointments = [...appointments].sort((left, right) =>
    `${left.appointment_date}T${left.appointment_time}`.localeCompare(
      `${right.appointment_date}T${right.appointment_time}`,
    ),
  )
  const heading = role === 'doctor'
    ? 'Assigned appointments'
    : role === 'patient'
      ? 'My appointments'
      : "Today's appointments"

  return (
    <section className="panel appointments-panel">
      <div className="panel-heading">
        <div>
          <h2>{heading}</h2>
          <p>
            {role === 'doctor'
              ? 'Appointments assigned to your doctor profile.'
              : role === 'patient'
                ? 'Your upcoming and previous appointments.'
                : 'Appointment activity.'}
          </p>
        </div>
        {role && (
          <button
            className="button button-ghost"
            type="button"
            onClick={() => void refreshAppointments()}
            disabled={isLoading}
          >
            {isLoading ? <LoaderCircle size={15} className="appointment-spinner" /> : 'Refresh'}
          </button>
        )}
      </div>

      {success && <p className="appointment-feedback success" role="status">{success}</p>}
      {error && <p className="appointment-feedback error" role="alert">{error}</p>}

      {isLoading ? (
        <p className="appointment-state" role="status">Loading appointments…</p>
      ) : error && appointments.length === 0 ? (
        <div className="appointment-state">
          <p>Appointments could not be loaded.</p>
          <button className="button button-outline" type="button" onClick={() => void refreshAppointments()}>
            Try again
          </button>
        </div>
      ) : sortedAppointments.length === 0 ? (
        <p className="appointment-state">
          {role === 'doctor' ? 'No appointments are assigned to you yet.' : 'No appointments found.'}
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date &amp; time</th>
                <th>{role === 'doctor' ? 'Patient ID' : 'Doctor ID'}</th>
                <th>Reason</th>
                <th>Status</th>
                {role === 'patient' && <th>Action</th>}
              </tr>
            </thead>
            <tbody>
              {sortedAppointments.map((appointment) => (
                <tr key={appointment.id}>
                  <td>{appointment.appointment_date} {appointment.appointment_time.slice(0, 5)}</td>
                  <td>{role === 'doctor' ? appointment.patient_id : appointment.doctor_id}</td>
                  <td>{appointment.reason || '—'}</td>
                  <td>
                    <span className={`status-badge status-${statusTone(appointment.status)}`}>
                      {appointment.status}
                    </span>
                  </td>
                  {role === 'patient' && (
                    <td>
                      {['scheduled', 'confirmed'].includes(appointment.status) ? (
                        <button
                          className="button button-danger"
                          type="button"
                          onClick={() => void handleCancellation(appointment)}
                          disabled={busyAppointment !== null}
                        >
                          {busyAppointment === appointment.id ? (
                            <LoaderCircle size={13} className="appointment-spinner" />
                          ) : (
                            <XCircle size={13} />
                          )}
                          Cancel
                        </button>
                      ) : '—'}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {role === 'patient' && (
        <form className="appointment-form" onSubmit={handleBooking}>
          <div className="appointment-form-heading">
            <CalendarDays size={16} />
            <h3>Book an appointment</h3>
          </div>
          <label>
            Doctor ID
            <input
              autoComplete="off"
              required
              value={doctorId}
              onChange={(event) => setDoctorId(event.target.value)}
              placeholder="Doctor profile UUID"
            />
          </label>
          <label>
            Date
            <input
              type="date"
              min={today || undefined}
              required
              value={appointmentDate}
              onChange={(event) => setAppointmentDate(event.target.value)}
            />
          </label>
          <label>
            Time
            <input
              type="time"
              required
              value={appointmentTime}
              onChange={(event) => setAppointmentTime(event.target.value)}
            />
          </label>
          <label className="appointment-reason">
            <span>Reason <em>(optional)</em></span>
            <textarea
              rows={2}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Briefly describe the reason for your visit"
            />
          </label>
          <button className="button button-primary" type="submit" disabled={busyAppointment !== null}>
            {busyAppointment === 'booking' ? 'Booking…' : 'Book appointment'}
          </button>
        </form>
      )}
    </section>
  )
}
