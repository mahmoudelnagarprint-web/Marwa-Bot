#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سكربت الاستعلام الموحّد — إجمالي المديونيات الحية اليوم.

المصدر: المصدر الرسمي الحي الوحيد (``G:\\ai\\Elnagar POS\\pos_data.db``) عبر
طبقة الربط المركزية ``config/data_source.py``. أي مسار SQLite قديم = رفض صريح.

التعريف الرسمي للمديونية (من كود التطبيق الحي `G:\\ai\\Elnagar POS\\app.py` 1655/1712):
    SELECT COUNT(*) AS debt_clients_count, IFNULL(SUM(balance), 0) AS total_receivables
    FROM clients WHERE balance > 0

الاستخدام:
    python tools\\debt_total.py                 # التقرير العربي
    python tools\\debt_total.py --json          # للإدماج الآلي
    python tools\\debt_total.py --top 10        # أعلى المدينين (بلا هواتف)
    python tools\\debt_total.py --db <مسار>      # مسار رسمي بديل (يُرفض أي مسار قديم)

رموز الخروج: 0 = نجاح | 2 = رفض مصدر قديم | 3 = فشل تحقق (الرقم لا يطابق المتوقع)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VISION_LAB = Path(__file__).resolve().parent.parent
if str(VISION_LAB) not in sys.path:
    sys.path.insert(0, str(VISION_LAB))

from config import data_source as ds  # noqa: E402


def build_report(args: argparse.Namespace) -> dict:
    info = ds.describe()
    totals = ds.debt_totals(path=args.db)
    rows = ds.debtors(limit=args.top, path=args.db) if args.top else []
    expected = ds.load_config().get("expected_debt") or {}
    exp_val = expected.get("total_receivables")
    match = None
    if exp_val is not None:
        match = (abs(totals["total_receivables"] - float(exp_val)) < 0.005
                 and totals["debt_clients_count"] == int(expected.get("debt_clients_count", -1)))
    freshness = ds.query_one("SELECT MAX(date) AS last_order_date, MAX(id) AS last_order_id FROM orders",
                             path=args.db)
    return {
        "source": totals["source"],
        "verdict": info["verdict"],
        "sql": totals["sql"],
        "debt_clients_count": totals["debt_clients_count"],
        "total_receivables_egp": totals["total_receivables"],
        "expected": expected or None,
        "matches_expected": match,
        "data_freshness": freshness,
        "debtors": rows,
    }


def print_report(rep: dict) -> None:
    print("═" * 62)
    print("  إجمالي المديونيات الحية — المصدر الرسمي الحي")
    print("═" * 62)
    print(f"  المصدر                : {rep['source']}")
    print(f"  تصنيف المصدر          : {rep['verdict']}")
    print(f"  بيانات آخر طلب        : #{rep['data_freshness'].get('last_order_id')} "
          f"بتاريخ {rep['data_freshness'].get('last_order_date')}")
    print("  الاستعلام الرسمي      :")
    print(f"    {rep['sql']}")
    print("─" * 62)
    print(f"  عدد العملاء المدينين  : {rep['debt_clients_count']}")
    print(f"  إجمالي المديونيات     : {rep['total_receivables_egp']} جنيه")
    if rep["matches_expected"] is not None:
        verdict = "مطابق ✔" if rep["matches_expected"] else "غير مطابق ✖"
        print(f"  التطابق مع المرجع     : {verdict} (المتوقع {rep['expected']})")
    if rep["debtors"]:
        print("─" * 62)
        print("  أعلى المدينين (بلا أرقام هواتف):")
        for r in rep["debtors"]:
            print(f"    #{r['id']:<4} {r['name']} | {r['type']} | {r['balance']} جنيه")
    print("═" * 62)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="إجمالي المديونيات الحية من المصدر الرسمي الحي")
    ap.add_argument("--json", action="store_true", help="إخراج JSON")
    ap.add_argument("--top", type=int, default=0, help="أعلى N مدينين (بلا هواتف)")
    ap.add_argument("--db", default=None, help="مسار رسمي بديل (يُرفض أي مسار قديم)")
    args = ap.parse_args(argv)

    try:
        rep = build_report(args)
    except ds.LegacySourceRefused as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"ok": False, "refused": True, "error": "legacy_source",
                          "path": (ds.last_violation() or {}).get("path", args.db or "")},
                         ensure_ascii=False))
        return 2

    if args.json:
        print(json.dumps({"ok": True, **rep}, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(rep)
    if args.json is False and rep["matches_expected"] is False:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())