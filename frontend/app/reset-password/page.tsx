import { AuthLink, AuthShell } from '@/components/auth/auth-shell'
import { ResetPasswordForm } from '@/components/auth/reset-password-form'

export default function ResetPasswordPage() {
  return <AuthShell eyebrow="Account recovery" title="Choose a new password" description="Create a new password for your MediFront AI account." footer={<span>Need a new reset link? <AuthLink href="/forgot-password">Start again</AuthLink></span>}><ResetPasswordForm /></AuthShell>
}