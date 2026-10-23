#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply migration 007 to Supabase/Postgres only; never touches local POS SQLite.
This script is intentionally not executed as part of the implementation task.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

CLOUD = Path(__file__).resolve().parent
sys.path.insert(0, str(CLOUD))
sys.path.insert(0, str(CLOUD.parent))

from schema_migrator import (  # noqa: E402
    BOOTSTRAP_SQL,
    MIGRATIONS_DIR,
    _applied_cloud,
    _connect_cloud,
    _log_local,
    _split_statements,
)

TARGET = MIGRATIONS_DIR / "007_scheduled_agent_tasks.sql"


def main() -> int:
    if not TARGET.exists():
        print(f"FAIL: {TARGET} غير موجود")
        return 2
    statements = _split_statements(TARGET.read_text(encoding="utf-8"))
    try:
        conn, route = _connect_cloud()
    except Exception as exc:
        print(f"FAIL: تعذر الاتصال بالسحابة: {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    try:
        cur = conn.cursor()
        cur.execute(BOOTSTRAP_SQL)
        conn.commit()
        if TARGET.name in _applied_cloud(conn):
            print(f"SKIP: {TARGET.name} مسجّل مسبقًا في schema_migrations")
            return 0

        started = time.time()
        for statement in statements:
            cur.execute(statement)
        conn.commit()
        cur.execute(
            "INSERT INTO schema_migrations (filename, statements) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO NOTHING",
            (TARGET.name, len(statements)),
        )
        conn.commit()
        elapsed = round(time.time() - started, 2)
        _log_local(TARGET.name, "APPLIED", f"cloud-only via {route}; local POS DB untouched")
        print(f"CLOUD APPLIED: {TARGET.name} via {route} ({len(statements)} statements, {elapsed}s)")
        return 0
    except Exception as exc:
        conn.rollback()
        message = str(exc).replace("\n", " ")[:300]
        _log_local(TARGET.name, "FAILED", f"cloud: {message}")
        print(f"FAIL: {TARGET.name} rolled back: {type(exc).__name__}: {message}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
