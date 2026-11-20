import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function AdminDashboardPage() {
  const { profile, user } = await requireRole('admin')
  return <MediFrontDashboard role={profile.role} profile={profile} userEmail={user.email} />
}