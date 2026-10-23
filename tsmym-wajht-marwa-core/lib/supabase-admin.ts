import 'server-only'

import { createClient } from '@supabase/supabase-js'

/** Privileged client: server only; never add NEXT_PUBLIC_ to the service key. */
export function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SECRET_KEY
  if (!url || !key) throw new Error('Supabase server credentials are not configured')
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  })
}
