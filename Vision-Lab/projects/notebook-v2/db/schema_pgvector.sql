-- =====================================================================
-- Notebook v2 — Proactive Second Brain & Unified Command Center
-- PostgreSQL 15+ (Supabase) + pgvector — مخطط كامل وidempotent
-- التشغيل: python db\migrate.py   (أو الصق الملف في SQL Editor بـ Supabase)
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ------------------------------------------------------------------ settings
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO settings(key, value) VALUES
    ('morning_briefing_at', '"08:00"'::jsonb),
    ('radar_stagnant_days',  '7'::jsonb),
    ('default_provider_id',   'null'::jsonb),
    ('default_model_id',     'null'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- ------------------------------------------------------------- ai_providers
CREATE TABLE IF NOT EXISTS ai_providers (
    id             SERIAL PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    kind           TEXT NOT NULL DEFAULT 'openai-compatible',
    base_url       TEXT NOT NULL,
    api_key_enc    TEXT NOT NULL,
    active         BOOLEAN NOT NULL DEFAULT TRUE,
    notes          TEXT,
    last_check_at  TIMESTAMPTZ,
    last_check_ok  BOOLEAN,
    last_check_msg TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_models (
    id            SERIAL PRIMARY KEY,
    provider_id   INTEGER NOT NULL REFERENCES ai_providers(id) ON DELETE CASCADE,
    model_id      TEXT NOT NULL,
    label         TEXT,
    capabilities  JSONB NOT NULL DEFAULT '{}'::jsonb,
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, model_id)
);

-- --------------------------------------------------------------- the vault
CREATE TABLE IF NOT EXISTS vault_prompts (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'عام',
    tags         TEXT[] NOT NULL DEFAULT '{}',
    source       TEXT NOT NULL DEFAULT 'manual',
    embedding    vector(1536),
    embed_model  TEXT,
    use_count    INTEGER NOT NULL DEFAULT 0,
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vault_embedding
    ON vault_prompts USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_vault_trgm_title
    ON vault_prompts USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_vault_trgm_body
    ON vault_prompts USING gin (body gin_trgm_ops);

-- ---------------------------------------------------------------- captures
CREATE TABLE IF NOT EXISTS captures (
    id                 SERIAL PRIMARY KEY,
    kind               TEXT NOT NULL DEFAULT 'note'
                       CHECK (kind IN ('note','task','idea','reminder','program_idea','home_item','workshop_need')),
    title              TEXT NOT NULL DEFAULT '',
    body               TEXT NOT NULL DEFAULT '',
    category           TEXT,
    priority           TEXT NOT NULL DEFAULT 'normal'
                       CHECK (priority IN ('low','normal','high','urgent')),
    status             TEXT NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open','done','archived')),
    due_at             TIMESTAMPTZ,
    remind_at          TIMESTAMptz,
    remind_every       TEXT NOT NULL DEFAULT 'none'
                       CHECK (remind_every IN ('none','daily','weekly','monthly')),
    source             TEXT NOT NULL DEFAULT 'ui',
    tags               TEXT[] NOT NULL DEFAULT '{}',
    confidence         REAL NOT NULL DEFAULT 0,
    routed_by          TEXT NOT NULL DEFAULT 'rules',
    needs_clarification BOOLEAN NOT NULL DEFAULT FALSE,
    question           TEXT,
    meta               JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    done_at            TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_captures_status ON captures(status);
CREATE INDEX IF NOT EXISTS idx_captures_kind   ON captures(kind);
CREATE INDEX IF NOT EXISTS idx_captures_due    ON captures(due_at);
CREATE INDEX IF NOT EXISTS idx_captures_remind ON captures(remind_at);
CREATE INDEX IF NOT EXISTS idx_captures_tags   ON captures USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_captures_trgm_title ON captures USING gin (title gin_trgm_ops);

CREATE TABLE IF NOT EXISTS capture_events (
    id         SERIAL PRIMARY KEY,
    capture_id INTEGER REFERENCES captures(id) ON DELETE CASCADE,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    type       TEXT NOT NULL,
    detail     TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_capture_events_capture ON capture_events(capture_id);

-- --------------------------------------------------------------- projects
CREATE TABLE IF NOT EXISTS projects (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL UNIQUE,
    area                TEXT NOT NULL DEFAULT 'personal'
                        CHECK (area IN ('retail','workshop','personal','software','other')),
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','paused','done','archived')),
    goal                TEXT,
    notes               TEXT,
    stagnant_after_days INTEGER NOT NULL DEFAULT 7,
    last_activity_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_log (
    id         SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    type       TEXT NOT NULL,
    detail     TEXT DEFAULT ''
);

-- -------------------------------------------------------------- home lists
CREATE TABLE IF NOT EXISTS home_lists (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS home_items (
    id         SERIAL PRIMARY KEY,
    list_id    INTEGER NOT NULL REFERENCES home_lists(id) ON DELETE CASCADE,
    item_text  TEXT NOT NULL,
    qty        TEXT,
    done       BOOLEAN NOT NULL DEFAULT FALSE,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    done_at    TIMESTAMPTZ,
    capture_id INTEGER REFERENCES captures(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_home_items_list ON home_items(list_id);

-- =================== Elnagar Print Workshop (bounded context) =============
-- موديول مستقل تمامًا: بادئة ws_ ولا يشارك أي جدول مع الـRetail.
-- ========================================================================

CREATE TABLE IF NOT EXISTS ws_customers (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    phone      TEXT,
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ws_customers_phone
    ON ws_customers(phone) WHERE phone IS NOT NULL AND phone <> '';

CREATE TABLE IF NOT EXISTS ws_jobs (
    id           SERIAL PRIMARY KEY,
    job_no       TEXT UNIQUE,
    customer_id  INTEGER REFERENCES ws_customers(id) ON DELETE SET NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    status       TEXT NOT NULL DEFAULT 'quote'
                 CHECK (status IN ('quote','confirmed','design','production',
                                   'finishing','ready','delivered','cancelled')),
    machine_type TEXT NOT NULL DEFAULT 'other'
                 CHECK (machine_type IN ('laser','cnc','print','engraving','vinyl','other')),
    qty          NUMERIC(10,2) NOT NULL DEFAULT 1,
    price        NUMERIC(12,2) NOT NULL DEFAULT 0,
    paid         NUMERIC(12,2) NOT NULL DEFAULT 0,
    due_date     DATE,
    priority     TEXT NOT NULL DEFAULT 'normal',
    notes        TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ws_jobs_status ON ws_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ws_jobs_customer ON ws_jobs(customer_id);

CREATE TABLE IF NOT EXISTS ws_job_events (
    id         SERIAL PRIMARY KEY,
    job_id     INTEGER NOT NULL REFERENCES ws_jobs(id) ON DELETE CASCADE,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_status TEXT,
    new_status TEXT,
    detail     TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS ws_materials (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'other'
               CHECK (kind IN ('sheet','filament','paint','ink','paper','vinyl','accessory','other')),
    unit       TEXT NOT NULL DEFAULT 'قطعة',
    qty        NUMERIC(12,3) NOT NULL DEFAULT 0,
    min_qty    NUMERIC(12,3) NOT NULL DEFAULT 0,
    unit_cost  NUMERIC(12,2) NOT NULL DEFAULT 0,
    supplier   TEXT,
    notes      TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ws_job_materials (
    id         SERIAL PRIMARY KEY,
    job_id     INTEGER NOT NULL REFERENCES ws_jobs(id) ON DELETE CASCADE,
    material_id INTEGER NOT NULL REFERENCES ws_materials(id) ON DELETE CASCADE,
    qty        NUMERIC(12,3) NOT NULL,
    unit_cost  NUMERIC(12,2) NOT NULL DEFAULT 0,
    used_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ws_material_logs (
    id          SERIAL PRIMARY KEY,
    material_id INTEGER NOT NULL REFERENCES ws_materials(id) ON DELETE CASCADE,
    job_id      INTEGER REFERENCES ws_jobs(id) ON DELETE SET NULL,
    delta       NUMERIC(12,3) NOT NULL,
    reason      TEXT,
    at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===================== Retail integration (read-side mirror) ==============

CREATE TABLE IF NOT EXISTS retail_snapshots (
    id          SERIAL PRIMARY KEY,
    node_id     TEXT,
    scope       TEXT NOT NULL DEFAULT 'full',
    payload     JSONB NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_retail_snapshots_at ON retail_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS retail_inventory (
    id              SERIAL PRIMARY KEY,
    snapshot_id     INTEGER NOT NULL REFERENCES retail_snapshots(id) ON DELETE CASCADE,
    product_id      INTEGER,
    name            TEXT NOT NULL,
    category        TEXT,
    stock_qty       NUMERIC(12,3),
    price_retail    NUMERIC(12,2),
    price_wholesale NUMERIC(12,2),
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_retail_inventory_snapshot ON retail_inventory(snapshot_id);

CREATE TABLE IF NOT EXISTS agent_reports (
    id          SERIAL PRIMARY KEY,
    agent       TEXT NOT NULL,
    scope       TEXT,
    severity    TEXT NOT NULL DEFAULT 'info'
                CHECK (severity IN ('info','warn','critical')),
    title       TEXT NOT NULL,
    body        TEXT,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    source      TEXT NOT NULL DEFAULT 'api',
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    acked_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_agent_reports_at ON agent_reports(received_at DESC);

CREATE TABLE IF NOT EXISTS sync_log (
    id      SERIAL PRIMARY KEY,
    at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    kind    TEXT NOT NULL,
    ok      BOOLEAN NOT NULL DEFAULT TRUE,
    node_id TEXT,
    detail  TEXT
);

-- ============================ Dual-node HA ================================

CREATE TABLE IF NOT EXISTS nodes (
    node_id     TEXT PRIMARY KEY,
    device_name TEXT,
    role        TEXT,
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at  TIMESTAMPTZ,
    meta        JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS leader_lease (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    holder     TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    acquired_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bot_state (
    bot        TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (bot, key)
);

CREATE TABLE IF NOT EXISTS cron_runs (
    id       SERIAL PRIMARY KEY,
    job      TEXT NOT NULL,
    run_date DATE NOT NULL,
    at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    node_id  TEXT,
    ok       BOOLEAN NOT NULL DEFAULT TRUE,
    detail   TEXT,
    UNIQUE (job, run_date)
);

CREATE TABLE IF NOT EXISTS outbox (
    id          SERIAL PRIMARY KEY,
    chat_id     BIGINT NOT NULL,
    body        TEXT NOT NULL,
    keyboard    JSONB,
    kind        TEXT NOT NULL DEFAULT 'plain',
    dedupe_key  TEXT,
    due_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at     TIMESTAMPTZ,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_outbox_dedupe
    ON outbox(dedupe_key) WHERE dedupe_key IS NOT NULL AND sent_at IS NULL;

CREATE TABLE IF NOT EXISTS pomodoros (
    id         SERIAL PRIMARY KEY,
    label      TEXT,
    minutes    INTEGER NOT NULL DEFAULT 25,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ends_at    TIMESTAMPTZ NOT NULL,
    status     TEXT NOT NULL DEFAULT 'running'
               CHECK (status IN ('running','done','cancelled')),
    node_id    TEXT
);
