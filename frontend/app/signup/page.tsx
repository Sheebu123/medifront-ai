import { AuthLink, AuthShell } from '@/components/auth/auth-shell'
import { SignupForm } from '@/components/auth/signup-form'

export default function SignupPage() {
  return <AuthShell eyebrow="Patient registration" title="Create your account" description="Set up secure access to MediFront AI in a few steps." footer={<span>Already have an account? <AuthLink href="/login">Sign in</AuthLink></span>}><SignupForm /></AuthShell>
}