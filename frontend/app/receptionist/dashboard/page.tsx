import MediFrontDashboard from '@/components/medifront-dashboard'
import { requireRole } from '@/lib/auth/server'

export default async function ReceptionistDashboardPage() {
  await requireRole('receptionist')
  return <MediFrontDashboard />
}