import Link from 'next/link'
import { AuthShell } from '@/components/auth/auth-shell'

export default function UnauthorizedPage() {
  return <AuthShell eyebrow="Access restricted" title="You do not have access" description="Your account is authenticated, but it does not have permission to view this area." footer={<Link className="font-semibold text-[#2878d7] hover:text-[#1f68bf]" href="/">Return to MediFront AI</Link>}><div className="rounded-lg border border-[#f4dec0] bg-[#fff8f0] p-4 text-sm leading-6 text-[#8c6b40]">Please contact your hospital administrator if you believe you should have access.</div></AuthShell>
}