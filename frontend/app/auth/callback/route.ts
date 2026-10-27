import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

import { createClient } from '@/lib/supabase/server'

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get('code')
  const next = request.nextUrl.searchParams.get('next')
  const destination = next === '/reset-password' ? '/reset-password' : '/'

  if (!code) {
    return NextResponse.redirect(new URL('/login?error=auth_callback_failed', request.url))
  }

  const supabase = await createClient()
  const { error } = await supabase.auth.exchangeCodeForSession(code)

  if (error) {
    return NextResponse.redirect(new URL('/login?error=auth_callback_failed', request.url))
  }

  return NextResponse.redirect(new URL(destination, request.url))
}