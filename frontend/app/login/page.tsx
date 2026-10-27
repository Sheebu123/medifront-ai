import { AuthLink, AuthShell } from '@/components/auth/auth-shell'
import { LoginForm } from '@/components/auth/login-form'

export default function LoginPage() {
  return <AuthShell eyebrow="Secure access" title="Welcome back" description="Sign in to continue to MediFront AI." footer={<span>Don&apos;t have an account? <AuthLink href="/register">Register</AuthLink></span>}><LoginForm /></AuthShell>
}