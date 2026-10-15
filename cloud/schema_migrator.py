# -*- coding: utf-8 -*-
"""Elnagar POS — Autonomous Schema Migrator (dual-engine: LOCAL SQLite + CLOUD Postgres)
======================================================================================
Granted by the owner (2026-10-14): permanent direct Postgres access stored in .env
(DIRECT_URL + POOLER_URL) so migrations run autonomously — no manual dashboard step
ever again. Phase 6 (2026-10-14): --all now applies each migration to BOTH engines:

  * LOCAL  (pos_data.db, SQLite) — statements filtered/split safely; Postgres-only
    "ADD COLUMN IF NOT EXISTS" is resolved via PRAGMA + syntax rewrite.
  * CLOUD  (Supabase Postgres via POOLER_URL) — the whole file in ONE transaction.

Connection chain (cloud): POOLER_URL first (IPv4 route — db.<ref> is IPv6-only and
this workshop network has ULA-only IPv6), then DIRECT_URL as fallback.

Ledger: cloud table `schema_migrations` (filename PK, applied_at, statements) +
local cloud/migrations/applied_migrations.log — dual record, idempotent skips.
A file is marked APPLIED only when BOTH engines committed (idempotent DDL makes
re-runs safe if one side failed before).

Security rules honoured:
  * Credentials live in .env only; NEVER printed/logged anywhere.
  * Local DB writes (DDL only) happen under explicit owner orders — a .bak
    timestamped backup is the owner's standing convention before migrations.

Usage:
  python cloud/schema_migrator.py <path/to/migration.sql>
  python cloud/schema_migrator.py --all     # every cloud/migrations/*.sql not yet applied
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent          # G:\ai\Elnagar POS
sys.path.insert(0, str(ROOT))

from cloud.supabase_sync import load_env               # noqa: E402  (official .env loader)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
APPLIED_LOG = MIGRATIONS_DIR / "applied_migrations.log"
LOCAL_DB = ROOT / "pos_data.db"

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    statements  INTEGER
);
"""


# ------------------------------------------------------------------ statement utils
def _split_statements(sql_text: str) -> List[str]:
    """Portable splitter: drop full-line comments (they may contain ';'),
    then split on ';' and keep non-empty statements. Post-split, each fragment
    may still carry comment lines that FOLLOWED a ';' — clean those too."""
    lines = [l for l in sql_text.splitlines() if not l.strip().startswith("--")]
    body = "\n".join(lines)
    out = []
    for s in body.split(";"):
        frag_lines = [l for l in s.splitlines() if not l.strip().startswith("--")]
        frag = "\n".join(frag_lines).strip()
        if frag:
            out.append(frag)
    return out


_ALTER_RE = re.compile(
    r"^ALTER\s+TABLE\s+(\w+)\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+(\w+)\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)


def _local_conn():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _local_apply(sql_path: Path) -> Tuple[bool, str]:
    """Apply one migration file to the LOCAL SQLite DB (DDL only, one transaction).
    Handles the Postgres-only `ADD COLUMN IF NOT EXISTS` via PRAGMA + rewrite."""
    sql = sql_path.read_text(encoding="utf-8")
    if not sql.strip():
        return False, "empty file"
    stmts = _split_statements(sql)
    conn = _local_conn()
    applied_cols: List[str] = []
    try:
        cur = conn.cursor()
        for stmt in stmts:
            m = _ALTER_RE.match(stmt)
            if m:
                table, col, rest = m.group(1), m.group(2), m.group(3).strip()
                existing = [r["name"] for r in cur.execute(f'PRAGMA table_info("{table}")')]
                if col in existing:
                    continue  # already there — idempotent skip
                cur.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {rest.split("--")[0].strip()}')
                applied_cols.append(f"{table}.{col}")
            else:
                cur.execute(stmt)
        conn.commit()
        detail = f"applied {len(stmts)} stmt(s)"
        if applied_cols:
            detail += " (+" + ", ".join(applied_cols) + ")"
        return True, detail
    except Exception as exc:
        conn.rollback()
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        conn.close()


def _log_local(name: str, result: str, detail: str = "") -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | {name} | {result}" + (f" | {detail}" if detail else "")
    try:
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        with open(APPLIED_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # logging must never kill the run


def _connect_cloud():
    """Try POOLER_URL then DIRECT_URL. Returns (conn, route_label) or raises."""
    import psycopg2

    env = load_env()
    attempts = [
        ((env.get("POOLER_URL") or "").strip().strip('"'), "session pooler"),
        ((env.get("DIRECT_URL") or "").strip().strip('"'), "direct db"),
    ]
    errors = []
    for dsn, label in attempts:
        if not dsn:
            continue
        try:
            return psycopg2.connect(dsn, connect_timeout=20), label
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:120]}")
    raise RuntimeError("no cloud route connected -> " + " || ".join(errors))


def _applied_cloud(conn) -> set:
    cur = conn.cursor()
    cur.execute("SELECT filename FROM schema_migrations")
    return {r[0] for r in cur.fetchall()}


def _applied_local() -> set:
    done: set = set()
    try:
        for line in APPLIED_LOG.read_text(encoding="utf-8").splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[2] == "APPLIED":
                done.add(parts[1])
    except FileNotFoundError:
        pass
    return done


def run_sql_file(sql_path: Path) -> bool:
    """Apply one migration: LOCAL first, then CLOUD, then record both ledgers."""
    if not sql_path.exists():
        print(f"FAIL: migration file not found: {sql_path}")
        return False

    # ---------- LOCAL (SQLite) ----------
    ok_local, local_detail = _local_apply(sql_path)
    if not ok_local:
        print(f"FAIL: {sql_path.name} LOCAL rolled back -> {local_detail}")
        _log_local(sql_path.name, "FAILED", f"local: {local_detail}")
        return False
    print(f"LOCAL APPLIED: {sql_path.name} -> {local_detail}")

    # ---------- CLOUD (Postgres) ----------
    try:
        conn, route = _connect_cloud()
    except Exception as exc:
        print(f"FAIL: {sql_path.name} CLOUD unreachable -> {exc}")
        _log_local(sql_path.name, "FAILED", "cloud unreachable — local applied, re-run to retry cloud")
        return False
    try:
        cur = conn.cursor()
        cur.execute(BOOTSTRAP_SQL)
        conn.commit()
        if sql_path.name in _applied_cloud(conn):
            print(f"CLOUD SKIP: {sql_path.name} already applied (schema_migrations)")
            print(f"APPLIED: {sql_path.name} (local + cloud ledger)")
            _log_local(sql_path.name, "APPLIED", "local done; cloud already recorded")
            return True
        sql = sql_path.read_text(encoding="utf-8").strip()
        started = time.time()
        cur.execute(sql)
        n_stmt = sql.count(";")
        conn.commit()
        secs = round(time.time() - started, 2)
        cur.execute(
            "INSERT INTO schema_migrations (filename, statements) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO NOTHING",
            (sql_path.name, n_stmt),
        )
        conn.commit()
        print(f"CLOUD APPLIED: {sql_path.name} via {route} (committed in {secs}s, ~{n_stmt} statements)")
        print(f"RECORDED: schema_migrations <- {sql_path.name}")
        _log_local(sql_path.name, "APPLIED", f"local + cloud via {route}")
        return True
    except Exception as exc:
        conn.rollback()
        msg = str(exc).replace("\n", " ")[:300]
        print(f"FAIL: {sql_path.name} CLOUD rolled back -> {type(exc).__name__}: {msg}")
        _log_local(sql_path.name, "FAILED", f"cloud: {msg} — local applied, re-run to retry cloud")
        return False
    finally:
        conn.close()


def verify_columns() -> None:
    """Read-only verification on BOTH engines: 001 mirror columns (15) +
    002 manufacturing artifacts (2 product columns + 2 new tables)."""
    expected_001 = {
        "clients": ["phone"],
        "products": ["sort_order", "stock"],
        "orders": ["local_image_path", "image_url", "unique_hash", "source_path", "synced"],
        "transactions": ["category", "user", "is_verified", "is_savings",
                         "material_cost_recovery", "net_profit_portion", "expense_type"],
    }
    expected_002_cols = {"products": ["material_type", "operation_type"]}
    expected_002_tables = ["raw_materials", "product_recipes"]

    # ---------- LOCAL ----------
    conn = _local_conn()
    try:
        cur = conn.cursor()
        missing = []
        for table, cols in {**expected_001, **expected_002_cols}.items():
            have = {r["name"] for r in cur.execute(f'PRAGMA table_info("{table}")')}
            missing += [f"{table}.{c}" for c in cols if c not in have]
        local_tables = {r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing += [f"table:{t}" for t in expected_002_tables if t not in local_tables]
        print(f"verify LOCAL : {'OK — all 001+002 artifacts present' if not missing else 'MISSING: ' + ', '.join(missing)}")
    finally:
        conn.close()

    # ---------- CLOUD ----------
    conn, route = _connect_cloud()
    try:
        cur = conn.cursor()
        present, absent = 0, []
        for table, cols in {**expected_001, **expected_002_cols}.items():
            for col in cols:
                cur.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                    (table, col),
                )
                if cur.fetchone():
                    present += 1
                else:
                    absent.append(f"{table}.{col}")
        for t in expected_002_tables:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s", (t,))
            if not cur.fetchone():
                absent.append(f"table:{t}")
        total = sum(len(v) for v in {**expected_001, **expected_002_cols}.values()) + 2
        print(f"verify CLOUD [{route}]: {present + (2 - len([a for a in absent if a.startswith('table:')]))}/{total} artifacts present")
        if absent:
            print("still missing:", ", ".join(absent))
        else:
            print("verify: ALL 001+002 artifacts exist — mirror is now full-width")
        cur.execute("SELECT filename, applied_at FROM schema_migrations ORDER BY applied_at")
        rows = cur.fetchall()
        print(f"schema_migrations ledger: {len(rows)} record(s)")
        for fn, ts in rows:
            print(f"  - {fn} @ {ts}")
    finally:
        conn.close()


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    if args[0] == "--all":
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            print("no migration files found in", MIGRATIONS_DIR)
            return 1
        done_local = _applied_local()
        pending = [f for f in files if f.name not in done_local]
        print(f"migrations found: {len(files)} | already applied: {len(files) - len(pending)} | pending: {len(pending)}")
        ok = True
        for f in pending:
            print(f"--- running {f.name} ---")
            ok = run_sql_file(f) and ok
        if ok:
            verify_columns()
        return 0 if ok else 1

    path = Path(args[0])
    if not path.is_absolute():
        path = ROOT / path
    ok = run_sql_file(path)
    if ok:
        verify_columns()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
