import type { User } from '@supabase/supabase-js'

import { LogoutButton } from './logout-button'

export function RoleDashboard({
  dashboardRole,
  currentRole,
  user,
  fullName,
}: {
  dashboardRole: string
  currentRole: string
  user: User
  fullName: string | null
}) {
  const dashboardTitle = dashboardRole.charAt(0).toUpperCase() + dashboardRole.slice(1)
  const currentRoleTitle = currentRole.charAt(0).toUpperCase() + currentRole.slice(1)
  const displayName = fullName || user.user_metadata?.full_name || user.email || 'MediFront user'

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f5f8fa] px-4 py-10 text-[#102a43]">
      <section className="w-full max-w-2xl rounded-2xl border border-[#e5edf3] bg-white p-8 shadow-[0_18px_50px_rgba(30,65,90,0.08)] sm:p-12">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#7c91a4]">MediFront AI</p>
            <h1 className="font-[Manrope,sans-serif] text-3xl font-extrabold tracking-tight">{dashboardTitle} Dashboard</h1>
          </div>
          <LogoutButton />
        </div>
        <div className="mt-10 rounded-xl border border-[#d9eaf2] bg-[#f7fbfd] p-5">
          <p className="text-lg font-bold">You are signed in as a {currentRoleTitle}.</p>
          <p className="mt-2 text-sm text-[#75889a]">{displayName}</p>
          {user.email && <p className="mt-1 text-sm text-[#75889a]">{user.email}</p>}
        </div>
        <p className="mt-6 text-sm leading-6 text-[#8292a5]">Your role-specific MediFront AI workspace will be available here as hospital functionality is added.</p>
      </section>
    </main>
  )
}