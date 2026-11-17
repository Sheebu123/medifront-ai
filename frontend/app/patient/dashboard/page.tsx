import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function PatientDashboardPage() {
  const { profile } = await requireRole('patient')
  return <MediFrontDashboard role={profile.role} />
}
