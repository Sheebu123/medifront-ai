import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function AdminDashboardPage() {
  await requireRole('admin')
  return <MediFrontDashboard />
}