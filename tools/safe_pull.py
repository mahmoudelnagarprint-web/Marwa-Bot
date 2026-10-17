#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarwaBot Auto-Pull (safe) — scheduled task 'MarwaBot_AutoPull'
Owner order 2026-10-17 (evening): refresh the local mirror from the Supabase
cloud every 15 minutes on the LAPTOP, with hard safety gates.

Cloud access: POOLER_URL postgres credentials from .env (READ-ONLY session).
The REST/API-key path is currently broken on this node (sb_secret -> 401,
publishable -> RLS-filtered empties on the five business tables), so the
pooler is the reliable path (verified 2026-10-17 morning intervention).

SAFETY GATES — lesson from the 2026-10-17 morning incident where a blind
full rebuild zeroed the mirror when REST returned empty sets:
  GATE 1  every business table must be NON-empty in the cloud
  GATE 2  cloud transactions count >= local count
          AND cloud max(tx date) >= local max(tx date)
  GATE 3  post-import transaction count must equal the fetched count,
          otherwise the rolling backup is restored automatically.

On pass: rolling backup -> rebuild the 7 mirror tables + daily_shifts/settings
(from the brain-vault local_state_json) -> verify -> log.
On fail: log ERROR and touch NOTHING.

Log   : G:/Marwa-Bot/logs/autopull.log        (gitignored)
Backup: G:/Marwa-Bot/backup/autopull_prev.db  (rolling, per run)
Exit   : 0 ok | 1 config | 2 gate1 | 3 gate2 | 4 gate3
"""
import datetime as _dt
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"G:\Marwa-Bot")
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))

import laptop_sync as LS          # designed engine (owner order 2026-10-14)
import psycopg2
import psycopg2.extras

LOG = ROOT / "logs" / "autopull.log"
BACKUP = ROOT / "backup" / "autopull_prev.db"
BUSINESS = ("clients", "products", "orders", "order_items", "transactions")


def log(msg, level="INFO"):
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "%s [%s] %s" % (ts, level, msg)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def _norm(v):
    """psycopg2 returns datetime objects; sqlite wants ISO strings."""
    if isinstance(v, _dt.datetime):
        return v.isoformat()
    if isinstance(v, (_dt.date, _dt.time)):
        return v.isoformat()
    return v


def _iso(s):
    return str(s or "").replace(" ", "T")[:19]


def local_stats():
    if not LS.DB_PATH.exists():
        return 0, ""
    conn = sqlite3.connect("file:%s?mode=ro" % LS.DB_PATH, uri=True)
    try:
        r = conn.execute("SELECT COUNT(*), COALESCE(MAX(date), '') FROM transactions").fetchone()
        return int(r[0]), _iso(r[1])
    finally:
        conn.close()


def main():
    env = LS.load_env()
    pooler = env.get("POOLER_URL") or env.get("DIRECT_URL")
    if not pooler:
        log("FATAL: POOLER_URL/DIRECT_URL missing in .env", "ERROR")
        return 1

    pconn = psycopg2.connect(pooler, connect_timeout=15)
    pconn.set_session(readonly=True, autocommit=True)
    pcur = pconn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    counts = {}
    for t in LS.MIRROR_TABLES:
        pcur.execute('SELECT COUNT(*) AS n FROM "%s"' % t)
        counts[t] = int(pcur.fetchone()["n"])
    pcur.execute("SELECT COALESCE(MAX(date)::text, '') AS d FROM transactions")
    cloud_max = _iso(pcur.fetchone()["d"])

    nloc, lmax = local_stats()
    log("cloud counts=%s | cloud_max_tx=%s | local tx=%d | local_max_tx=%s"
        % (counts, cloud_max, nloc, lmax))

    empty = [t for t in BUSINESS if counts.get(t, 0) == 0]
    if empty:
        log("GATE1 FAIL: cloud business tables empty: %s — abort (mirror untouched)" % empty, "ERROR")
        pconn.close()
        return 2
    if counts["transactions"] < nloc:
        log("GATE2 FAIL: cloud tx (%d) < local tx (%d) — abort" % (counts["transactions"], nloc), "ERROR")
        pconn.close()
        return 3
    if cloud_max < lmax:
        log("GATE2 FAIL: cloud max (%s) older than local max (%s) — abort" % (cloud_max, lmax), "ERROR")
        pconn.close()
        return 3

    if LS.DB_PATH.exists():
        shutil.copyfile(str(LS.DB_PATH), str(BACKUP))
        log("rolling backup -> %s" % BACKUP.name)

    conn = sqlite3.connect(str(LS.DB_PATH))
    try:
        for table in LS.MIRROR_TABLES:
            pcur.execute('SELECT * FROM "%s"' % table)
            rows = [{k: _norm(v) for k, v in dict(r).items()} for r in pcur.fetchall()]
            info = LS._seed_table(conn, table, rows)
            log("pull %-16s %4d rows" % (table, info["rows"]))
        pcur.execute("SELECT value FROM system_brain_sync WHERE key=%s", (LS.VAULT_KEY_STATE,))
        row = pcur.fetchone()
        if row and row.get("value"):
            state = json.loads(row["value"])
            for table in ("daily_shifts", "settings"):
                info = LS._seed_table(conn, state.get(table) or [])
                log("state %-12s %d rows" % (table, info["rows"]))
        else:
            log("vault local_state_json missing — daily_shifts/settings kept", "WARN")
    finally:
        conn.close()
    pconn.close()

    n2, lmax2 = local_stats()
    if n2 != counts["transactions"]:
        log("GATE3 FAIL: local tx=%d != cloud tx=%d — restoring rolling backup"
            % (n2, counts["transactions"]), "ERROR")
        shutil.copyfile(str(BACKUP), str(LS.DB_PATH))
        return 4
    log("OK: mirror refreshed (tx=%d, max=%s)" % (n2, lmax2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
