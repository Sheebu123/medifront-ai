'use client'

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { CalendarDays, CheckCircle, CheckCircle2, Filter, LoaderCircle, Stethoscope, XCircle } from 'lucide-react'

import {
  FastApiError,
  cancelAppointment,
  createAppointment,
  getAppointments,
  getDoctors,
  updateAppointmentStatus,
} from '@/lib/api/fastapi'
import type { Appointment, AppointmentCreateInput, AppointmentRole, AppointmentStatus, Doctor } from '@/lib/appointments/types'

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
  const [doctors, setDoctors] = useState<Doctor[]>([])
  const [isLoading, setIsLoading] = useState(Boolean(role))
  const [busyAppointment, setBusyAppointment] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [today, setToday] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  // Booking form state
  const [doctorId, setDoctorId] = useState('')
  const [customDoctorId, setCustomDoctorId] = useState(false)
  const [appointmentDate, setAppointmentDate] = useState('')
  const [appointmentTime, setAppointmentTime] = useState('')
  const [reason, setReason] = useState('')

  const isStaff = role === 'receptionist' || role === 'admin'

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

  useEffect(() => {
    if (role === 'patient') {
      void getDoctors()
        .then((items) => {
          setDoctors(items)
          if (items.length > 0 && !doctorId) {
            setDoctorId(items[0].id)
          }
        })
        .catch(() => {
          // If doctors endpoint is not reached, patient can type doctor UUID manually
          setCustomDoctorId(true)
        })
    }
  }, [role])

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
      setSuccess('Your appointment has been successfully booked.')
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
    if (busyAppointment) return
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

  async function handleStatusChange(appointment: Appointment, newStatus: AppointmentStatus) {
    if (busyAppointment || !isStaff) return

    setBusyAppointment(appointment.id)
    setError(null)
    setSuccess(null)
    try {
      await updateAppointmentStatus(appointment.id, newStatus)
      setSuccess(`Appointment status updated to ${newStatus}.`)
      await refreshAppointments()
    } catch (requestError) {
      setError(getErrorMessage(requestError))
    } finally {
      setBusyAppointment(null)
    }
  }

  const filteredAppointments = appointments
    .filter((apt) => statusFilter === 'all' || apt.status === statusFilter)
    .sort((left, right) =>
      `${left.appointment_date}T${left.appointment_time}`.localeCompare(
        `${right.appointment_date}T${right.appointment_time}`,
      ),
    )

  const heading =
    role === 'doctor'
      ? 'Assigned Appointments'
      : role === 'patient'
        ? 'My Appointments'
        : role === 'receptionist'
          ? 'Front Desk Appointments'
          : role === 'admin'
            ? 'Hospital Master Appointments'
            : "Today's Appointments"

  return (
    <section className="panel appointments-panel">
      <div className="panel-heading">
        <div>
          <h2>{heading}</h2>
          <p>
            {role === 'doctor'
              ? 'Appointments assigned to your doctor profile.'
              : role === 'patient'
                ? 'Your scheduled, confirmed, and previous appointments.'
                : isStaff
                  ? 'Manage hospital scheduling, check-ins, confirmations, and cancellations.'
                  : 'Live appointment activity.'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
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
      </div>

      {isStaff && (
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', color: '#65778a', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Filter size={13} /> Filter status:
          </span>
          {['all', 'scheduled', 'confirmed', 'completed', 'cancelled'].map((status) => (
            <button
              key={status}
              type="button"
              className={`button ${statusFilter === status ? 'button-primary' : 'button-outline'}`}
              style={{ fontSize: '10px', padding: '5px 10px' }}
              onClick={() => setStatusFilter(status)}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      )}

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
      ) : filteredAppointments.length === 0 ? (
        <p className="appointment-state">
          {role === 'doctor'
            ? 'No appointments are assigned to you yet.'
            : isStaff
              ? 'No appointments match the current view.'
              : 'No appointments found.'}
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date &amp; time</th>
                <th>{role === 'doctor' ? 'Patient ID' : 'Doctor ID'}</th>
                {isStaff && <th>Patient ID</th>}
                <th>Reason</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredAppointments.map((appointment) => {
                const isBusy = busyAppointment === appointment.id
                return (
                  <tr key={appointment.id}>
                    <td>{appointment.appointment_date} {appointment.appointment_time.slice(0, 5)}</td>
                    <td>{role === 'doctor' ? appointment.patient_id : appointment.doctor_id}</td>
                    {isStaff && <td>{appointment.patient_id}</td>}
                    <td>{appointment.reason || '—'}</td>
                    <td>
                      <span className={`status-badge status-${statusTone(appointment.status)}`}>
                        {appointment.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        {/* Patient can cancel scheduled/confirmed */}
                        {role === 'patient' && ['scheduled', 'confirmed'].includes(appointment.status) && (
                          <button
                            className="button button-danger"
                            type="button"
                            onClick={() => void handleCancellation(appointment)}
                            disabled={busyAppointment !== null}
                          >
                            {isBusy ? <LoaderCircle size={13} className="appointment-spinner" /> : <XCircle size={13} />}
                            Cancel
                          </button>
                        )}

                        {/* Staff actions: Confirm, Complete, Cancel */}
                        {isStaff && appointment.status === 'scheduled' && (
                          <>
                            <button
                              className="button button-primary"
                              type="button"
                              onClick={() => void handleStatusChange(appointment, 'confirmed')}
                              disabled={busyAppointment !== null}
                              style={{ padding: '4px 8px', fontSize: '10px' }}
                            >
                              {isBusy ? <LoaderCircle size={12} className="appointment-spinner" /> : <CheckCircle size={12} />}
                              Confirm
                            </button>
                            <button
                              className="button button-danger"
                              type="button"
                              onClick={() => void handleCancellation(appointment)}
                              disabled={busyAppointment !== null}
                              style={{ padding: '4px 8px', fontSize: '10px' }}
                            >
                              <XCircle size={12} /> Cancel
                            </button>
                          </>
                        )}

                        {isStaff && appointment.status === 'confirmed' && (
                          <>
                            <button
                              className="button button-soft"
                              type="button"
                              onClick={() => void handleStatusChange(appointment, 'completed')}
                              disabled={busyAppointment !== null}
                              style={{ padding: '4px 8px', fontSize: '10px' }}
                            >
                              {isBusy ? <LoaderCircle size={12} className="appointment-spinner" /> : <CheckCircle2 size={12} />}
                              Complete
                            </button>
                            <button
                              className="button button-danger"
                              type="button"
                              onClick={() => void handleCancellation(appointment)}
                              disabled={busyAppointment !== null}
                              style={{ padding: '4px 8px', fontSize: '10px' }}
                            >
                              <XCircle size={12} /> Cancel
                            </button>
                          </>
                        )}

                        {(!['scheduled', 'confirmed'].includes(appointment.status) || (role === 'doctor')) && (
                          <span style={{ color: '#9aa8b4', fontSize: '10px' }}>—</span>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
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

          {!customDoctorId && doctors.length > 0 ? (
            <label>
              Select Doctor
              <select
                required
                value={doctorId}
                onChange={(event) => {
                  if (event.target.value === '__custom__') {
                    setCustomDoctorId(true)
                    setDoctorId('')
                  } else {
                    setDoctorId(event.target.value)
                  }
                }}
                style={{
                  height: '40px',
                  borderRadius: '8px',
                  border: '1px solid #dbe6ed',
                  padding: '0 10px',
                  backgroundColor: '#fff',
                  color: '#102a43',
                }}
              >
                {doctors.map((doctor) => (
                  <option key={doctor.id} value={doctor.id}>
                    {doctor.full_name ? `${doctor.full_name}` : `Doctor (${doctor.id.slice(0, 8)}...)`}
                  </option>
                ))}
                <option value="__custom__">Enter custom Doctor UUID...</option>
              </select>
            </label>
          ) : (
            <div>
              <label>
                Doctor Profile UUID
                <input
                  autoComplete="off"
                  required
                  value={doctorId}
                  onChange={(event) => setDoctorId(event.target.value)}
                  placeholder="Doctor profile UUID (e.g. b74f1b2e-...)"
                />
              </label>
              {doctors.length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    setCustomDoctorId(false)
                    if (doctors.length > 0) setDoctorId(doctors[0].id)
                  }}
                  style={{
                    fontSize: '10px',
                    color: '#2878d7',
                    background: 'none',
                    border: 'none',
                    padding: '2px 0 8px',
                    cursor: 'pointer',
                  }}
                >
                  &larr; Choose from available doctors list
                </button>
              )}
            </div>
          )}

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
