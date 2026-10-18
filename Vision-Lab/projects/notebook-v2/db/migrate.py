# -*- coding: utf-8 -*-
"""تهيئة قاعدة PostgreSQL + pgvector لمشروع النوتبوك v2.

التشغيل (من جذر المشروع):
    python db\\migrate.py            # تطبيق المخطط كاملًا (آمن للتكرار)
    python db\\migrate.py --check   # فحص فقط: ما الجداول الموجودة؟
    python db\\migrate.py --print   # طباعة السكيمة (للصقها في Supabase SQL Editor)

السكيمة idempotent بالكامل — تشغيلها مرتين لا يكسر شيئًا ولا يفقد بيانات.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nb import config, db  # noqa: E402

SCHEMA_FILE = PROJECT_ROOT / "db" / "schema_pgvector.sql"


def _statements(sql_text: str):
    """تفكيك السكيمة لجُمل منفذة (لا توجد دوال/تريجر في السكيمة — التقسيم على ; آمن)."""
    for raw in sql_text.split(";"):
        kept = [ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if kept:
            yield "\n".join(kept)


def check() -> int:
    tables = db.q(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = 'public' ORDER BY table_name"""
    )
    names = [t["table_name"] for t in tables]
    print(f"الجداول الموجودة في {config.DB_DSN_HOST}: {len(names)}")
    for n in names:
        print(f"  • {n}")
    return 0


def apply() -> int:
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")
    stmts = list(_statements(sql_text))
    print(f"تطبيق {len(stmts)} جملة على {config.DB_DSN_HOST} ...")
    done, failed = 0, 0
    conn = db.connect()
    try:
        cur = conn.cursor()
        for stmt in stmts:
            head = " ".join(stmt.split())[:70]
            try:
                cur.execute(stmt)
                done += 1
                print(f"  ✔ {head}")
            except Exception as exc:
                failed += 1
                print(f"  ✖ {head}\n      ↳ {type(exc).__name__}: {exc}")
                raise
        conn.commit()
        print(f"تم: {done} جملة نُفذت بنجاح.")
        print("تلميح: لو فشل CREATE EXTENSION فنفّذ السكيمة من Supabase SQL Editor بصلاحية postgres.")
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    args = set(sys.argv[1:] if argv is None else argv)
    if "--print" in args:
        print(SCHEMA_FILE.read_text(encoding="utf-8"))
        return 0
    if "--check" in args:
        return check()
    return apply()


if __name__ == "__main__":
    sys.exit(main())
