'use client'

import { useState } from 'react'

import { createClient } from '@/lib/supabase/client'

import { AuthError, AuthField, AuthSubmit } from './auth-field'

export function ForgotPasswordForm() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    const email = String(new FormData(event.currentTarget).get('email')).trim()
    const supabase = createClient()
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/auth/callback?next=/reset-password` })
    if (resetError) setError(resetError.message)
    else setMessage('If an account is associated with that email, you will receive a password reset link shortly.')
    setLoading(false)
  }

  return <form className="space-y-5" onSubmit={handleSubmit}>
    {error && <AuthError message={error} />}
    {message && <p role="status" className="rounded-lg border border-[#c9ebe5] bg-[#effaf8] px-3 py-2.5 text-sm text-[#137b5b]">{message}</p>}
    <AuthField label="Email address" name="email" type="email" placeholder="you@example.com" autoComplete="email" />
    <AuthSubmit loading={loading}>Send reset link</AuthSubmit>
  </form>
}