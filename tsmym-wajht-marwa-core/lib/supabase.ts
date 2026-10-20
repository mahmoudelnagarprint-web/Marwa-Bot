// lib/supabase.ts — عميل Supabase للواجهة (MARWA CORE task-2)
// المفاتيح تُقرأ فقط من .env.local (متجاهل من Git) — لا قيم داخل الكود أبداً.
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = process.env.NEXT_PUBLIC_SUPABASE_URL
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

/** هل الإعدادات السحابية جاهزة؟ (تُقرأ من .env.local وقت البناء) */
export const supabaseConfigured = Boolean(url && anonKey)

/**
 * عميل anon-key للواجهة. null عندما يكون .env.local غير مهيأ —
 * اللوحة تعرض حالة «غير مهيأ» بدل الانهيار.
 */
export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url as string, anonKey as string, {
      realtime: { params: { eventsPerSecond: 5 } },
    })
  : null
