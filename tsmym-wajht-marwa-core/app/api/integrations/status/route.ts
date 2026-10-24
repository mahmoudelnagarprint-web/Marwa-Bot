// app/api/integrations/status/route.ts — حالة التكاملات (آمنة للواجهة — بلا رموز إطلاقاً)
// MARWA CORE task-6: يقرأgetStatus من خزنة السيرفر — الواجهة تعرض متصل/غير متصل فقط.
import { NextResponse } from 'next/server'
import { getStatus } from '@/lib/tools/tokens'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET() {
  try {
    return NextResponse.json(
      {
        success: true,
        integrations: [getStatus('google'), getStatus('canva')],
        /** توجيه للمالك: أضف INTEGRATIONS_SECRET ومفاتيح المزودين في .env.local أولاً */
        envReady: {
          google: Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET),
          canva: Boolean(process.env.CANVA_CLIENT_ID && process.env.CANVA_CLIENT_SECRET),
          secret: Boolean(process.env.INTEGRATIONS_SECRET),
        },
      },
      { headers: { 'Cache-Control': 'no-store' } },
    )
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg }, { status: 500 })
  }
}
