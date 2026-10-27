import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'MediFront AI | Hospital Front Desk Operations',
  description: 'Intelligent hospital reception, patient assistance, appointments and queue operations for MediCare City Hospital.',
}

export const viewport: Viewport = {
  colorScheme: 'light',
  themeColor: '#f5f8fa',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className="antialiased">{children}{process.env.NODE_ENV === 'production' && <Analytics />}</body></html>
}
