// lib/tools/tokens.ts — خزنة رموز OAuth (سيرفر فقط — ممنوع استيرادها من مكونات العميل)
// MARWA CORE task-6 (أمر المالك 2026-10-24): الوكلاء يعملون بالنيابة عن المالك
// دون تدخله — Refresh Tokens تُخزن مشفرة AES-256-GCM وتُحدَّث تلقائياً عند الانتهاء.
//
// 📍 التخزين: ملف محلي gitignored — `.integrations/tokens.enc` بجذر المستودع
//    (اللابتوب هو العامل الخلفي — يقرأ نفس الخزنة مباشرة).
// 🔐 المفتاح: مشتق من INTEGRATIONS_SECRET (بيئة) — يُطلب عند أول ربط حساب.
// 🚧 بديل سحابي (موثق في INTEGRATIONS_SETUP.md): جدول integrations_tokens في
//    Supabase بسياسة RLS تمنع anon تماماً — يُفعَّل عند توفير service-role key للعامل.
// ملاحظة: هذا الملف يعمل في مسارات API السيرفر فقط — لا يُشحن لمتصفح العميل أبداً.

import crypto from 'crypto'
import fs from 'fs'
import path from 'path'
import type { ProviderId, TokenBundle } from './types'

const REPO_ROOT = process.env.ROOT_WORKSPACE || path.resolve(process.cwd(), '..')
const VAULT_DIR = path.join(REPO_ROOT, '.integrations')
const VAULT_FILE = path.join(VAULT_DIR, 'tokens.enc')

const PROVIDER_NAMES: Record<ProviderId, string> = { google: 'google', canva: 'canva' }

function assertProvider(p: string): asserts p is ProviderId {
  if (!(p in PROVIDER_NAMES)) throw new Error(`مزود غير معروف: ${p}`)
}

/** مفتاح التشفير 32 بايت — مشتق من INTEGRATIONS_SECRET (env) */
function deriveKey(): Buffer {
  const secret = process.env.INTEGRATIONS_SECRET
  if (!secret || secret.length < 16) {
    throw new Error(
      'INTEGRATIONS_SECRET غير مضبوط — أضفه إلى .env.local أولاً (راجع INTEGRATIONS_SETUP.md القسم 4)',
    )
  }
  return crypto.scryptSync(secret, 'marwa-integrations-v1', 32)
}

function encrypt(plain: string): string {
  const iv = crypto.randomBytes(12)
  const cipher = crypto.createCipheriv('aes-256-gcm', deriveKey(), iv)
  const enc = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()])
  return [iv.toString('base64'), cipher.getAuthTag().toString('base64'), enc.toString('base64')].join(':')
}

function decrypt(payload: string): string {
  const [ivB64, tagB64, dataB64] = payload.split(':')
  const decipher = crypto.createDecipheriv('aes-256-gcm', deriveKey(), Buffer.from(ivB64, 'base64'))
  decipher.setAuthTag(Buffer.from(tagB64, 'base64'))
  return Buffer.concat([decipher.update(Buffer.from(dataB64, 'base64')), decipher.final()]).toString('utf8')
}

type VaultShape = Partial<Record<ProviderId, TokenBundle>>

function readVault(): VaultShape {
  try {
    const raw = fs.readFileSync(VAULT_FILE, 'utf8')
    return JSON.parse(decrypt(raw)) as VaultShape
  } catch {
    return {} // لا خزنة بعد أو مفتاح مختلف — نبدأ نظيفين
  }
}

function writeVault(v: VaultShape): void {
  fs.mkdirSync(VAULT_DIR, { recursive: true })
  fs.writeFileSync(VAULT_FILE, encrypt(JSON.stringify(v)), { encoding: 'utf8', mode: 0o600 })
}

/** حفظ/تحديث رموز مزود — تُستدعى من مسارات الـcallback (سيرفر) فقط */
export function saveTokens(provider: string, tokens: TokenBundle): void {
  assertProvider(provider)
  const v = readVault()
  v[provider] = tokens
  writeVault(v)
}

/** قراءة الرموز الخام (للمسارات الداخلية فقط) */
export function getTokens(provider: string): TokenBundle | null {
  assertProvider(provider)
  return readVault()[provider] ?? null
}

/** حذف رموز مزود (Disconnect) */
export function clearTokens(provider: string): void {
  assertProvider(provider)
  const v = readVault()
  delete v[provider]
  writeVault(v)
}

export type IntegrationStatus = {
  provider: ProviderId
  connected: boolean
  expires_at: string | null
  /** هل الـaccess token منتهٍ (سيُجدد تلقائياً عند الاستخدام) */
  expired: boolean
  scope: string | null
  updated_at: string | null
}

/** حالة الاتصال — آمنة للواجهة (لا رموز إطلاقاً) */
export function getStatus(provider: string): IntegrationStatus {
  assertProvider(provider)
  const t = readVault()[provider]
  if (!t) {
    return { provider: provider as ProviderId, connected: false, expires_at: null, expired: false, scope: null, updated_at: null }
  }
  const expired = new Date(t.expires_at).getTime() <= Date.now() + 60_000 // هامش دقيقة
  return { provider: provider as ProviderId, connected: true, expires_at: t.expires_at, expired, scope: t.scope, updated_at: t.updated_at }
}

/** تجديد الـaccess token عبر الـrefresh token — لكل مزود نقطة نهايته */
async function refreshBundle(provider: ProviderId, bundle: TokenBundle): Promise<TokenBundle> {
  if (!bundle.refresh_token) throw new Error(`لا يوجد refresh_token لـ${provider} — أعد ربط الحساب`)
  const body = new URLSearchParams({
    grant_type: 'refresh_token',
    refresh_token: bundle.refresh_token,
  })
  if (provider === 'google') {
    body.set('client_id', process.env.GOOGLE_CLIENT_ID ?? '')
    body.set('client_secret', process.env.GOOGLE_CLIENT_SECRET ?? '')
  } else {
    body.set('client_id', process.env.CANVA_CLIENT_ID ?? '')
    body.set('client_secret', process.env.CANVA_CLIENT_SECRET ?? '')
  }
  const tokenUrl =
    provider === 'google' ? 'https://oauth2.googleapis.com/token' : 'https://api.canva.com/rest/v1/oauth/token'
  const res = await fetch(tokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  const json = (await res.json()) as { access_token?: string; refresh_token?: string; expires_in?: number; error?: string }
  if (!res.ok || !json.access_token) {
    throw new Error(`فشل تجديد الرمز (${res.status}): ${json.error ?? 'غير معروف'}`)
  }
  const next: TokenBundle = {
    access_token: json.access_token,
    // جوجل قد لا تعيد refresh_token في التجديد — نحتفظ بالقديم
    refresh_token: json.refresh_token ?? bundle.refresh_token,
    expires_at: new Date(Date.now() + (json.expires_in ?? 3600) * 1000).toISOString(),
    scope: bundle.scope,
    updated_at: new Date().toISOString(),
  }
  saveTokens(provider, next)
  return next
}

/**
 * رمز وصول صالح دائماً — تجديد تلقائي عند الانتهاء (يستدعيه العامل الخلفي/الأدوات).
 * ⚠️ دالة سيرفر فقط — لا تمرر نتيجتها لمكون عميل.
 */
export async function getValidAccessToken(provider: string): Promise<string> {
  assertProvider(provider)
  const bundle = getTokens(provider)
  if (!bundle) throw new Error(`${provider} غير متصل — اربط الحساب من الإعدادات أولاً`)
  const soon = new Date(bundle.expires_at).getTime() <= Date.now() + 120_000 // هامش دقيقتين
  if (!soon) return bundle.access_token
  const next = await refreshBundle(provider as ProviderId, bundle)
  return next.access_token
}
