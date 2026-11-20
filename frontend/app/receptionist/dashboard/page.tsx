import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function ReceptionistDashboardPage() {
  const { profile, user } = await requireRole('receptionist')
  return <MediFrontDashboard role={profile.role} profile={profile} userEmail={user.email} />
}