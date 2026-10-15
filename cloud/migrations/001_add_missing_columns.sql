-- ============================================================================
-- Elnagar POS → Supabase mirror expansion (Level 1, decision 3)
-- Date: 2026-10-13
-- Purpose: make the cloud mirror a byte-level copy of the local schema by adding
-- the columns that are currently missing on Supabase. Run this in:
--   Supabase Dashboard → SQL Editor → New query → paste → Run
-- Idempotent (ADD COLUMN IF NOT EXISTS) so it is safe to re-run.
-- NOTE: the MCP sync keys are REST service-role keys, they CANNOT run DDL.
--       That is why the owner runs this SQL once from the dashboard.
-- ============================================================================

-- clients: phone is the missing column (local TEXT, nullable)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS phone TEXT;

-- products: sort_order and stock are missing (local INTEGER default 0)
ALTER TABLE products ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS stock INTEGER DEFAULT 0;

-- orders: image/file tracking columns are missing
ALTER TABLE orders ADD COLUMN IF NOT EXISTS local_image_path TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS unique_hash TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS source_path TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS synced INTEGER DEFAULT 0;

-- transactions: expense/verification columns are missing
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS "user" TEXT;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS is_verified INTEGER DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS is_savings INTEGER DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS material_cost_recovery REAL DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS net_profit_portion REAL DEFAULT 0;
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS expense_type TEXT DEFAULT 'Business';

-- ============================================================================
-- After this runs, cloud/supabase_sync.py (already introspection-based) will
-- automatically stop shrinking the mirror and carry the full local row.
-- Verify afterwards with:  python cloud\supabase_sync.py --push-once
-- ============================================================================
