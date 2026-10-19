# -*- coding: utf-8 -*-
"""تهيئة قاعدة PostgreSQL + pgvector لمشروع النوتبوك v2.

التشغيل (من جذر المشروع):
    python db\\migrate.py            # تطبيق المخطط كاملًا (آمن للتكرار)
    python db\\migrate.py --check   # فحص فقط: ما الجداول الموجودة؟
    python db\\migrate.py --print   # طباعة السكيمة (للصقها في Supabase SQL Editor)

السكيمة idempotent بالكامل — تشغيلها مرتين لا يكسر شيئًا ولا يفقد بيانات.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nb import config, db  # noqa: E402

SCHEMA_FILE = PROJECT_ROOT / "db" / "schema_pgvector.sql"


def _statements(sql_text: str):
    """تفكيك السكيمة لجُمل — **بمحلّل حالات مش بتقسيم أعمى على `;`**.

    ليه ده اتغيّر: التقسيم على `;` كان بيكسر أي كتلة `DO $$ ... $$`
    (جسم الدالة بيحتوي `;` جوّاه) وأي نص فيه `;` أو `%`. المحلّل ده
    بيتعامل مع:
      • `$$ … $$` و`$tag$ … $tag$` (dollar-quoting) — والنوع ده إلزامي لأي
        دالة/تريجر أو تعديل قيود مستقبلي.
      • النصوص `'…'` (مع `''` الهاربة) و`"…"` (أسماء معرّفات).
      • تعليقات `--` و`/* … */` المتداخلة.
    النص **ما بيتشالش** من الجملة المنفذة — التعليقات بتتشال من **العنوان
    المعروض** بس، فمفيش أي احتمال نحذف محتوى حقيقي بالغلط.
    """
    stmts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(sql_text)
    state = "normal"          # normal|line|block|single|double|dollar
    depth = 0                 # عمق تعليق الكتلة
    tag = ""                  # وسم الـdollar-quoting الحالي

    while i < n:
        ch = sql_text[i]
        nxt = sql_text[i + 1] if i + 1 < n else ""

        if state == "normal":
            if ch == "-" and nxt == "-":
                state = "line"
            elif ch == "/" and nxt == "*":
                state, depth = "block", 1
            elif ch == "'":
                state = "single"
            elif ch == '"':
                state = "double"
            elif ch == "$":
                m = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql_text[i:])
                if m:
                    tag, state = m.group(0), "dollar"
                    buf.append(tag)
                    i += len(tag)
                    continue
            elif ch == ";":
                stmt = "".join(buf).strip()
                if _has_code(stmt):
                    stmts.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        buf.append(ch)
        i += 1

        if state == "line":
            if ch == "\n":
                state = "normal"
        elif state == "block":
            if ch == "/" and nxt == "*":
                buf.append(nxt)
                i += 1
                depth += 1
            elif ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 1
                depth -= 1
                if depth == 0:
                    state = "normal"
        elif state == "single":
            if ch == "'":
                if nxt == "'":          # '' = علامة تنصيص هاربة
                    buf.append(nxt)
                    i += 1
                else:
                    state = "normal"
        elif state == "double":
            if ch == '"':
                if nxt == '"':
                    buf.append(nxt)
                    i += 1
                else:
                    state = "normal"
        elif state == "dollar":
            if "".join(buf[-len(tag):]) == tag and len(buf) > len(tag):
                state = "normal"

    tail = "".join(buf).strip()
    if _has_code(tail):
        stmts.append(tail)
    return stmts


def _has_code(stmt: str) -> bool:
    """هل الجملة فيها كود حقيقي (مش تعليقات/فراغات بس)؟"""
    s = re.sub(r"/\*.*?\*/", " ", stmt, flags=re.S)
    lines = [ln for ln in s.splitlines()
             if ln.strip() and not ln.strip().startswith("--")]
    return bool("".join(lines).strip())


def _head(stmt: str, width: int = 70) -> str:
    """أول سطر مفيد من الجملة (تخطّي التعليقات) — للعرض بس."""
    for ln in stmt.splitlines():
        t = ln.strip()
        if t and not t.startswith("--") and not t.startswith("/*"):
            return " ".join(t.split())[:width]
    return " ".join(stmt.split())[:width]


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
            head = _head(stmt)
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
