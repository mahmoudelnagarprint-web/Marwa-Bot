#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""parity_watchdog — حارس التطابق المزدوج (Parity Watchdog) — أمر المالك 2026-10-13 (مستوى 1، مقبول).

الفكرة (اقتراح معتمد):
  قراءة فقط (قراءة 100%): حساب مقاييس المحلي pos_data.db (mode=ro) ومرآة Supabase —
  للأرقام الخمسة (clients/products/orders/order_items/transactions):
    count لكل جدول + مجموع الأرصدة + مجموع المخزون (stock_qty) + max(id) + آخر طلب.
  المقارنة تعرض فرق = فارق حقيقي (Diff) ويُكتب في memory/reports/parity-YYYY-MM-DD-HHMM.md + ملخص موجز.

القواعد الملتزم بها:
  - pos_data.db تُفتح بِ WAL? لا — mode=ro فقط (لا كتابة). لا SQL write.
  - مقارنة على مقياس NOT على صفوف كاملة — أرقام مجمّع (count / sums / max) لا تنقل (superset) لا نقل الصفوف.
  - انسخ من نفس النمط: DB mode=ro عبر uri=file:...?mode=ro. لا اتصال ro إلى supabase (client) للقراءة فقط.
  - .env يُقرأ بلا طباعة أي سر. لا تُطبع مفاتيح ولا تُطبع قيم.
  - الهدف الاختباري: نسخة بمقياس نسخة (نسختان الاختبار = sandbox) عند --local-db (افتراضيًا نسخة في _sandbox_pos_writer أولًا).

الاستخدام:
  python scripts\parity_watchdog.py --once                 # شغل مرة (افتراضي)
  python scripts\parity_watchdog.py --daemon --interval 60  # مراقبة كل 60 ثانية (بعد تفعيل بموافقة المالك)
  python scripts\parity_watchdog.py --local-db "_sandbox_pos_writer\pos_data.db"  # اختبار على نسخة أولًا
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows console: تأكد من UTF-8 للطباعة (cp1252 يكسر العربية/الإيموجي)
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
# مسارات — يشير السكربت افتراضيًا للحي لقراءته (قراءة فقط)
WORKSPACE = Path(__file__).resolve().parent.parent

DEFAULT_LOCAL_DB = r"G:\ai\Elnagar POS\pos_data.db"
TABLES = ["clients", "products", "orders", "order_items", "transactions"]

_LOCAL_SQL = {
    # لكل جدول: كل مقياس = SQL SUM/COUNT صريح — قراءة فقط، أعمدة الجداول الفعلية.
    "clients":      {"count": "SELECT COUNT(*) FROM clients",
                     "sum_balance": "SELECT COALESCE(SUM(balance),0) FROM clients"},
    "products":     {"count": "SELECT COUNT(*) FROM products",
                     "sum_stock_qty": "SELECT COALESCE(SUM(stock_qty),0) FROM products"},
    "orders":       {"count": "SELECT COUNT(*) FROM orders",
                     "max_id": "SELECT COALESCE(MAX(id),0) FROM orders",
                     "sum_total": "SELECT COALESCE(SUM(total_amount),0) FROM orders"},
    "order_items":  {"count": "SELECT COUNT(*) FROM order_items",
                     "sum_total": "SELECT COALESCE(SUM(total),0) FROM order_items"},
    "transactions": {"count": "SELECT COUNT(*) FROM transactions",
                     "max_id": "SELECT COALESCE(MAX(id),0) FROM transactions",
                     "sum_amount": "SELECT COALESCE(SUM(amount),0) FROM transactions"},
}


def load_env(env_path: Path) -> dict:
    """load .env key=value (لا يعتمد على python-dotenv). لا print values."""
    env: dict = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k:
                env[k] = v
    return env


def local_metrics(db_path: Path) -> dict:
    """Compute local aggregate metrics. DB opened strictly read-only (mode=ro)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    snaps = {}
    try:
        for t in TABLES:
            m = {}
            for name, sql in _LOCAL_SQL[t].items():
                m[name] = conn.execute(sql).fetchone()[0]
            snaps[t] = m
    finally:
        conn.close()
    return snaps


def cloud_metrics(env: dict) -> tuple:
    """Compute cloud aggregate metrics from Supabase mirror (read only).
    Returns (snapshots dict or None, error string).
    Uses the supabase client exactly like supabase_sync.py.
    """
    url = env.get("SUPABASE_URL", "")
    key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_PUBLISHABLE_KEY", "")
    if not url or not key:
        return None, "SUPABASE_URL / SUPABASE_SECRET_KEY missing in .env"
    try:
        from supabase import create_client
        client = create_client(url, key)
    except Exception as exc:
        return None, f"supabase import/create: {type(exc).__name__}: {exc}"

    # أعمدة كل جدول في السحابة (على ما هو في TABLES_SCHEMA المتزامَنة)
    CLOUD_COLS = {
        "clients":      ["balance"],
        "products":     ["stock_qty"],
        "orders":       ["total_amount", "id"],
        "order_items":  ["total"],
        "transactions": ["amount", "id"],
    }
    AGG = {  # توزيع قيم الصفوف حسب المقياس
        "sum_balance":   lambda r: r.get("balance") or 0,
        "sum_stock_qty": lambda r: r.get("stock_qty") or 0,
        "sum_total":     lambda r: r.get("total_amount") or r.get("total") or 0,
        "sum_amount":    lambda r: r.get("amount") or 0,
        "max_id":        lambda r: int(r.get("id") or 0),
    }

    snaps = {}
    try:
        for t in TABLES:
            cols = ",".join(CLOUD_COLS[t])
            # pull كل الصفوف (الصفحة الأولى ثم pagination حتى نهاية الجدول)
            rows: list = []
            fetch = client.table(t).select(cols).execute().data or []
            rows += fetch
            total_so_far = len(rows)
            while len(fetch) == 1000:
                fetch = client.table(t).select(cols).range(total_so_far, total_so_far + 999).execute().data or []
                rows += fetch
                total_so_far = len(rows)
            m = {}
            m["count"] = len(rows)
            for name in _LOCAL_SQL[t]:
                if name == "count":
                    continue
                vals = [AGG[name](r) for r in rows]
                m[name] = round(sum(vals), 2) if name != "max_id" else (max(vals) if vals else 0)
            snaps[t] = m
        return snaps, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def compare(loc: dict, cloud: dict | None) -> list:
    """Diff each table — list of diff rows, each table OK if no diff."""
    out = []
    for t in TABLES:
        lm = loc.get(t, {})
        cm = cloud.get(t, {}) if cloud else {}
        diffs = {}
        for name in _LOCAL_SQL[t]:
            a = lm.get(name, 0)
            b = cm.get(name, None)
            if b is None:
                diffs[name] = {"local": a, "cloud": None, "note": "cloud missing (no env)"}
                continue
            if abs(a - b) > 1e-6:
                diffs[name] = {"local": a, "cloud": b, "delta": round(b - a, 2)}
        out.append({"table": t, "ok": not diffs, "diff": diffs})
    return out


def render_md(ts: str, res: dict) -> str:
    lines = [f"# تقرير التطابق — {ts}", ""]
    ok_all = True
    for row in res["diff"]:
        t = row["table"]
        if row["ok"]:
            lines.append(f"- ✅ {t}: مطابق")
            continue
        ok_all = False
        lines.append(f"- ❌ {t}: " + "; ".join(f"{k}={v}" for k, v in row["diff"].items()))
    lines.append("")
    lines.append("## ملخص الأرقام")
    for t in TABLES:
        lines.append(f"- {t}: {json.dumps(res['local'][t], ensure_ascii=False)} (local)")
    lines.append("")
    lines.append("## الحالة")
    lines.append("**مطابق**" if ok_all else "**فجوة — راجع الفرق أعلاه**")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Parity Watchdog — حارس التطابق المزدوج")
    ap.add_argument("--once", action="store_true", help="شغّل مرة واحدة (افتراضي)")
    ap.add_argument("--daemon", action="store_true", help="شغّل بشكل مستمر")
    ap.add_argument("--interval", type=int, default=60, help="ثوانٍ بين دورات الـ daemon")
    ap.add_argument("--local-db", default=DEFAULT_LOCAL_DB, help="مسار pos_data.db (افتراضي الحي)")
    ap.add_argument("--env", default=str(Path(r"G:\ai\Elnagar POS\.env")), help="مسار .env")
    ap.add_argument("--json-out", default="", help="مسار لملف JSON للـ snapper (فارغ=لا)")
    ap.add_argument("--report-every", type=int, default=60,
                    help="كل كم دورة نكتب تقرير markdown (افتراضي 60 = كل ساعة عند interval=60)")
    ap.add_argument("--log", default="", help="مسار ملف سجل نصي إضافي (داemon)")
    args = ap.parse_args()

    local_path = Path(args.local_db)
    if not local_path.exists():
        print(json.dumps({"error": f"local db not found: {local_path}"}, ensure_ascii=False))
        return 1

    env = load_env(Path(args.env))
    if not env.get("SUPABASE_URL") or not (env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_PUBLISHABLE_KEY")):
        print(json.dumps({"error": "SUPABASE_URL / key missing in .env"}, ensure_ascii=False))
        return 1

    def _logline(s: str) -> None:
        if args.log:
            try:
                Path(args.log).parent.mkdir(parents=True, exist_ok=True)
                with open(args.log, "a", encoding="utf-8") as fh:
                    fh.write(s + "\n")
            except Exception:
                pass

    cycle = 0
    last_matched = None
    while True:
        cycle += 1
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        loc = local_metrics(local_path)
        cloud, cerr = cloud_metrics(env)
        if cloud is None:
            msg = json.dumps({"time": ts, "error": cerr}, ensure_ascii=False)
            print(msg)
            _logline(msg)
            if not args.daemon:
                return 1
            time.sleep(args.interval)
            continue

        res = {
            "time": ts,
            "local_db": str(local_path),
            "local": loc,
            "cloud": cloud,
            "diff": compare(loc, cloud),
            "matched": all(r["ok"] for r in compare(loc, cloud)),
        }
        summary = {r["table"]: "✅" if r["ok"] else "❌ " + json.dumps(r["diff"], ensure_ascii=False) for r in res["diff"]}

        # في الوضع الدائم: اطبع فقط عند تغيّر الحالة (تفادي ضجيج الخلفية)
        changed = res["matched"] != last_matched
        if changed or not args.daemon:
            msg = json.dumps({"time": ts, "matched": res["matched"], "summary": summary}, ensure_ascii=False)
            print(msg)
            _logline(msg)
        last_matched = res["matched"]

        # تقرير markdown دوري (كل report-every دورة، أو عند تغيّر الحالة)
        md = render_md(ts, res)
        reports_dir = WORKSPACE / "memory" / "reports"
        want_report = (not args.daemon) or changed or (args.report_every and cycle % args.report_every == 0)
        if reports_dir.is_dir() and want_report:
            fname = reports_dir / f"parity-{datetime.now().strftime('%Y-%m-%d-%H%M')}.md"
            fname.write_text(md, encoding="utf-8")
            # أبقي آخر حالة في ملف ثابت parity-LATEST.md ليسهل استعراضه
            (reports_dir / "parity-LATEST.md").write_text(md, encoding="utf-8")
            print(f"[report] {fname}")
            _logline(f"report {fname}")

        if args.json_out:
            Path(args.json_out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"[json] {args.json_out}")

        if not args.daemon:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
