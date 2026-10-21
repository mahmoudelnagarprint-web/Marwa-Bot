// app/api/afkar/route.ts — معمل الابتكار: غرفة أفكار (Notes/Ideas/Season Radar)
// بأمر المالك 2026-10-21 (المايسترو مروة): حاضنة رسمية لواجهة النوت بوك المبنية
// سابقاً — حصر ودمج لا إعادة بناء. المحرك هو workspaces/afkar_ideas/engine/afkar_engine.py
// (مخزن ملف واحد في active_workspaces بصيغة موثقة) وأوامر التحويل تمر من نفس
// محرك التوجيه router_daemon.py — لا منطق مزدوج، لا أسرار في الكود.
import { NextRequest, NextResponse } from 'next/server'
import { execFile } from 'child_process'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') ||
  'G:\\ai\\Naggar Print POS Agent\\workspaces'
const AFKAR_DIR = path.join(WORKSPACE_ROOT, 'afkar_ideas')
const ENGINE = path.join(AFKAR_DIR, 'engine', 'afkar_engine.py')
const ROUTER = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'

type EngineResult = { ok: boolean; data?: unknown; error?: string }

/**
 * ملاحظة معمارية (درس ويندوز): كل أمر للمحرك يمر كوسيط مستقل عبر execFile —
 * دمج «mutate» مع حمولة JSON في سلسلة واحدة يجعل المحلل يراها اسماً واحداً
 * فيرد «أمر غير معروف». لذلك args مصفوفة: ['mutate', '{"action":...}'].
 */
function runEngine(args: string[]): Promise<EngineResult> {
  return new Promise((resolve) => {
    execFile(
      PYTHON,
      ['-X', 'utf8', ENGINE, ...args],
      // نفس عرف /api/slash تماماً: cwd على الجذر بلا مسافات — execFile بدون
      // shell يفصل الوسائط بمسافات فيتعثر على مسار يحمل مسافات (Naggar Print POS).
      { timeout: 30_000, encoding: 'utf8', cwd: path.dirname(WORKSPACE_ROOT) },
      (err, stdout, stderr) => {
        if (err) {
          // الأسباب الحقيقية (مسار فيه مسافات، تعثر الوسائط) تظهر في stderr
          const detail = String(stderr || '').trim()
          resolve({ ok: false, error: `${String(err.message).slice(0, 160)} :: ${detail.slice(0, 500)}` })
          return
        }
        try {
          const parsed = JSON.parse(stdout) as EngineResult
          resolve(parsed)
        } catch (e) {
          resolve({ ok: false, error: `المحرك أعاد نصاً غير صالح: ${String(e).slice(0, 120)}` })
        }
      },
    )
  })
}

/**
 * ملاحظة معمارية (درس ويندوز): كل أمر للمحرك يمر كوسيط مستقل عبر execFile —
 * دمج «mutate» مع حمولة JSON في سلسلة واحدة يجعل المحلل يراها اسماً واحداً
 * فيرد «أمر غير معروف». لذلك args مصفوفة: ['mutate', '{"action":...}'].
 */

function runRouter(text: string): Promise<{ ok: boolean; message?: string; file?: string; push?: string }> {
  return new Promise((resolve) => {
    execFile(
      PYTHON,
      ['-X', 'utf8', ROUTER, 'parse', text],
      { timeout: 30_000, encoding: 'utf8', cwd: path.dirname(WORKSPACE_ROOT) },
      (err, stdout) => {
        if (err) {
          resolve({ ok: false, message: err.message.slice(0, 200) })
          return
        }
        try {
          resolve(JSON.parse(stdout) as { ok: boolean; message?: string; file?: string; push?: string })
        } catch {
          resolve({ ok: false, message: 'المحرك أعاد نصاً غير صالح' })
        }
      },
    )
  })
}

export async function GET() {
  const res = await runEngine(['dashboard'])
  // المحرك يرجع {ok, stats, by_category, ...} كحمولة نهائية — نمررها كاملة
  return NextResponse.json(res)
}

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>
  try {
    body = (await req.json()) as Record<string, unknown>
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const action = String(body.action ?? '')

  // تحويل الفكرة لمشروع: أوامر متوازية إلى بيبو/حكيم/كوكو عبر محرك التوجيه
  if (action === 'convert_idea') {
    const id = Number(body.id)
    const title = String(body.title ?? '').trim()
    if (!id || !title) {
      return NextResponse.json({ ok: false, message: 'الفكرة غير محددة' }, { status: 400 })
    }
    const slug = title.slice(0, 60).replace(/\s+/g, ' ')
    const commands = [
      `/task @bebo الفكرة «${slug}» — جهّز المقاسات وملف DXF تجريبي للمنتج — من معمل أفكار`,
      `/task @hakim الفكرة «${slug}» — احسب التكلفة وسعّر المنتج الجديد — من معمل أفكار`,
      `/task @koko الفكرة «${slug}» — جهّز حملة تسويقية وبوست تشويقي — من معمل أفكار`,
    ]
    // متوازية حقيقية: الثلاثة يُطلقون في نفس اللحظة (لا تسلسل)
    const results = await Promise.all(commands.map((text) => runRouter(text)))
    const dispatched = results.filter((r) => r.ok).length
    const rec = await runEngine(['spawn', String(id), JSON.stringify(commands)])
    return NextResponse.json({
      ok: dispatched > 0,
      dispatched,
      total: commands.length,
      commands,
      results: results.map((r) => ({ ok: r.ok, message: r.message })),
      recorded: rec.ok,
    })
  }
  const script = JSON.stringify({
    action,
    id: body.id !== undefined ? Number(body.id) : undefined,
    title: typeof body.title === 'string' ? body.title : undefined,
    body: typeof body.body === 'string' ? body.body : undefined,
    category: typeof body.category === 'string' ? body.category : undefined,
    tags: Array.isArray(body.tags) ? (body.tags as unknown[]).map(String) : undefined,
    project: typeof body.project === 'string' ? body.project : undefined,
  })
  const res = await runEngine(['mutate', script])
  if (!res.ok) {
    return NextResponse.json({ ok: false, message: res.error }, { status: 500 })
  }
  // المحرك يرجع {ok, note} — نمرر الحمولة كما هي لتحيا الواجهة بشكل موحد
  return NextResponse.json(res)
}

// ملاحظة معمارية: كل أمر للمحرك يمر كوسيط مستقل عبر execFile (['mutate', json])
// — دمج الاسم مع الحمولة في سلسلة واحدة يجعل المحلل يراها اسماً واحداً فيرد
// «أمر غير معروف». الحمولة نفسها وسيط واحد فالمسافات داخله آمنة.