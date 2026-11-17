import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function DoctorDashboardPage() {
  const { profile } = await requireRole('doctor')
  return <MediFrontDashboard role={profile.role} />
}
