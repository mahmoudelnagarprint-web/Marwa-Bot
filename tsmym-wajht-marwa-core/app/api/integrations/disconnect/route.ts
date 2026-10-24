// app/api/integrations/disconnect/route.ts — فصل مزود (حذف رموزه من الخزنة المشفرة)
// MARWA CORE task-6: POST { provider } — بلا رموز في الرد ولا في الطلب.
import { NextRequest, NextResponse } from 'next/server'
import { clearTokens, getStatus } from '@/lib/tools/tokens'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { provider?: string }
    const provider = body.provider ?? ''
    if (provider !== 'google' && provider !== 'canva') {
      return NextResponse.json({ success: false, error: 'مزود غير مدعوم' }, { status: 400 })
    }
    clearTokens(provider)
    return NextResponse.json({ success: true, status: getStatus(provider) })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg }, { status: 500 })
  }
}
