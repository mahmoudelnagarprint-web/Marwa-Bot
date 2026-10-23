#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""apply_006_cloud — تطبيق migration 006 على السحابة فقط (Postgres).
لا يلمس القاعدة المحلية الحية إطلاقاً (بوابة POS_LIVE_WRITE تبقى مقفلة).

بأمر المالك 2026-10-20 (الميثاق المعماري لواجهة MARWA CORE):
جداول agent_tasks + agent_updates + RLS + سياسات anon + Realtime publication.

  * يقرأ 006_agent_workspace.sql
  * يتصل بالسحابة عبر المسار الرسمي (POOLER_URL ثم DIRECT_URL — _connect_cloud)
  * أسطر "alter publication ... add table" متسامحة إزاء "already member".
  * يسجّل في schema_migrations + applied_migrations.log (cloud-only)
  * يتحقق: الجداول موجودة؟ RLS؟ أعضاء publication؟ السياسات منشأة؟
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

CLOUD = Path(__file__).resolve().parent
sys.path.insert(0, str(CLOUD))
sys.path.insert(0, str(CLOUD.parent))

from schema_migrator import (  # noqa: E402  — مسار التطبيق الرسمي
    BOOTSTRAP_SQL,
    MIGRATIONS_DIR,
    _applied_cloud,
    _connect_cloud,
    _log_local,
    _split_statements,
)

TARGET = MIGRATIONS_DIR / "006_agent_workspace.sql"


def check_pub_membership(cur) -> set:
    cur.execute(
        "SELECT pubname, tablename FROM pg_publication_tables "
        "WHERE pubname='supabase_realtime' ORDER BY tablename")
    return {r[1] for r in cur.fetchall()}


def check_rls(cur) -> dict:
    cur.execute(
        "SELECT tablename, rowsecurity FROM pg_tables "
        "WHERE schemaname='public' AND tablename IN ('agent_tasks','agent_updates')")
    return {r[0]: bool(r[1]) for r in cur.fetchall()}


def check_policies(cur) -> dict:
    cur.execute(
        "SELECT tablename, count(*) FROM pg_policies "
        "WHERE schemaname='public' AND tablename IN ('agent_tasks','agent_updates') "
        "GROUP BY tablename")
    return {r[0]: int(r[1]) for r in cur.fetchall()}


def _verify(cur) -> bool:
    members = check_pub_membership(cur)
    rls = check_rls(cur)
    pols = check_policies(cur)
    print("---- تحقق (غرفة الوكيل — جداول الوكلاء) ----")
    ok = True
    for t in ("agent_tasks", "agent_updates"):
        exists = t in rls
        in_pub = t in members
        n_pol = pols.get(t, 0)
        print(f"{t}: وجود={'نعم' if exists else 'لا ❌'}  "
              f"RLS={'مفعّل ✅' if rls.get(t) else 'غير مفعّل ❌'}  "
              f"policies={n_pol}  realtime_member={'نعم ✅' if in_pub else 'لا ❌'}")
        ok = ok and exists and bool(rls.get(t)) and in_pub
    print("تحقق نهائي: الجداول + RLS + Realtime publication سليمة ✅" if ok
          else "تحقق: نقص في عنصر أو أكثر ❌")
    return ok


def main() -> int:
    if not TARGET.exists():
        print(f"FAIL: {TARGET} غير موجود")
        return 2
    sql = TARGET.read_text(encoding="utf-8")
    stmts = _split_statements(sql)

    try:
        conn, route = _connect_cloud()
    except Exception as exc:
        print(f"FAIL: سحابة غير قابلة للوصول -> {type(exc).__name__}: {str(exc)[:160]}")
        return 2

    try:
        cur = conn.cursor()
        cur.execute(BOOTSTRAP_SQL)
        conn.commit()

        if TARGET.name in _applied_cloud(conn):
            print(f"SKIP: {TARGET.name} مسجّل سلفاً في schema_migrations — ومستثنى")
            return 0 if _verify(cur) else 1

        started = time.time()
        tolerant = 0
        for i, stmt in enumerate(stmts, 1):
            try:
                cur.execute(stmt)
            except Exception as exc:
                msg = str(exc)
                upper = stmt.upper()
                if "ALTER PUBLICATION" in upper and ("already member" in msg.lower() or "already a member" in msg.lower()):
                    print(f"  — متسامح: جملة {i} ({upper[:40]}…) -> عضواً سلفاً ({msg[:80]}…)")
                    tolerant += 1
                    continue
                raise
        conn.commit()
        secs = round(time.time() - started, 2)

        cur.execute(
            "INSERT INTO schema_migrations (filename, statements) VALUES (%s, %s) "
            "ON CONFLICT (filename) DO NOTHING",
            (TARGET.name, len(stmts)),
        )
        conn.commit()
        print(f"CLOUD APPLIED: {TARGET.name} via {route} (committed in {secs}s, "
              f"~{len(stmts)} statements, {tolerant} publication tolerant-skip)")
        _log_local(TARGET.name, "APPLIED", f"cloud-only via {route} (local LIVE untouched by design)")

        return 0 if _verify(cur) else 1
    except Exception as exc:
        conn.rollback()
        msg = str(exc).replace("\n", " ")[:300]
        print(f"FAIL: {TARGET.name} CLOUD rolled back -> {type(exc).__name__}: {msg}")
        _log_local(TARGET.name, "FAILED", f"cloud: {msg}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
