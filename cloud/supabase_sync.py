#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elnagar POS — Hybrid Cloud Sync Engine (HermesSyncManager)
=========================================================
Level 1 implementation, path 1 (cloud).
- push_mirror(): reads LOCAL pos_data.db (mode=ro only) tables and upserts to Supabase.
- pull_queue(): reads Supabase `commands` where status='pending' (posted from Telegram
  while the program was offline), executes them LOCALLY via official program functions,
  then updates status -> 'applied'.
- Optional --query-client/--query-product: reads prices/clients FROM THE CLOUD for
  Telegram continuity (reduces load on the local agent).

Security rules honoured:
  * pos_data.db opened strictly WITH mode=ro (read-only) -> no local writes from mirror.
  * No token values are logged or printed; .env loads locally.
  * TELEGRAM_BOT_TOKEN supplied by owner (option B, 2026-10-12) — used only to send
    screenshots to OWNER for system_command; the local POLLER of the bot is off, so
    the cloud webhook is the only receiver (avoids 409).
Usage:
  python cloud\\supabase_sync.py --push-once
  python cloud\\supabase_sync.py --pull-once          (default 10 max)
  python cloud\\supabase_sync.py --daemon             (every SYNC_INTERVAL_SECONDS)
  python cloud\\supabase_sync.py --query-client <q>   (read from cloud)
  python cloud\\supabase_sync.py --query-product <q>  (read from cloud)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Path setup -------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent          # G:\ai\Naggar Print POS Agent
SYNC_DIR = Path(__file__).resolve().parent             # G:\ai\Naggar Print POS Agent\cloud

# ── طبقة الربط المركزية (task-2): المرآة تقرأ من المصدر الرسمي الحي فقط ──
_VISION_LAB = Path(__file__).resolve().parent.parent / "Vision-Lab"   # نسبي — يعمل على أي عقدة (ورشة/لابتوب)
if str(_VISION_LAB) not in sys.path:
    sys.path.insert(0, str(_VISION_LAB))
from config import data_source as _central  # noqa: E402

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SYNC_DIR) not in sys.path:
    sys.path.insert(0, str(SYNC_DIR))

DB_PATH = _central.db_path()          # المصدر الرسمي الحي — بدل نسخة المساحة الميتة
ENV_PATH = ROOT / ".env"
LOG_PATH = SYNC_DIR / "supabase_sync.log"

DEFAULT_INTERVAL = 60

# Core tables mirrored (single mode of transport: LOCAL -> CLOUD for read + mirror,
# CLOUD -> LOCAL only for queued commands via pull_queue).
# 002_manufacturing_schema (Phase 6, 2026-10-14): raw_materials + product_recipes join the mirror.
MIRROR_TABLES = ("clients", "products", "orders", "order_items", "transactions",
                 "raw_materials", "product_recipes")

# LOCAL schema = exact per PRAGMA table_info (2026-10-13, + 002 manufacturing 2026-10-14).
# This is the source of truth; the cloud mirror is expanded via cloud/migrations/
# (001 + 002, applied autonomously by cloud/schema_migrator.py --all).
# push_mirror() dynamically intersects these with the cloud's actual columns (introspection),
# so the moment a migration runs, the mirror becomes byte-exact.
LOCAL_SCHEMA = {
    "clients": ["id", "name", "phone", "type", "balance", "notes"],
    "products": ["id", "name", "category", "price_wholesale", "price_retail",
                 "stock_qty", "sort_order", "stock", "last_cost_price",
                 "material_type", "operation_type"],
    "orders": ["id", "client_id", "total_amount", "status", "date", "local_image_path",
               "image_url", "unique_hash", "notes", "source_path", "synced",
               "delivery_date", "custom_notes"],
    "order_items": ["id", "order_id", "product_id", "product_name", "qty", "price", "total"],
    "transactions": ["id", "client_id", "type", "amount", "notes", "date", "category",
                     "user", "related_ref", "is_verified", "is_savings",
                     "material_cost_recovery", "net_profit_portion", "expense_type"],
    "raw_materials": ["code", "name", "category", "material_kind", "width_cm", "height_cm",
                      "sheet_price", "price_per_cm2", "unit", "supplier", "notes"],
    "product_recipes": ["product_id", "material_code", "operation_type", "length_cm",
                        "width_cm", "waste_pct", "machine_time_min", "extra_parts", "notes"],
}

PK_FIELDS = {
    "clients": "id",
    "products": "id",
    "orders": "id",
    "order_items": "id",
    "transactions": "id",
    "raw_materials": "code",
    "product_recipes": "product_id",
}

# Fallback subset — verified present on Supabase (001 + 002 applied autonomously 2026-10-14).
# Used ONLY if live introspection fails, so the daemon never dies on a network blip.
SAFE_FALLBACK = {
    "clients": ["id", "name", "type", "balance", "notes"],
    "products": ["id", "name", "category", "price_wholesale", "price_retail",
                 "stock_qty", "last_cost_price", "material_type", "operation_type"],
    "orders": ["id", "client_id", "total_amount", "status", "date", "notes",
               "delivery_date", "custom_notes"],
    "order_items": ["id", "order_id", "product_id", "product_name", "qty", "price", "total"],
    "transactions": ["id", "client_id", "type", "amount", "notes", "date", "related_ref"],
    "raw_materials": ["code", "name", "category", "material_kind", "width_cm", "height_cm",
                      "sheet_price", "price_per_cm2", "unit", "supplier", "notes"],
    "product_recipes": ["product_id", "material_code", "operation_type", "length_cm",
                        "width_cm", "waste_pct", "machine_time_min", "extra_parts", "notes"],
}


def load_env() -> Dict[str, str]:
    """Load key=... lines from .env (no dependency). Never prints values."""
    env: Dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                env[k] = v
    return env


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"{ts} [{level}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


class HermesSyncManager:
    """Reads local ro DB -> upsert cloud; drains pending cloud commands to local."""

    def __init__(self, env: Optional[Dict[str, str]] = None):
        self.env = env or load_env()
        self.url = self.env.get("SUPABASE_URL", "")
        self.key = self.env.get("SUPABASE_SECRET_KEY", "") or self.env.get(
            "SUPABASE_PUBLISHABLE_KEY", ""
        )
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL / key missing in .env")
        self._client = None
        # Live cloud-column cache (introspection) + one-time warn flags
        self._cloud_cols: Optional[Dict[str, set]] = None
        self._cloud_cols_failed = False
        self._schema_warned: Dict[str, bool] = {}

    # ------------------------------------------------------------------ cloud
    def _get_client(self):
        if self._client is None:
            from supabase import create_client

            self._client = create_client(self.url, self.key)
        return self._client

    def _read_local_table(self, table: str, cols: List[str]) -> List[Dict[str, Any]]:
        """Read a local table with pos_data.db strictly read-only (mode=ro)."""
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            quoted = ", ".join(f'"{c}"' for c in cols)  # quotes protect reserved names ("user")
            order_by = PK_FIELDS.get(table, "id")  # 002: non-id PKs (code / product_id)
            rows = conn.execute(f"SELECT {quoted} FROM {table} ORDER BY {order_by}").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # -------------------------------------------------- live cloud introspection
    def _cloud_columns(self) -> Optional[Dict[str, set]]:
        """Introspect the LIVE cloud columns once per process via the REST OpenAPI
        document (Swagger 2.0 -> definitions). Returns None when unavailable."""
        if self._cloud_cols is None and not self._cloud_cols_failed:
            try:
                import requests as _rq

                r = _rq.get(
                    f"{self.url.rstrip('/')}/rest/v1/",
                    headers={
                        "apikey": self.key,
                        "Authorization": f"Bearer {self.key}",
                        "Accept": "application/openapi+json",
                    },
                    timeout=30,
                )
                r.raise_for_status()
                defs = (r.json() or {}).get("definitions", {})
                cols_map = {
                    t: set((defs.get(t) or {}).get("properties", {}).keys())
                    for t in MIRROR_TABLES
                }
                if not any(cols_map.values()):
                    raise ValueError("empty swagger definitions")
                self._cloud_cols = cols_map
            except Exception as exc:
                log(f"cloud introspection failed -> SAFE_FALLBACK columns ({type(exc).__name__})", "WARN")
                self._cloud_cols_failed = True
        return self._cloud_cols

    def _effective_columns(self, table: str) -> List[str]:
        """LOCAL_SCHEMA ∩ live cloud columns — the mirror widens AUTOMATICALLY the
        moment cloud/migrations/001_add_missing_columns.sql runs on Supabase."""
        cloud = self._cloud_columns()
        if not cloud:
            return list(SAFE_FALLBACK[table])
        cols = [c for c in LOCAL_SCHEMA[table] if c in cloud.get(table, set())]
        dropped = [c for c in LOCAL_SCHEMA[table] if c not in cloud.get(table, set())]
        if dropped and not self._schema_warned.get(table):
            log(
                f"{table}: cloud lacks {dropped} — run cloud/migrations/001_add_missing_columns.sql "
                "on Supabase; skipped for now",
                "WARN",
            )
            self._schema_warned[table] = True
        return cols or list(SAFE_FALLBACK[table])

    # ------------------------------------------------------------- push mirror
    def push_mirror(self, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        """Upsert local tables -> Supabase (LOCAL -> CLOUD). ro local reads."""
        client = self._get_client()
        tables = tables or list(MIRROR_TABLES)
        summary: Dict[str, Any] = {}
        for table in tables:
            if table not in LOCAL_SCHEMA:
                raise ValueError(f"Unknown table: {table}")
            cols = self._effective_columns(table)
            rows = self._read_local_table(table, cols)
            pk = PK_FIELDS[table]
            if rows:
                # upsert ignores non-PK uniqueness; PK drives conflict resolution
                resp = (
                    client.table(table)
                    .upsert(rows, on_conflict=pk)
                    .execute()
                )
                n = len(resp.data) if resp.data is not None else 0
            else:
                n = 0
            summary[table] = {"rows": len(rows), "upserted": n}
            log(f"push_mirror: {table} rows={len(rows)} upserted={n}")
        return summary

    # -------------------------------------------------------------- pull queue
    def pull_queue(self, limit: int = 10) -> Dict[str, Any]:
        """Read Supabase 'commands' status=pending and apply locally with official
        program functions. This is the ONLY CLOUD -> LOCAL write path."""
        client = self._get_client()
        resp = (
            client.table("commands")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        applied, failed, skipped = [], [], []
        for cmd in rows:
            cmd_id = cmd.get("id")
            cmd_action = (cmd.get("action") or cmd.get("type") or "").strip()
            payload = cmd.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            if cmd_action == "system_command":
                cmd_action = "system_command"  # tolerate typo
            # System commands run differently (they are NOT DB transactions)
            if cmd_action == "system_command":
                result = self._execute_system_command(payload)
            elif cmd_action == "orchestrate":
                result = self._run_orchestrator(payload)
            else:
                # Official local function dispatch (safe signatures only)
                result = self._dispatch_command(cmd_action, payload)
            if result.get("success"):
                applied.append({"id": cmd_id, "action": cmd_action})
                self._mark_applied(cmd_id, result)
            else:
                failed.append({"id": cmd_id, "action": cmd_action, "error": result.get("error")})
                self._mark_failed(cmd_id, result.get("error"))
        return {
            "pending": len(rows),
            "applied": applied,
            "failed": failed,
            "skipped": skipped,
        }

    def _execute_system_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a system_command on this machine: screenshot / shutdown / restart.
        Screenshot is sent directly to OWNER via Telegram, then marked applied."""
        cmd = (payload.get("cmd") or "").strip().lower()
        try:
            if cmd == "screenshot":
                return self._take_screenshot_and_send()
            if cmd in ("shutdown", "off"):
                os.system('shutdown /s /t 5 /c "ElnagarPOS cloud command"')
                return {"success": True, "info": "shutdown scheduled"}
            if cmd in ("restart", "reboot"):
                os.system('shutdown /r /t 5 /c "ElnagarPOS cloud command"')
                return {"success": True, "info": "restart scheduled"}
            if cmd in ("open_app", "open_folder"):
                # Machine command (Phase 7): open a program or folder on this PC.
                target = (payload.get("path") or payload.get("folder") or "").strip()
                if not target:
                    return {"success": False, "error": "open_app/open_folder needs payload.path"}
                try:
                    os.startfile(target)  # Windows shell open (exe, folder, file)
                    return {"success": True, "info": f"opened {target}"}
                except Exception as exc:
                    return {"success": False, "error": f"startfile failed: {exc}"}
            return {"success": False, "error": f"Unknown system cmd: {cmd}"}
        except Exception as exc:
            return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    def _take_screenshot_and_send(self) -> Dict[str, Any]:
        """mss screenshot -> sendPhoto to OWNER via Telegram -> success."""
        import mss  # mss is already a dependency of the program
        import requests as _rq

        owner = self.env.get("OWNER_TELEGRAM_ID", "")
        token = self.env.get("TELEGRAM_BOT_TOKEN", "")
        if not owner or not token:
            return {"success": False, "error": "OWNER_TELEGRAM_ID / TELEGRAM_BOT_TOKEN missing in .env"}
        shot_path = SYNC_DIR / "screenshot.png"
        with mss.mss() as sct:
            sct.shot(output=str(shot_path))
        with open(shot_path, "rb") as fh:
            files = {"photo": (shot_path.name, fh, "image/png")}
            data = {"chat_id": owner}
            r = _rq.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data=data,
                files=files,
                timeout=60,
            )
        if not r.ok:
            return {"success": False, "error": f"Telegram sendPhoto {r.status_code}: {r.text[:200]}"}
        try:
            shot_path.unlink()
        except Exception:
            pass
        return {"success": True, "info": "screenshot sent to owner"}

    def _run_orchestrator(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the LOCAL orchestrator brain on business text and send its reply
        directly to OWNER via Telegram (NO DB writes — read-only brain).
        Enqueued by the cloud webhook with payload={"text": "...", "chat_id": "..."}."""
        try:
            text = (payload.get("text") or payload.get("message") or "").strip()
            chat_id = str(payload.get("chat_id") or self.env.get("OWNER_TELEGRAM_ID") or "").strip()
            if not text:
                return {"success": False, "error": "no text in orchestrate payload"}
            # Local orchestrator (Phase 1) — pure routing + stub sub-agents.
            sys.path.insert(0, str(ROOT))
            from orchestrator.core import Orquesta
            reply = Orquesta().handle(text).get("reply") or "تمام."
            # Deliver the reply back to the owner over Telegram.
            sent = self._tg_send_message(chat_id, reply)
            if sent:
                return {"success": True, "info": f"orchestrate replied ({len(reply)} chars)"}
            return {"success": False, "error": "orchestrate reply failed to send"}
        except Exception as exc:
            return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    def _tg_send_message(self, chat_id: str, text: str) -> bool:
        """Send a plain text message to a chat via the program bot token."""
        import requests as _rq

        token = self.env.get("TELEGRAM_BOT_TOKEN", "")
        if not token or not chat_id:
            return False
        # Telegram message limit ~4096; chunk politely.
        chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)] or [text]
        for chunk in chunks:
            r = _rq.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk},
                timeout=30,
            )
            if not r.ok:
                return False
        return True

    def _dispatch_command(self, cmd_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import database  # official local module

            if cmd_type == "create_order":
                # Map payload to official save_order_transaction signature
                items = payload.get("items") or []
                if isinstance(items, str):
                    items = json.loads(items)
                return database.save_order_transaction(
                    client_id=payload.get("client_id"),
                    total_amount=payload.get("total_amount", 0),
                    discount=payload.get("discount", 0),
                    net_total=payload.get("net_total", payload.get("total_amount", 0)),
                    paid_amount=payload.get("paid_amount", 0),
                    remaining=payload.get(
                        "remaining",
                        (payload.get("total_amount", 0) or 0)
                        - (payload.get("paid_amount", 0) or 0)
                        - (payload.get("discount", 0) or 0),
                    ),
                    items=items,
                    payment_method=payload.get("payment_method", "Credit"),
                    notes=payload.get("notes", ""),
                )
            if cmd_type == "create_client":
                return database.add_new_client(
                    payload.get("name", ""),
                    payload.get("phone", ""),
                    payload.get("type", "Retail"),
                    payload.get("notes", "Created via cloud command"),
                )
            if cmd_type == "add_product":
                return database.add_quick_product(
                    payload.get("name", ""),
                    payload.get("category", ""),
                    payload.get("price_retail", 0),
                    payload.get("price_wholesale", 0),
                )
            if cmd_type == "record_payment":
                # official payment function: record_client_payment(client_id, amount, notes)
                return database.record_client_payment(
                    payload.get("client_id"),
                    payload.get("amount", 0),
                    payload.get("notes", "Payment via cloud command"),
                )
            return {"success": False, "error": f"Unknown command type: {cmd_type}"}
        except Exception as exc:
            return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    def _mark_applied(self, cmd_id, result) -> None:
        client = self._get_client()
        client.table("commands").update(
            {
                "status": "applied",
                "reason": json.dumps(result, ensure_ascii=False)[:1000],
            }
        ).eq("id", cmd_id).execute()

    def _mark_failed(self, cmd_id, error) -> None:
        client = self._get_client()
        client.table("commands").update(
            {
                "status": "failed",
                "reason": str(error)[:1000],
            }
        ).eq("id", cmd_id).execute()

    # ------------------------------------------------------------ cloud queries
    def query_clients(self, q: str, limit: int = 10) -> List[Dict[str, Any]]:
        client = self._get_client()
        resp = (
            client.table("clients")
            .select("*")
            .ilike("name", f"%{q}%")
            .limit(limit)
            .execute()
        )
        return resp.data or []

    def query_products(self, q: str, limit: int = 10) -> List[Dict[str, Any]]:
        client = self._get_client()
        resp = (
            client.table("products")
            .select("*")
            .ilike("name", f"%{q}%")
            .limit(limit)
            .execute()
        )
        return resp.data or []

    # ---------------------------------------------------------------- daemon
    def run_daemon(self, interval: int = DEFAULT_INTERVAL, no_pull: bool = False) -> None:
        """no-pull: الدفع فقط — سحب الأوامر يبقى لمشرف وحيد (Marwa Pulse في المرحلة 2)
        لتفادي التنفيذ المزدوج لنفس الأمر عند تعدد الساحبين."""
        log(f"daemon starting interval={interval}s no_pull={no_pull}")
        while True:
            try:
                self.push_mirror()
            except Exception as exc:
                log(f"push_mirror error: {exc}", "ERROR")
            if not no_pull:
                try:
                    res = self.pull_queue()
                    if res["pending"]:
                        log(f"pull_queue applied={len(res['applied'])} failed={len(res['failed'])}")
                except Exception as exc:
                    log(f"pull_queue error: {exc}", "ERROR")
            time.sleep(interval)


def _main() -> int:
    ap = argparse.ArgumentParser(description="Hermes cloud sync")
    ap.add_argument("--push-once", action="store_true")
    ap.add_argument("--pull-once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--no-pull", action="store_true",
                    help="daemon: الدفع فقط (سحب الأوامر لمشرف وحيد — Pulse)")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL)
    ap.add_argument("--query-client", type=str)
    ap.add_argument("--query-product", type=str)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    try:
        env = load_env()
        mgr = HermesSyncManager(env=env)
        if args.push_once:
            print(json.dumps(mgr.push_mirror(), ensure_ascii=False, indent=2))
        elif args.pull_once:
            print(json.dumps(mgr.pull_queue(limit=args.limit), ensure_ascii=False, indent=2))
        elif args.query_client:
            rows = mgr.query_clients(args.query_client, args.limit)
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        elif args.query_product:
            rows = mgr.query_products(args.query_product, args.limit)
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        elif args.daemon:
            mgr.run_daemon(interval=args.interval, no_pull=args.no_pull)
        else:
            ap.print_help()
            return 2
        return 0
    except Exception as exc:
        log(f"fatal: {exc}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(_main())
