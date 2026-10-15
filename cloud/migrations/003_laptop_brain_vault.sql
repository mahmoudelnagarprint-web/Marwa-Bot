-- 003_laptop_brain_vault.sql — system_brain_sync: the cloud brain vault
-- Owner order 2026-10-14: a cloud key/value table hosting Marwa's engineering brain
-- so the LAPTOP node can pull the full memory (STATUS / decisions / rules / env backup)
-- and push its own learned rules back, keeping both nodes in sync even when the
-- workshop PC is powered off.
--
-- Portable dialect: valid on BOTH engines applied by cloud/schema_migrator.py --all:
--   * LOCAL  (pos_data.db, SQLite)
--   * CLOUD  (Supabase Postgres via POOLER_URL)
--
-- Keys stored by tools/laptop_sync.py:
--   status_md             <- STATUS.md            (system state + latest decisions summary)
--   decisions_log_md      <- memory/decisions_log.md
--   roadmap_md            <- memory/roadmap.md
--   learned_rules         <- RULES.md             (acquired rules)
--   owner_preferences_md  <- memory/owner_preferences.md
--   lessons_md            <- memory/lessons.md
--   agent_charter_md      <- AGENT.md
--   env_backup            <- .env                 (node identity is rewritten on restore)
--   brain_manifest        <- JSON manifest (files, sizes, node, pushed_at)
--
-- NOTE (hardening, applied as a separate cloud-only step because SQLite has no RLS):
--   ALTER TABLE system_brain_sync ENABLE ROW LEVEL SECURITY;
--   with zero policies the vault becomes readable/writable ONLY via the secret key.

CREATE TABLE IF NOT EXISTS system_brain_sync (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
