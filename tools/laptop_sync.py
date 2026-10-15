#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Marwa Laptop Sync — العقدتان متزامنتان دائماً (الورشة + اللابتوب)
================================================================
Owner order 2026-10-14. The cloud brain vault (Supabase table `system_brain_sync`,
migration 003) is the meeting point of the two nodes:

  WORKSHOP (NODE_ID=WORKSHOP)   LAPTOP (NODE_ID=LAPTOP)
     |  supabase_sync --push-once      (mirror data, existing engine)
     |  laptop_sync.py --push-brain  -> system_brain_sync  <- laptop_sync.py --push-brain
     |                                                            |
     +--------- git pull / push (GitHub: Marwa-Bot) --------------+

Modes
-----
  --pull-all      Pull ALL Supabase mirror tables (clients, products, orders,
                  order_items, transactions, raw_materials, product_recipes)
                  + the brain vault -> build/update ROOT/pos_data.db locally
                  and refresh the memory files. THIS NEVER TOUCHES THE LIVE
                  WORKSHOP DB (only the repo-local mirror).
  --pull-brain    Brain files only (fast pickup of the other node's memory).
  --push-brain    Read the memory files + .env (+ live shift/settings state on
                  the workshop) -> upsert into system_brain_sync, then git
                  add/commit/push the brain files (best-effort, honest errors).
  --restore-env   Rebuild ROOT/.env from vault key env_backup. A fresh machine
                  gets NODE_ID=LAPTOP automatically. Refuses to overwrite an
                  existing .env unless --force.
  --status        Read-only: NODE_ID, local mirror counts, vault keys + ages.
  --no-git        (with --push-brain) skip the git step.

Requirements: `pip install supabase`  (REST path; no psycopg2 needed here).
Identity comes from ROOT/.env -> NODE_ID=WORKSHOP | LAPTOP.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent          # repo root (both nodes)
ENV_PATH = ROOT / ".env"
DB_PATH = ROOT / "pos_data.db"
PAGE = 1000                                             # PostgREST max rows per page

# ---------------------------------------------------------------- brain files
BRAIN_FILES: Dict[str, str] = {
    "status_md": "STATUS.md",
    "decisions_log_md": "memory/decisions_log.md",
    "roadmap_md": "memory/roadmap.md",
    "learned_rules": "RULES.md",
    "owner_preferences_md": "memory/owner_preferences.md",
    "lessons_md": "memory/lessons.md",
    "agent_charter_md": "AGENT.md",
}
BRAIN_GIT_PATHS = ["STATUS.md", "RULES.md", "AGENT.md", "memory"]

VAULT_KEY_ENV = "env_backup"
VAULT_KEY_STATE = "local_state_json"    # daily_shifts + settings rows (JSON)
VAULT_KEY_MANIFEST = "brain_manifest"

# ------------------------------------------------------------- local schema
# Exact per PRAGMA table_info of the live pos_data.db (2026-10-14). Portable
# SQLite dialect — the laptop mirror is byte-compatible with the workshop.
SQLITE_SCHEMA: Dict[str, str] = {
    "clients": """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            type TEXT DEFAULT 'Retail',
            balance REAL DEFAULT 0,
            notes TEXT
        )""",
    "products": """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price_wholesale REAL DEFAULT 0,
            price_retail REAL DEFAULT 0,
            stock_qty INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0,
            last_cost_price REAL DEFAULT 0,
            material_type TEXT,
            operation_type TEXT
        )""",
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            client_id INTEGER,
            total_amount REAL,
            status TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            local_image_path TEXT,
            image_url TEXT,
            unique_hash TEXT,
            notes TEXT,
            source_path TEXT,
            synced INTEGER DEFAULT 0,
            delivery_date TEXT,
            custom_notes TEXT
        )""",
    "order_items": """
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            product_name TEXT,
            qty INTEGER,
            price REAL,
            total REAL
        )""",
    "transactions": """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY,
            client_id INTEGER,
            type TEXT,
            amount REAL,
            notes TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category TEXT,
            "user" TEXT,
            related_ref TEXT,
            is_verified INTEGER DEFAULT 0,
            is_savings INTEGER DEFAULT 0,
            material_cost_recovery REAL DEFAULT 0,
            net_profit_portion REAL DEFAULT 0,
            expense_type TEXT DEFAULT 'Business'
        )""",
    "raw_materials": """
        CREATE TABLE IF NOT EXISTS raw_materials (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'sheet',
            material_kind TEXT NOT NULL DEFAULT 'wood',
            width_cm REAL DEFAULT 0,
            height_cm REAL DEFAULT 0,
            sheet_price REAL DEFAULT 0,
            price_per_cm2 REAL DEFAULT 0,
            unit TEXT DEFAULT 'sheet',
            supplier TEXT,
            notes TEXT
        )""",
    "product_recipes": """
        CREATE TABLE IF NOT EXISTS product_recipes (
            product_id INTEGER PRIMARY KEY,
            material_code TEXT,
            operation_type TEXT,
            length_cm REAL DEFAULT 0,
            width_cm REAL DEFAULT 0,
            waste_pct REAL DEFAULT 5.0,
            machine_time_min REAL DEFAULT 0,
            extra_parts TEXT,
            notes TEXT
        )""",
    "daily_shifts": """
        CREATE TABLE IF NOT EXISTS daily_shifts (
            id INTEGER PRIMARY KEY,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            total_revenue REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            net_profit REAL DEFAULT 0,
            status TEXT DEFAULT 'open'
        )""",
    "settings": """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
    "system_brain_sync": """
        CREATE TABLE IF NOT EXISTS system_brain_sync (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""",
}

MIRROR_TABLES = ["clients", "products", "orders", "order_items",
                 "transactions", "raw_materials", "product_recipes"]
PK_FIELDS: Dict[str, str] = {
    "clients": "id", "products": "id", "orders": "id", "order_items": "id",
    "transactions": "id", "raw_materials": "code", "product_recipes": "product_id",
    "daily_shifts": "id", "settings": "key",
}

# ------------------------------------------------------------ tiny utilities
def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def load_env() -> Dict[str, str]:
    """No-dependency .env loader (same semantics as cloud/supabase_sync.py).
    Never prints values."""
    env: Dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k:
                env[k] = v
    return env


def node_id(env: Dict[str, str]) -> str:
    nid = env.get("NODE_ID", "").strip().upper()
    return nid if nid in ("WORKSHOP", "LAPTOP") else "UNKNOWN"


def get_client(env: Dict[str, str]):
    from supabase import create_client

    url = env.get("SUPABASE_URL", "").rstrip("/")
    key = (env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
           or env.get("SUPABASE_PUBLISHABLE_KEY") or env.get("SUPABASE_ANON_KEY") or "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL / secret key missing in .env — plant .env first")
    return create_client(url, key)


def _read_file(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _write_file(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)


def _fetch_all(client, table: str) -> List[Dict[str, Any]]:
    """Paginated full-table fetch (PostgREST caps rows per request)."""
    rows: List[Dict[str, Any]] = []
    start = 0
    while True:
        resp = (client.table(table).select("*").range(start, start + PAGE - 1).execute())
        page = resp.data or []
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        start += PAGE


def _table_cols(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f'PRAGMA table_info("{table}")')
    return [r[1] for r in cur.fetchall()]


def _seed_table(conn: sqlite3.Connection, table: str, rows: List[Dict[str, Any]],
                drop_extra: bool = True) -> Dict[str, Any]:
    """Idempotent full refresh of one mirror table inside a single transaction."""
    conn.executescript(SQLITE_SCHEMA[table])
    cols = _table_cols(conn, table)
    kept, dropped = 0, set()
    cur = conn.cursor()
    cur.execute(f'DELETE FROM "{table}"')
    for row in rows:
        values = {}
        for c in cols:
            if c in row:
                values[c] = row[c]
            else:
                values[c] = None
        if drop_extra:
            dropped |= {k for k in row.keys() if k not in cols}
        placeholders = ", ".join("?" for _ in cols)
        quoted = ", ".join(f'"{c}"' for c in cols)
        cur.execute(f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                    [values[c] for c in cols])
        kept += 1
    conn.commit()
    return {"rows": kept, "dropped_cloud_cols": sorted(dropped)}


# ------------------------------------------------------------------- pull data
def pull_all(env: Dict[str, str]) -> int:
    client = get_client(env)
    print(f"[node] {node_id(env)} | mirror target: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        for table in MIRROR_TABLES:
            rows = _fetch_all(client, table)
            info = _seed_table(conn, table, rows)
            extra = f" (cloud-only cols skipped: {info['dropped_cloud_cols']})" if info["dropped_cloud_cols"] else ""
            print(f"  [pull] {table:<16} {info['rows']:>4} rows{extra}")
    finally:
        conn.close()
    _apply_brain_to_disk(client, env, restore_env_if_missing=True)
    print("[done] pull-all complete — local mirror is current.")
    return 0


def pull_brain(env: Dict[str, str]) -> int:
    client = get_client(env)
    changed = _apply_brain_to_disk(client, env, restore_env_if_missing=True)
    print(f"[done] pull-brain complete — {changed} file(s) refreshed.")
    return 0


# ------------------------------------------------------------------ brain pull
def _vault_rows(client) -> Dict[str, Dict[str, Any]]:
    rows = _fetch_all(client, "system_brain_sync")
    return {r["key"]: r for r in rows if r.get("key")}


def _apply_brain_to_disk(client, env: Dict[str, str],
                         restore_env_if_missing: bool) -> int:
    vault = _vault_rows(client)
    changed = 0

    # 1) memory files
    for key, rel in BRAIN_FILES.items():
        row = vault.get(key)
        if not row or row.get("value") is None:
            print(f"  [brain] {key:<22} missing in vault — skipped")
            continue
        target = ROOT / rel
        current = _read_file(target)
        if current == row["value"]:
            print(f"  [brain] {key:<22} up-to-date ({len(row['value'])} chars)")
        else:
            _write_file(target, row["value"])
            changed += 1
            print(f"  [brain] {key:<22} WRITTEN -> {rel} ({len(row['value'])} chars)")

    # 2) manifest (informational)
    if VAULT_KEY_MANIFEST in vault:
        manifest_value = vault[VAULT_KEY_MANIFEST].get("value")
        if isinstance(manifest_value, str):
            try:
                manifest_value = json.loads(manifest_value)
            except Exception:
                pass
        if not isinstance(manifest_value, str):
            _write_file(ROOT / "memory" / "brain_manifest.json",
                        json.dumps(manifest_value, ensure_ascii=False, indent=2))

    # 3) local state (daily_shifts + settings) — keeps financial semantics identical
    state_row = vault.get(VAULT_KEY_STATE)
    if state_row and state_row.get("value"):
        try:
            state = json.loads(state_row["value"])
            conn = sqlite3.connect(DB_PATH)
            try:
                for table in ("daily_shifts", "settings"):
                    rows = state.get(table) or []
                    info = _seed_table(conn, table, rows)
                    print(f"  [state] {table:<12} {info['rows']} row(s) restored")
            finally:
                conn.close()
        except Exception as exc:
            print(f"  [state] FAILED to apply local_state_json: {exc}")

    # 4) env backup — bootstrap only (never overwrite an existing .env)
    if restore_env_if_missing and not ENV_PATH.exists():
        row = vault.get(VAULT_KEY_ENV)
        if row and row.get("value"):
            _write_env_with_node(row["value"], "LAPTOP")
            print("  [env]   .env was MISSING — restored from vault (NODE_ID=LAPTOP).")
            print("         Review it, then re-run your command.")
            changed += 1
        else:
            print("  [env]   .env missing and vault has no env_backup — plant it manually.")
    return changed


def _write_env_with_node(env_text: str, nid: str) -> None:
    out_lines, seen = [], False
    for line in env_text.splitlines():
        if line.strip().startswith("NODE_ID"):
            out_lines.append(f"NODE_ID={nid}")
            seen = True
        else:
            out_lines.append(line)
    if not seen:
        out_lines.append(f"NODE_ID={nid}")
    _write_file(ENV_PATH, "\n".join(out_lines) + "\n")


# ------------------------------------------------------------------ brain push
def _capture_local_state(env: Dict[str, str]) -> Optional[str]:
    """Workshop-only: read daily_shifts + settings from the LIVE db (mode=ro)."""
    live = (env.get("LIVE_DB_PATH") or "").strip()
    if not live or not Path(live).exists():
        return None
    conn = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        state: Dict[str, Any] = {}
        for table in ("daily_shifts", "settings"):
            try:
                rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"')]
                state[table] = rows
            except sqlite3.Error:
                state[table] = []
        return json.dumps(state, ensure_ascii=False)
    finally:
        conn.close()


def push_brain(env: Dict[str, str], use_git: bool = True) -> int:
    client = get_client(env)
    nid = node_id(env)
    payload: Dict[str, str] = {}
    sizes: Dict[str, int] = {}

    for key, rel in BRAIN_FILES.items():
        content = _read_file(ROOT / rel)
        if content is None:
            print(f"  [brain] {key:<22} file missing ({rel}) — skipped")
            continue
        payload[key] = content
        sizes[key] = len(content)

    env_text = _read_file(ENV_PATH)
    if env_text is not None:
        payload[VAULT_KEY_ENV] = env_text
        sizes[VAULT_KEY_ENV] = len(env_text)
    else:
        print("  [brain] env_backup skipped — no .env at repo root")

    state = _capture_local_state(env)
    if state:
        payload[VAULT_KEY_STATE] = state
        print(f"  [state] live daily_shifts + settings captured ({len(state)} chars)")

    manifest = {
        "node": nid,
        "pushed_at": _utcnow(),
        "files": {k: v for k, v in sorted(sizes.items())},
        "machine": os.environ.get("COMPUTERNAME", ""),
    }
    payload[VAULT_KEY_MANIFEST] = json.dumps(manifest, ensure_ascii=False)

    stamp = _utcnow()
    rows = [{"key": k, "value": v, "updated_at": stamp} for k, v in payload.items()]
    client.table("system_brain_sync").upsert(rows, on_conflict="key").execute()
    print(f"[vault] pushed {len(rows)} key(s) to system_brain_sync from node {nid} @ {stamp}")

    if use_git:
        return _git_push_brain(nid)
    return 0


def _git_push_brain(nid: str) -> int:
    if not (ROOT / ".git").exists():
        print("[git]   not a git repository — vault push done, git skipped (honest skip).")
        return 0
    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True, timeout=120)
    try:
        run("add", *BRAIN_GIT_PATHS)
        st = run("status", "--porcelain")
        if not st.stdout.strip():
            print("[git]   brain files already committed — nothing new.")
            return 0
        msg = f"brain: sync from {nid} @ {stamp_short()}"
        run("commit", "-m", msg)
        push = run("push", "origin", "HEAD")
        if push.returncode == 0:
            print(f"[git]   committed + pushed: {msg}")
        else:
            print(f"[git]   commit OK, push FAILED (honest): {push.stderr.strip()[:200]}")
            print("        fix remote/auth then: git push origin HEAD")
        return 0
    except Exception as exc:
        print(f"[git]   FAILED (vault push already done): {exc}")
        return 0


def stamp_short() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


# ------------------------------------------------------------------ other modes
def restore_env(env: Dict[str, str], force: bool) -> int:
    if ENV_PATH.exists() and not force:
        print("[env] .env already exists — refusing to overwrite (use --force to replace).")
        return 1
    # needs at least URL + key reachable (from args/env of this process)
    try:
        client = get_client(env)
    except Exception as exc:
        print(f"[env] cannot reach cloud: {exc}")
        print("      restore-env needs SUPABASE_URL + secret key available (any .env or env vars).")
        return 1
    vault = _vault_rows(client)
    row = vault.get(VAULT_KEY_ENV)
    if not row or not row.get("value"):
        print("[env] vault has no env_backup yet — push it first with --push-brain.")
        return 1
    _write_env_with_node(row["value"], "LAPTOP")
    print("[env] .env restored from vault with NODE_ID=LAPTOP — review it now.")
    return 0


def status(env: Dict[str, str]) -> int:
    print(f"[node]  {node_id(env)}   (.env: {'present' if ENV_PATH.exists() else 'MISSING'})")
    if DB_PATH.exists():
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            for t in MIRROR_TABLES + ["daily_shifts", "settings"]:
                try:
                    n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                    print(f"  [db]  {t:<16} {n:>4} rows")
                except sqlite3.Error:
                    print(f"  [db]  {t:<16} -")
        finally:
            conn.close()
    else:
        print("[db]   no local pos_data.db yet — run --pull-all")
    try:
        client = get_client(env)
        vault = _vault_rows(client)
        print(f"[vault] {len(vault)} key(s) in system_brain_sync:")
        for k, row in sorted(vault.items()):
            size = len(row.get("value") or "")
            print(f"  {k:<22} {size:>8} chars  updated {row.get('updated_at')}")
    except Exception as exc:
        print(f"[vault] unreachable: {exc}")
    return 0


# ------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description="Marwa laptop sync (WORKSHOP <-> LAPTOP)")
    ap.add_argument("--pull-all", action="store_true")
    ap.add_argument("--pull-brain", action="store_true")
    ap.add_argument("--push-brain", action="store_true")
    ap.add_argument("--restore-env", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--force", action="store_true", help="allow restore-env to overwrite .env")
    args = ap.parse_args()

    env = load_env()
    if not env and not args.restore_env:
        print("FATAL: no .env at repo root and no credentials in this process.")
        print("On the laptop: plant .env (see LAPTOP_SECRET_KIT) or use --restore-env with keys available.")
        return 2

    try:
        if args.pull_all:
            return pull_all(env)
        if args.pull_brain:
            return pull_brain(env)
        if args.push_brain:
            return push_brain(env, use_git=not args.no_git)
        if args.restore_env:
            return restore_env(env, force=args.force)
        if args.status:
            return status(env)
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}")
        return 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
