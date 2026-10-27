'use client'

import { useState } from 'react'

import { createClient } from '@/lib/supabase/client'

import { AuthError, AuthField, AuthSubmit } from './auth-field'

export function SignupForm() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setMessage('')
    const formData = new FormData(event.currentTarget)
    const password = String(formData.get('password'))
    const confirmation = String(formData.get('password_confirmation'))
    if (password.length < 8) { setError('Your password must be at least 8 characters.'); return }
    if (password !== confirmation) { setError('The passwords do not match.'); return }
    setLoading(true)
    const supabase = createClient()
    const { data, error: signUpError } = await supabase.auth.signUp({
      email: String(formData.get('email')).trim(),
      password,
      options: {
        data: {
          full_name: String(formData.get('full_name')).trim(),
          phone: String(formData.get('phone')).trim(),
        },
      },
    })

    if (signUpError) {
      setError(signUpError.message.toLowerCase().includes('already') ? 'An account with this email may already exist. Try signing in.' : signUpError.message)
      setLoading(false)
      return
    }

    if (data.session) {
      window.location.assign('/')
      return
    }
    setMessage('Check your email to confirm your account, then return to sign in.')
    setLoading(false)
  }

  return <form className="space-y-4" onSubmit={handleSubmit} noValidate>
    {error && <AuthError message={error} />}
    {message && <p role="status" className="rounded-lg border border-[#c9ebe5] bg-[#effaf8] px-3 py-2.5 text-sm text-[#137b5b]">{message}</p>}
    <AuthField label="Full name" name="full_name" placeholder="Your full name" autoComplete="name" />
    <AuthField label="Email address" name="email" type="email" placeholder="you@example.com" autoComplete="email" />
    <AuthField label="Phone number" name="phone" type="tel" placeholder="Optional" autoComplete="tel" required={false} />
    <AuthField label="Password" name="password" type="password" placeholder="At least 8 characters" autoComplete="new-password" />
    <AuthField label="Confirm password" name="password_confirmation" type="password" placeholder="Repeat your password" autoComplete="new-password" />
    <p className="text-xs leading-5 text-[#8292a5]">New public accounts are registered as patients automatically.</p>
    <AuthSubmit loading={loading}>Create account</AuthSubmit>
  </form>
}