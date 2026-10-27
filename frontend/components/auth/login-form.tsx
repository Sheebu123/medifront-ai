'use client'

import Link from 'next/link'
import { useState } from 'react'

import { createClient } from '@/lib/supabase/client'

import { AuthError, AuthField, AuthSubmit } from './auth-field'

export function LoginForm() {
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setLoading(true)
    const formData = new FormData(event.currentTarget)
    const supabase = createClient()
    const { error: signInError } = await supabase.auth.signInWithPassword({
      email: String(formData.get('email')).trim(),
      password: String(formData.get('password')),
    })

    if (signInError) {
      setError(signInError.message === 'Invalid login credentials' ? 'The email or password is incorrect.' : signInError.message)
      setLoading(false)
      return
    }

    window.location.assign('/')
  }

  return <form className="space-y-5" onSubmit={handleSubmit}>
    {error && <AuthError message={error} />}
    <AuthField label="Email address" name="email" type="email" placeholder="you@example.com" autoComplete="email" />
    <div>
      <div className="mb-2 flex items-center justify-between"><label className="text-sm font-semibold text-[#52687c]" htmlFor="login-password">Password</label><Link className="text-xs font-semibold text-[#2878d7] hover:text-[#1f68bf]" href="/forgot-password">Forgot password?</Link></div>
      <input id="login-password" className="block h-11 w-full rounded-lg border border-[#dbe6ed] bg-white px-3 text-sm text-[#102a43] outline-none transition focus:border-[#2878d7] focus:ring-4 focus:ring-[#2878d7]/10" name="password" type="password" placeholder="Enter your password" autoComplete="current-password" required />
    </div>
    <AuthSubmit loading={loading}>Sign in</AuthSubmit>
  </form>
}