import { getCurrentProfile, getCurrentUser } from "@/lib/auth/server"
import { redirect } from "next/navigation"

export default async function Page() {
  const user = await getCurrentUser()
  if (!user) redirect('/login')

  const profile = await getCurrentProfile()
  if (!profile) redirect('/unauthorized')

  redirect(`/${profile.role}/dashboard`)
}
