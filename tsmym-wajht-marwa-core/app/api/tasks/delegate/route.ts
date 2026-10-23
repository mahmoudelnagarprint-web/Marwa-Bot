import { NextRequest, NextResponse } from 'next/server'
import { createDirectTask } from '@/lib/direct-task'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  let body: { text?: unknown }
  try {
    body = await req.json() as { text?: unknown }
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح.' }, { status: 400 })
  }
  if (typeof body.text !== 'string' || body.text.length > 2200) {
    return NextResponse.json({ ok: false, message: 'نص المهمة غير صالح أو أطول من المسموح.' }, { status: 400 })
  }
  const result = await createDirectTask(body.text)
  return NextResponse.json(result, { status: result.ok ? 200 : 422, headers: { 'Cache-Control': 'no-store' } })
}
