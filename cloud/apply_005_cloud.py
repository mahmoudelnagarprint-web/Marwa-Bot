#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""apply_005_cloud — تطبيق migration 005 على السحابة فقط (Postgres).
لا يلمس القاعدة المحلية الحية إطلاقاً (بوابة POS_LIVE_WRITE تبقى مقفلة).

  * يقرأ 005_pulse_realtime.sql
  * يتصل بالسحابة عبر المسار الرسمي (POOLER_URL ثم DIRECT_URL — _connect_cloud)
  * ينفّذ الجُمل: إنشاء sync_events/applied_ops + RLS + publication.
    — سطرا "alter publication ... add table" متسامحان إزاء "already member"
      (خطأ التكرار الوحيد المتوقع؛ أي خطأ آخر ×= فشل المعاملة كلها).
  * يسجّل في schema_migrations (جدول السجل السحابي) + applied_migrations.log
  * يتحقق: الجداول موجودة؟ rowsecurity مفعّل؟ أعضاء publication؟
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

TARGET = MIGRATIONS_DIR / "005_pulse_realtime.sql"


def check_pub_membership(cur) -> dict:
    cur.execute(
        "SELECT pubname, tablename FROM pg_publication_tables "
        "WHERE pubname='supabase_realtime' ORDER BY tablename")
    rows = {r[1] for r in cur.fetchall()}
    return rows


def check_rls(cur) -> dict:
    cur.execute(
        "SELECT tablename, rowsecurity FROM pg_tables "
        "WHERE schemaname='public' AND tablename IN ('sync_events','applied_ops')")
    return {r[0]: bool(r[1]) for r in cur.fetchall()}


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
            _verify(cur)
            return 0

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

        _verify(cur)
        return 0
    except Exception as exc:
        conn.rollback()
        msg = str(exc).replace("\n", " ")[:300]
        print(f"FAIL: {TARGET.name} CLOUD rolled back -> {type(exc).__name__}: {msg}")
        _log_local(TARGET.name, "FAILED", f"cloud: {msg}")
        return 1
    finally:
        conn.close()


def _verify(cur) -> None:
    members = check_pub_membership(cur)
    rls = check_rls(cur)
    print("---- تحقق (حسب التصميم: applied_ops دفتر تكرار لا يُبث) ----")
    for t in ("sync_events", "applied_ops"):
        in_pub = t in members
        need_pub = (t == "sync_events")                      # applied_ops بلا بث عمداً
        print(f"{t}: وجود={'نعم' if t in rls else 'لا'}  "
              f"RLS={'مفعّل ✅' if rls.get(t) else 'غير مفعّل ❌'}  "
              f"realtime_member={'نعم ✅' if in_pub else ('لا (متعمد — غير مطلوب) ✅' if not need_pub else 'لا ❌')}")
    print(f"commands: realtime_member={'نعم ✅' if 'commands' in members else 'لا ❌'}")
    bad = (("sync_events" not in rls or not rls.get("sync_events") or "sync_events" not in members)
           or ("applied_ops" not in rls or not rls.get("applied_ops"))
           or "commands" not in members)
    print("تحقق: RLS deny-by-default + Realtime publication سليمان ✅" if not bad
          else "تحقق: نقص في عنصر أو أكثر ❌")


if __name__ == "__main__":
    sys.exit(main())
