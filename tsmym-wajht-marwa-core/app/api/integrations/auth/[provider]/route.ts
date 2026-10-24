// app/api/integrations/auth/[provider]/route.ts — بدء موجة OAuth (Google / Canva)
// MARWA CORE task-6: يبني رابط موافقة المالك:
//   Google: OAuth 2.0 + access_type=offline (نحصل على refresh_token) + state ضد CSRF
//   Canva:  OAuth 2.0 + PKCE (code_verifier يُخزن في كوكي HttpOnly قصير العمر)
// المالك يوافق مرة واحدة → الكولباك يستبدل الكود برموز تُحفظ مشفرة في خزنة السيرفر.

import { NextRequest, NextResponse } from 'next/server'
import crypto from 'crypto'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const GOOGLE_SCOPES = [
  'https://www.googleapis.com/auth/spreadsheets',
  'https://www.googleapis.com/auth/calendar',
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/documents',
].join(' ')

const CANVA_SCOPES = ['design:content:write', 'design:content:read', 'asset:write'].join(' ')

function baseUrl(req: NextRequest): string {
  // لو الواجهة مفتوحة من الموبايل على الشبكة — الكولباك يعود لنفس الأصل
  return process.env.INTEGRATIONS_BASE_URL || `${req.nextUrl.protocol}//${req.nextUrl.host}`
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ provider: string }> }) {
  const { provider } = await ctx.params
  const state = crypto.randomBytes(16).toString('base64url')
  const origin = baseUrl(req)

  try {
    if (provider === 'google') {
      const clientId = process.env.GOOGLE_CLIENT_ID
      if (!clientId) {
        return NextResponse.json(
          { success: false, error: 'GOOGLE_CLIENT_ID غير مضبوط — راجع INTEGRATIONS_SETUP.md القسم 1' },
          { status: 500 },
        )
      }
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: `${origin}/api/integrations/callback/google`,
        response_type: 'code',
        scope: GOOGLE_SCOPES,
        access_type: 'offline', // ← للحصول على refresh_token (عمل خلفي بلا تدخل)
        prompt: 'consent', // ← يضمن إعادة refresh_token في كل موافقة
        include_granted_scopes: 'true',
        state,
      })
      const res = NextResponse.redirect(`https://accounts.google.com/o/oauth2/v2/auth?${params}`)
      res.cookies.set('oauth_state', state, { httpOnly: true, maxAge: 600, sameSite: 'lax', path: '/' })
      return res
    }

    if (provider === 'canva') {
      const clientId = process.env.CANVA_CLIENT_ID
      if (!clientId) {
        return NextResponse.json(
          { success: false, error: 'CANVA_CLIENT_ID غير مضبوط — راجع INTEGRATIONS_SETUP.md القسم 2' },
          { status: 500 },
        )
      }
      // PKCE: code_verifier عشوائي → code_challenge بـ SHA256/base64url
      const verifier = crypto.randomBytes(48).toString('base64url')
      const challenge = crypto.createHash('sha256').update(verifier).digest('base64url')
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: `${origin}/api/integrations/callback/canva`,
        response_type: 'code',
        scope: CANVA_SCOPES,
        code_challenge: challenge,
        code_challenge_method: 'S256',
        state,
      })
      const res = NextResponse.redirect(`https://www.canva.com/api/oauth/authorize?${params}`)
      res.cookies.set('oauth_state', state, { httpOnly: true, maxAge: 600, sameSite: 'lax', path: '/' })
      res.cookies.set('pkce_verifier', verifier, { httpOnly: true, maxAge: 600, sameSite: 'lax', path: '/' })
      return res
    }

    return NextResponse.json({ success: false, error: `مزود غير مدعوم: ${provider}` }, { status: 404 })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg }, { status: 500 })
  }
}
