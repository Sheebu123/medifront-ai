import MediFrontDashboard from '@/components/medifront-dashboard'
import { getAppointmentsForUser } from '@/lib/appointments/server'
import { requireRole } from '@/lib/auth/server'

export default async function PatientDashboardPage() {
  const { user } = await requireRole('patient')
  const appointments = await getAppointmentsForUser('patient', user.id)
  return <MediFrontDashboard appointments={appointments} />
}