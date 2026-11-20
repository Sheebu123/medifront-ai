import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function PatientDashboardPage() {
  const { profile, user } = await requireRole('patient')
  return <MediFrontDashboard role={profile.role} profile={profile} userEmail={user.email} />
}
