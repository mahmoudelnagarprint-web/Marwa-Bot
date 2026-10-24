// app/api/integrations/callback/[provider]/route.ts — استبدال الكود برموز وحفظها مشفرة
// MARWA CORE task-6: هذا المسار (سيرفر فقط) يستقبل عودة موافقة المالك:
//   يتحقق من state (CSRF) → يستبدل code برموز الوصول/التحديث → يحفظها في خزنة
//   السيرفر المشفرة (.integrations/tokens.enc — بلا مرور بالواجهة) → يعيد المالك
//   لصفحة الإعدادات بعلامة نجاح. التوكنات لا تلمس المتصفح إطلاقاً.

import { NextRequest, NextResponse } from 'next/server'
import { saveTokens } from '@/lib/tools/tokens'
import type { ProviderId, TokenBundle } from '@/lib/tools/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function baseUrl(req: NextRequest): string {
  return process.env.INTEGRATIONS_BASE_URL || `${req.nextUrl.protocol}//${req.nextUrl.host}`
}

function backWith(origin: string, ok: boolean, msg: string): NextResponse {
  return NextResponse.redirect(`${origin}/?integrations=${ok ? 'connected' : 'failed'}&msg=${encodeURIComponent(msg)}`)
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params
  const origin = baseUrl(req)
  const sp = req.nextUrl.searchParams
  const code = sp.get('code')
  const state = sp.get('state')
  const cookieState = req.cookies.get('oauth_state')?.value

  if (provider !== 'google' && provider !== 'canva') {
    return backWith(origin, false, `مزود غير مدعوم: ${provider}`)
  }
  if (!code || !state || !cookieState || state !== cookieState) {
    return backWith(origin, false, 'فشل التحقق الأمني (state) — أعد المحاولة من الإعدادات')
  }

  const t0 = Date.now()
  try {
    const tokens = (await exchange(provider as ProviderId, code, req, origin)) as TokenBundle
    saveTokens(provider as ProviderId, tokens)
    console.log(`[integrations] ${provider} متصل — حفظ مشفر تم في ${Date.now() - t0}ms`)
    const res = backWith(origin, true, `${provider} متصل بنجاح`)
    res.cookies.delete('oauth_state')
    res.cookies.delete('pkce_verifier')
    return res
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    console.error('[integrations] فشل تبادل الرموز:', msg)
    return backWith(origin, false, `فشل ربط ${provider}: ${msg}`)
  }
}

async function exchange(
  provider: ProviderId,
  code: string,
  req: NextRequest,
  origin: string,
): Promise<TokenBundle> {
  if (provider === 'google') {
    const res = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: process.env.GOOGLE_CLIENT_ID ?? '',
        client_secret: process.env.GOOGLE_CLIENT_SECRET ?? '',
        redirect_uri: `${origin}/api/integrations/callback/google`,
        grant_type: 'authorization_code',
      }),
    })
    const json = (await res.json()) as { access_token?: string; refresh_token?: string; expires_in?: number; scope?: string; error?: string }
    if (!res.ok || !json.access_token) throw new Error(`Google: ${json.error ?? res.status}`)
    return {
      access_token: json.access_token,
      refresh_token: json.refresh_token ?? null,
      expires_at: new Date(Date.now() + (json.expires_in ?? 3600) * 1000).toISOString(),
      scope: json.scope ?? null,
      updated_at: new Date().toISOString(),
    }
  }

  // Canva — PKCE: نرسل code_verifier من الكوكي (بلا client_secret)
  const verifier = req.cookies.get('pkce_verifier')?.value
  const res = await fetch('https://api.canva.com/rest/v1/oauth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      code_verifier: verifier ?? '',
      client_id: process.env.CANVA_CLIENT_ID ?? '',
      redirect_uri: `${origin}/api/integrations/callback/canva`,
    }),
  })
  const json = (await res.json()) as { access_token?: string; refresh_token?: string; expires_in?: number; scope?: string; error_description?: string }
  if (!res.ok || !json.access_token) throw new Error(`Canva: ${json.error_description ?? res.status}`)
  return {
    access_token: json.access_token,
    refresh_token: json.refresh_token ?? null,
    expires_at: new Date(Date.now() + (json.expires_in ?? 3600) * 1000).toISOString(),
    scope: json.scope ?? null,
    updated_at: new Date().toISOString(),
  }
}
