import Link from 'next/link'
import { Hospital, ShieldCheck } from 'lucide-react'

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  footer,
}: {
  eyebrow: string
  title: string
  description: string
  children: React.ReactNode
  footer: React.ReactNode
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f5f8fa] px-4 py-10 text-[#102a43]">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl border border-[#e5edf3] bg-white shadow-[0_18px_50px_rgba(30,65,90,0.08)] lg:grid-cols-[0.9fr_1.1fr]">
        <section className="hidden bg-[linear-gradient(145deg,#102a43,#1c5273)] p-10 text-white lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="mb-12 flex items-center gap-3">
              <span className="grid size-11 place-items-center rounded-xl bg-[linear-gradient(140deg,#2878d7,#12b2a5)]">
                <Hospital size={23} />
              </span>
              <div>
                <strong className="block font-[Manrope,sans-serif] text-base tracking-wide">MEDIFRONT <span className="text-[#66d4cc]">AI</span></strong>
                <small className="text-[11px] text-[#b9d2df]">Hospital operations</small>
              </div>
            </div>
            <p className="mb-3 text-xs font-bold uppercase tracking-[0.18em] text-[#a6d9df]">Care starts here</p>
            <h2 className="max-w-sm font-[Manrope,sans-serif] text-4xl font-extrabold leading-tight">A calmer front desk for every patient.</h2>
            <p className="mt-5 max-w-sm text-sm leading-6 text-[#c9dce5]">Secure access to the MediFront AI hospital experience, built for patients and care teams.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-[#c9dce5]"><ShieldCheck size={16} className="text-[#66d4cc]" /> Your information is private and secure</div>
        </section>
        <section className="p-6 sm:p-10">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-10 place-items-center rounded-xl bg-[linear-gradient(140deg,#2878d7,#12b2a5)] text-white"><Hospital size={20} /></span>
            <div><strong className="block font-[Manrope,sans-serif] text-sm tracking-wide">MEDIFRONT <span className="text-[#10a7a0]">AI</span></strong><small className="text-[10px] text-[#8292a5]">Hospital operations</small></div>
          </div>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#7c91a4]">{eyebrow}</p>
          <h1 className="font-[Manrope,sans-serif] text-3xl font-extrabold tracking-tight text-[#102a43]">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-[#75889a]">{description}</p>
          <div className="mt-7">{children}</div>
          <div className="mt-7 text-center text-xs text-[#8292a5]">{footer}</div>
        </section>
      </div>
    </main>
  )
}

export function AuthLink({ href, children }: { href: string; children: React.ReactNode }) {
  return <Link className="font-semibold text-[#2878d7] hover:text-[#1f68bf]" href={href}>{children}</Link>
}