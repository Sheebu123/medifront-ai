'use client'

import { useState } from 'react'

import { createClient } from '@/lib/supabase/client'

import { AuthError, AuthField, AuthSubmit } from './auth-field'

export function ResetPasswordForm() {
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setMessage('')
    const formData = new FormData(event.currentTarget)
    const password = String(formData.get('password'))
    if (password.length < 8) { setError('Your password must be at least 8 characters.'); return }
    if (password !== String(formData.get('password_confirmation'))) { setError('The passwords do not match.'); return }
    setLoading(true)
    const { error: updateError } = await createClient().auth.updateUser({ password })
    if (updateError) setError(updateError.message.includes('session') ? 'This reset link is invalid or has expired. Request a new one.' : updateError.message)
    else setMessage('Your password has been updated. You can now sign in with your new password.')
    setLoading(false)
  }

  return <form className="space-y-5" onSubmit={handleSubmit}>
    {error && <AuthError message={error} />}
    {message && <p role="status" className="rounded-lg border border-[#c9ebe5] bg-[#effaf8] px-3 py-2.5 text-sm text-[#137b5b]">{message}</p>}
    <AuthField label="New password" name="password" type="password" placeholder="At least 8 characters" autoComplete="new-password" />
    <AuthField label="Confirm new password" name="password_confirmation" type="password" placeholder="Repeat your password" autoComplete="new-password" />
    <AuthSubmit loading={loading}>Update password</AuthSubmit>
  </form>
}