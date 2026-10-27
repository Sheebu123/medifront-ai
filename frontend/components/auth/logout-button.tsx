'use client'

import { useState } from 'react'

import { createClient } from '@/lib/supabase/client'

export function LogoutButton() {
  const [loading, setLoading] = useState(false)

  async function handleLogout() {
    setLoading(true)
    await createClient().auth.signOut()
    window.location.assign('/login')
  }

  return <button className="rounded-lg border border-[#dbe6ed] px-3 py-2 text-sm font-semibold text-[#52687c] transition hover:border-[#2878d7] hover:text-[#2878d7] disabled:opacity-60" onClick={handleLogout} disabled={loading}>{loading ? 'Signing out...' : 'Sign out'}</button>
}