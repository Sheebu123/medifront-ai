import MediFrontDashboard from '@/components/medifront-dashboard'
import { getAppointmentsForUser } from '@/lib/appointments/server'
import { requireRole } from '@/lib/auth/server'

export default async function DoctorDashboardPage() {
  const { user } = await requireRole('doctor')
  const appointments = await getAppointmentsForUser('doctor', user.id)
  return <MediFrontDashboard appointments={appointments} />
}