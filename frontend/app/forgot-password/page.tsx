import { AuthLink, AuthShell } from '@/components/auth/auth-shell'
import { ForgotPasswordForm } from '@/components/auth/forgot-password-form'

export default function ForgotPasswordPage() {
  return <AuthShell eyebrow="Account recovery" title="Reset your password" description="Enter your email and we will send instructions to securely reset your password." footer={<span>Remembered your password? <AuthLink href="/login">Back to sign in</AuthLink></span>}><ForgotPasswordForm /></AuthShell>
}