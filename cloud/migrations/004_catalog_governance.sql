-- ============================================================================
-- Elnagar POS — Migration 004: Catalog governance columns (Smart Excel Catalog)
-- Date: 2026-10-15 (owner order: "نفّذي عملية الاستيراد الآن — تحديث التكاليف
--       وتصنيفات المخزون محليًا وسحابيًا" عبر كتالوج الإكسيل الذكي)
-- Purpose: store the Excel master catalog's smart fields on products:
--   * inventory_type     — تصنيف المخزون: مستمر (تصنيع حسب الطلب) / رصيد بالعدد
--   * manufacturing_cost — تكلفة التشغيل والمصنعية لكل وحدة (EGP)
--   (تكلفة الخامة تتدفق إلى العمود القائم last_cost_price = خام + تشغيل،
--    ليصبح محرك COGS/الربح في financial_engine حقيقيًا)
-- Portability: same dual-engine dialect as 002 — the LOCAL (SQLite) applier in
--   cloud/schema_migrator.py checks pragma and strips "IF NOT EXISTS", so this
--   ONE file runs on BOTH engines via `python cloud/schema_migrator.py --all`.
-- Idempotent: safe to re-run on both engines.
-- ============================================================================

ALTER TABLE products ADD COLUMN IF NOT EXISTS inventory_type TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS manufacturing_cost REAL DEFAULT 0;
