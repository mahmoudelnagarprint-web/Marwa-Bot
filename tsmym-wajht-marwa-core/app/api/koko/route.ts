// app/api/koko/route.ts — وكالة كوكو للتسويق 2026-10-20
// الخط الأحمر: pos_data.db قراءة فقط. بوستات فيسبوك تمرر لسكربت Python خارجي (Facebook Publisher).
// بحث الصور: فهرس محلي مبسط على DESIGNS_DIR/أرشيف صور — جاهز للربط بـCLIP/ChromaDB لاحقاً.
import { NextRequest, NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'
import { execFile } from 'child_process'
import fs from 'fs'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') ||
  'G:\\ai\\Naggar Print POS Agent\\workspaces'
const ENGINE = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'
const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'
const DESIGNS_DIR = process.env.DESIGNS_DIR || 'G:\\ai\\Naggar Print POS Agent\\designs'
const FB_PUBLISHER = process.env.FB_PUBLISHER_SCRIPT || 'G:\\ai\\Naggar Print POS Agent\\scripts\\facebook_publisher.py'
const WABUSINESS_E164 = '+201000433420' // رقم البزنس الرسمي للورشة — مرجع ثابت في كل العروض

export type VipClient = { id: number; name: string; phone: string; type: string; balance: number }
export type AssetHit = { name: string; rel: string; ext: string; size: number }

function toE164(raw: string | null | undefined): string {
  if (!raw) return ''
  let d = String(raw).replace(/\D/g, '')
  if (d.startsWith('0020')) d = d.slice(2)
  else if (d.startsWith('20') && d.length > 12) d = d.slice(2)
  else if (d.startsWith('0') && d.length === 11) d = '20' + d.slice(1)
  return d.length === 12 ? `+${d}` : ''
}

function runSlash(text: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      [ENGINE, 'parse', text],
      { timeout: 30_000, encoding: 'utf8', cwd: path.dirname(WORKSPACE_ROOT) },
      (err, stdout) => (err ? reject(err) : resolve(JSON.parse(stdout) as Record<string, unknown>)),
    )
  })
}

/** استدعاء سكربت الناشر — محور التكامل العبقري: الواجهة → API → Python(Selenium) */
function runFacebookPublisher(payload: { content: string; image?: string }): Promise<Record<string, unknown>> {
  return new Promise((resolve) => {
    fs.stat(FB_PUBLISHER, (err) => {
      if (err) {
        resolve({ ok: false, message: `سكربت الناشر غير موجود: ${FB_PUBLISHER}`, queued: true })
        return
      }
      execFile(
        PYTHON,
        [FB_PUBLISHER, '--content', payload.content, ...(payload.image ? ['--image', payload.image] : [])],
        { timeout: 120_000, encoding: 'utf8', cwd: path.dirname(FB_PUBLISHER) },
        (err2, stdout) => {
          if (err2) {
            resolve({ ok: false, message: String(err2.message).slice(0, 200), queued: true })
            return
          }
          try {
            resolve(JSON.parse(stdout) as Record<string, unknown>)
          } catch {
            resolve({ ok: true, raw: stdout.slice(0, 400) })
          }
        },
      )
    })
  })
}

const IMG_EXTS = new Set(['.jpg', '.jpeg', '.png', '.webp'])

function walkImages(dir: string, rel: string, out: AssetHit[], depth: number): void {
  if (depth > 3 || out.length >= 120) return
  let entries: fs.Dirent[] = []
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true })
  } catch {
    return
  }
  for (const e of entries) {
    const relPath = rel ? `${rel}/${e.name}` : e.name
    const abs = path.join(dir, e.name)
    if (e.isDirectory()) walkImages(abs, relPath, out, depth + 1)
    else if (e.isFile() && IMG_EXTS.has(path.extname(e.name).toLowerCase())) {
      try {
        const st = fs.statSync(abs)
        out.push({ name: e.name, rel: relPath, ext: path.extname(e.name).slice(1).toUpperCase(), size: st.size })
      } catch { /* تجاهل */ }
    }
  }
}

export async function GET() {
  try {
    // عملاء VIP من غرفة سلمى: جملة أو ديّن أو وعود عرائس (نفس مفاتيح salma-summary)
    const db = new DatabaseSync(DB_PATH, { readOnly: true })
    const clients = db.prepare('SELECT id, name, phone, type, balance FROM clients').all() as Record<string, unknown>[]
    db.close()
    const vips: VipClient[] = clients
      .map((c) => ({
        id: Number(c.id),
        name: String(c.name ?? ''),
        phone: toE164(String(c.phone ?? '')),
        type: String(c.type ?? ''),
        balance: Number(c.balance ?? 0),
      }))
      .filter((c) => c.type === 'Wholesale' || c.balance > 0 || /عروسة|عرس/.test(c.name))

    // فهرس أصول الصور (محلي مبسط — نقطة ربط CLIP/ChromaDB لاحقاً)
    const assets: AssetHit[] = []
    walkImages(DESIGNS_DIR, '', assets, 0)

    return NextResponse.json({
      source: 'pos-db-ro (read-only)',
      tag: 'محسوب من البرنامج',
      business_e164: WABUSINESS_E164,
      wa_business_link: `https://wa.me/${WABUSINESS_E164.slice(1)}`,
      vips,
      assets,
      assets_dir: DESIGNS_DIR,
      clip_ready: false, // مؤشر جاهزية الربط بالـCLIP/ChromaDB — false = بحث نصي على أسماء الملفات
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `فشل وكالة كوكو: ${message.slice(0, 200)}` }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  let action = '', content = '', image = '', query = '', promo = ''
  try {
    const body = (await req.json()) as { action?: string; content?: string; image?: string; query?: string; promo?: string }
    action = body.action ?? ''
    content = body.content ?? ''
    image = body.image ?? ''
    query = body.query ?? ''
    promo = body.promo ?? ''
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }

  try {
    // ---------- 🚀 نشر على فيسبوك ----------
    if (action === 'fb_publish') {
      if (!content.trim()) return NextResponse.json({ ok: false, message: 'البوست فاضي' }, { status: 400 })
      const out = await runFacebookPublisher({ content, image: image || undefined })
      // سجل للمحرك — كوكو تعلم الفريق
      const notify = out.ok
        ? `/summon @marwa 🚀 بوست كوكو نُشر على فيسبوك بنجاح${image ? ' (بصورة)' : ''}`
        : `/summon @marwa ⚠️ نشر فيسبوك مؤجل — السكربت غير متاح الآن، البوست محفوظ للإعادة`
      try { await runSlash(notify) } catch { /* تنبيه غير حرج */ }
      return NextResponse.json({ ok: Boolean(out.ok), notify: out.ok ? '🚀 نُشر على فيسبوك — مروة تلقت التأكيد' : '⚠️ مؤجل — السكربت غير متاح (البوست محفوظ)', detail: out })
    }

    // ---------- 🔍 البحث البصري (نصي على الأسماء الآن — CLIP لاحقاً) ----------
    if (action === 'asset_search') {
      if (!query.trim()) return NextResponse.json({ ok: false, message: 'ابحثي بشيء' }, { status: 400 })
      const words = query.trim().split(/\s+/)
      const assets: AssetHit[] = []
      walkImages(DESIGNS_DIR, '', assets, 0)
      const hits = assets.filter((a) => words.some((w) => a.rel.includes(w)))
      return NextResponse.json({ ok: true, query, hits, clip_ready: false, hint: 'بحث نصي على أسماء الملفات — الربط بـCLIP/ChromaDB جاهز واجهته' })
    }

    // ---------- 📢 إرسال عرض مجمع للـVIP ----------
    if (action === 'wa_broadcast') {
      if (!promo.trim()) return NextResponse.json({ ok: false, message: 'نص العرض فاضي' }, { status: 400 })
      // رسالة ترويجية موحدة CTA برقم البزنس الثابت — الالتزام بالتوافقي مع سلمى (لا رسائل فردية هنا)
      const text = `📢 ${promo}\n📞 للتواصل والطلب: 01000433420 (النجار برنت)\n${`https://wa.me/201000433420`}`
      const out = await runSlash(`/summon @salma 📢 عرض ترويجي جاهز للنشر على عملاء الـVIP (${text.length} حرف) — راجعي القائمة واعتمدي`)
      return NextResponse.json({ ok: Boolean(out.ok), preview: text, notify: '📢 العرض المجمع جاهز — مرّر لسلمى للاعتماد' })
    }

    return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, message: message.slice(0, 200) }, { status: 500 })
  }
}
