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


def out(*parts, **kw) -> None:
    """طباعة عربية آمنة على أي كونسول (ويندوز cp1252 مش بيفهم العربي).

    من غير الدالة دي `print` بيرمي `UnicodeEncodeError` على كونسول
    ويندوز الافتراضي وبيوقّف السكربت كله — يعني **أداة الميجراسيون
    مش موجودة عمليًا** عند المالك. هنا بنحاول الترميز الحالي، ولو فشل
    بنسقط لـ`backslashreplace` (بنطبع التمثيل الآمن بدل ما نقع).

    ملاحظة: دي **طباعة بس** — قراءة السكيمة وتنفيذها بـUTF-8 زي ما هما،
    ومفيش أي تحويل لملف السكيمة نفسه.
    """
    text = " ".join(str(p) for p in parts)
    stream = kw.get("file", sys.stdout)
    try:
        print(text, file=stream, **{k: v for k, v in kw.items() if k != "file"})
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "ascii"
        safe = text.encode(enc, "backslashreplace").decode(enc, "replace")
        print(safe, file=stream, **{k: v for k, v in kw.items() if k != "file"})


def schema_statements() -> List[str]:
    """جمل السكيمة كما بيطلعها المقسّم (للاستخدام في `check` و`apply`)."""
    return list(_statements(SCHEMA_FILE.read_text(encoding="utf-8")))


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

    ملاحظة مهمة (مقيسة، مش مفترضة): السكيمة الحالية `schema_pgvector.sql`
    فيها **صفر** `$$` · **صفر** كتل `DO` · **صفر** دوال · **صفر** فاصلة
    منقوطة داخل نص · **صفر** تعليقات كتلية — فالمقسّم الساذج القديم كان
    بيطلع **نفس الـ52 جملة** بالظبط. يعني الفايدة هنا **مستقبلية ودفاعية**:
    أول ما يُضاف تريجر أو دالة أو نص فيه `;` المقسّم القديم كان هيكسر
    بصمت، والجديد بيمنع ده من أصله. مش إصلاح لعطل حاضر.
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


def _created_tables(stmts) -> List[str]:
    """أسماء الجداول اللي السكيمة بتنشئها (للمقارنة بالواقع)."""
    names: List[str] = []
    for s in stmts:
        m = re.search(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
                      r'(?:"?public"?\s*\.\s*)?"?([A-Za-z_][A-Za-z0-9_]*)"?',
                      s, flags=re.I)
        if m:
            names.append(m.group(1))
    return names


def check() -> int:
    """فحص: عدد جمل السكيمة ↔ عدد جداول القاعدة، مع تحذير ظاهر عند الاختلاف."""
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")
    stmts = list(_statements(sql_text))
    created = _created_tables(stmts)

    try:
        tables = db.q(
            """SELECT table_name FROM information_schema.tables
               WHERE table_schema = 'public' ORDER BY table_name"""
        )
    except Exception as exc:  # noqa: BLE001
        out(f"✖ مش قادر أقرأ الجداول: {type(exc).__name__}: {exc}")
        return 1
    present = [t["table_name"] for t in tables]

    out("=" * 66)
    out(f"  فحص السكيمة على {config.DB_DSN_HOST}")
    out("=" * 66)
    out(f"  جمل السكيمة (المقسّم) : {len(stmts)}")
    out(f"  جداول في السكيمة      : {len(created)}")
    out(f"  جداول في القاعدة      : {len(present)}")

    # --- الاتفاق بين السكيمة والقاعدة (تحذير ظاهر، مش دفن) ---
    missing = sorted(set(created) - set(present))   # في السكيمة ومش في القاعدة
    extra = sorted(set(present) - set(created))     # في القاعدة ومش في السكيمة

    out("")
    if missing:
        out(f"  ⚠ تحذير: {len(missing)} جدول في السكيمة ومش موجود في القاعدة:")
        for n in missing:
            out(f"      • {n}    ← نفّذ: python db\\migrate.py")
    else:
        out("  ✔ كل جداول السكيمة موجودة في القاعدة")

    if extra:
        out(f"  ℹ ملاحظة: {len(extra)} جدول في القاعدة مش من السكيمة "
            f"(بيوته مشروع تاني على نفس القاعدة):")
        for n in sorted(extra):
            out(f"      • {n}")

    out("")
    out(f"  الحصيلة: {'سكيمة متطابقة' if not missing else 'ناقصة — محتاجة تطبيق'}")
    out("=" * 66)
    for n in present:
        out(f"  • {n}")
    return 0 if not missing else 1


def apply() -> int:
    sql_text = SCHEMA_FILE.read_text(encoding="utf-8")
    stmts = list(_statements(sql_text))
    out(f"تطبيق {len(stmts)} جملة على {config.DB_DSN_HOST} ...")
    done, failed = 0, 0
    conn = db.connect()
    try:
        cur = conn.cursor()
        for stmt in stmts:
            head = _head(stmt)
            try:
                cur.execute(stmt)
                done += 1
                out(f"  ✔ {head}")
            except Exception as exc:
                failed += 1
                out(f"  ✖ {head}\n      ↳ {type(exc).__name__}: {exc}")
                raise
        conn.commit()
        out(f"تم: {done} جملة نُفذت بنجاح.")
        out("تلميح: لو فشل CREATE EXTENSION فنفّذ السكيمة من Supabase SQL Editor بصلاحية postgres.")
        return 0
    finally:
        conn.close()


def _emit_schema() -> None:
    """يطبع السكيمة خام **بايت-بايت** بغضّ النظر عن ترميز الكونسول.

    ليه من `print`: السكيمة فيها تعليقات عربية كتير، وأي طباعة بتمر على
    ترميز الكونسول (cp1252 على ويندوز) بترمي `UnicodeEncodeError`. ولأن
    الغرض من `--print` هو اللصق في Supabase SQL Editor، لازم المخرج يطلع
    **UTF-8 سليم بالكامل** — فبنكتب في `stdout.buffer` مباشرة، وبنلفّ
    stdout نفسه لـUTF-8 كاحتياط لو الـbuffer مش متاح.
    """
    data = SCHEMA_FILE.read_bytes()
    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write(data)
        buf.flush()
        return
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    sys.stdout.write(data.decode("utf-8"))
    sys.stdout.flush()


def main(argv=None) -> int:
    args = set(sys.argv[1:] if argv is None else argv)
    if "--print" in args:
        _emit_schema()
        return 0
    if "--check" in args:
        return check()
    return apply()


if __name__ == "__main__":
    sys.exit(main())
