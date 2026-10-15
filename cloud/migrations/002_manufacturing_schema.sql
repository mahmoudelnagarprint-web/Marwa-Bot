-- ============================================================================
-- Elnagar POS — Migration 002: Manufacturing schema (Phase 6)
-- Date: 2026-10-14 (owner order: "تفعيل المرحلة 6 وإدارة الخامات وهندسة التكاليف")
-- Purpose: link products to materials + operation routes + engineering costs.
-- Portability: written in the common SQLite/Postgres dialect subset
--   * explicit TEXT / INTEGER / REAL primary keys (no AUTOINCREMENT/SERIAL)
--   * CREATE TABLE IF NOT EXISTS (valid in both engines)
--   * ALTER TABLE ... ADD COLUMN IF NOT EXISTS is Postgres syntax; the LOCAL
--     (SQLite) applier in cloud/schema_migrator.py checks pragma first and
--     strips "IF NOT EXISTS" — so this ONE file runs on BOTH engines via
--     `python cloud/schema_migrator.py --all`.
-- Idempotent: safe to re-run on both engines.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1) raw_materials: مواصفات الخامات — الألواح (خشب/أكريليك) والخامات الجاهزة
--    code: معرف نصي ثابت (مثال: mdf_3mm_60x40 / acrylic_3mm_60x40 / mug_11oz)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_materials (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL DEFAULT 'sheet',      -- sheet (لوح) | ready (خامة جاهزة)
    material_kind   TEXT NOT NULL DEFAULT 'wood',       -- wood | acrylic | mdf | paper | film | ready
    width_cm        REAL DEFAULT 0,
    height_cm       REAL DEFAULT 0,
    sheet_price     REAL DEFAULT 0,
    price_per_cm2   REAL DEFAULT 0,                     -- محسوب = sheet_price / (width*height)
    unit            TEXT DEFAULT 'sheet',
    supplier        TEXT,
    notes           TEXT
);

-- ---------------------------------------------------------------------------
-- 2) product_recipes: وصفة كل منتج — الخامة + مسار التشغيل + الأبعاد + الهالك
--    product_id = PK (صفة واحدة لكل منتج — مرجع مباشر لجدول products)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_recipes (
    product_id        INTEGER PRIMARY KEY REFERENCES products(id),
    material_code     TEXT,                             -- -> raw_materials.code
    operation_type    TEXT,                             -- laser | sublimation | framing | engraving | composite
    length_cm         REAL DEFAULT 0,
    width_cm          REAL DEFAULT 0,
    waste_pct         REAL DEFAULT 5.0,                -- نسبة الهالك %
    machine_time_min  REAL DEFAULT 0,                  -- وقت تشغيل الماكينة (دقائق)
    extra_parts       TEXT,                            -- مكونات مركبة (نص منظم: خشب+فوتو+سلوفان ...)
    notes             TEXT
);

-- ---------------------------------------------------------------------------
-- 3) products: عمودا التصنيف الآلي (Auto-Tagging Engine — data_healer)
-- ---------------------------------------------------------------------------
ALTER TABLE products ADD COLUMN IF NOT EXISTS material_type TEXT;   -- wood | acrylic | sublimation | engraving_ready | composite | unknown
ALTER TABLE products ADD COLUMN IF NOT EXISTS operation_type TEXT;  -- laser | sublimation | framing | engraving | composite | unknown

-- ============================================================================
-- After this migration:
--   * cloud/schema_migrator.py --all  applies it to LOCAL (SQLite) + CLOUD (PG)
--   * data_healer auto-tagging fills material_type/operation_type (owner-approved)
--   * manufacturing_agent computes costs from raw_materials + product_recipes
-- ============================================================================
