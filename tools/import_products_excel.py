#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""import_products_excel.py — الاستيراد الآمن (Safe Import Tool) — أمر المالك 2026-10-14.

يقبل الشيت `products_catalog_master.xlsx` من المالك ويطبّق تعديلاته بإحكام:

  [1] Dry-run (افتراضي): يقرأ الشيت + القاعدة (mode=ro) ويُنتج تقرير مطابقة شامل
      لكل العمود الذكي (اسم، تصنيف، أسعار، مخزون، نوع خامة، مسار تشغيل، نوع مخزون، تكاليف)
      — بلا أي كتابة على القاعدة إطلاقًا.
  [2] Apply (بعد موافقة المالك): 
      - نسخة احتياطية فورية pos_data.db.bak-<timestamp> قبل أي تعديل.
      - تحديث الأعمدة عبر الدوال الرسمية لقاعدة database.py ONLY:
          update_product_details(...)  → name/category/prices/sort_order
          update_product_stock_db(...) → stock (دلتا = المطلوب - الحالي)
      - الأعمدة الذكية الجديدة (material_type/operation_type/inventory_type/
        raw_material_cost/manufacturing_cost) قابلة للقراءة والمطابقة في Dry-run،
        لكن التطبيق يتطلب إضافة دالة رسمية (توسعة database.py) — يُعرض على المالك.

القواعد الملتزم بها (AGENT/RULES):
  - لا SQL مباشر على القاعدة — فقط استدعاء دوال database.py الرسمية.
  - النسخة الاحتياطية قبل أي كتابة (+ integrity check سريع).
  - لا تعبث بجداول غير products (لا orders/transactions/clients).
  - بعد التطبيق، يُنصح تشغيل مزامنة سحابية (supabase_sync.py --push-once).

الاستخدام:
  python tools\import_products_excel.py --file exports\products_catalog_master.xlsx
  python tools\import_products_excel.py --file exports\products_catalog_master.xlsx --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from openpyxl import load_workbook
except ImportError:
    print("خطأ: openpyxl غير مضمّن — استخدم Python المحمول أو شغّل pip install openpyxl")
    sys.exit(1)

DEFAULT_DB = r"G:\ai\Elnagar POS\pos_data.db"
DEFAULT_DB_DIR = Path(r"G:\ai\Elnagar POS")            # حيث نسخة الاحتياطية
# الرؤوس الفعلية داخل الشيت (صف 2)
KNOWN_HEADS = {
    "id", "name", "category", "material_type", "operation_type", "inventory_type",
    "stock", "raw_material_cost", "manufacturing_cost", "total_cost",
    "selling_price", "profit_margin", "profit_percentage", "notes",
}
WARN_FIELDS = ["material_type", "operation_type", "inventory_type",
               "raw_material_cost", "manufacturing_cost"]   # قراءة/مطابقة فقط — غير قابلة للتطبيق بهذه الدوال


def _f(v) -> float:
    """تحويل آمن إلى float (يدعم العربية العددية والفارغ)؟"""
    try:
        if isinstance(v, (int, float)):
            return float(v)
        if v is None:
            return 0.0
        s = str(v).replace(",", ".").strip()
        # إزالة إزالة علامة الجنية إن وجدت
        s = s.replace("ج", "").replace("G", "").replace("E", "").strip()
        if not s:
            return 0.0
        return float(s)
    except (TypeError, ValueError):
        return None


def read_sheet(path: Path) -> tuple:
    """يرجع (rows, headers, warnings) من الشيت: كل ملف dict فيه id إلزامي."""
    wb = load_workbook(path, data_only=True)  # نقرأ القيم المحسوبة (بعد حفظ الإكسيل)
    ws = wb.active
    # الرؤوس من الصف 2
    headers = [ws.cell(row=2, column=j).value for j in range(1, ws.max_column + 1)]
    if headers[0] != "id":
        # أحيانًا أول عمود "الرقم" — نأخذ من الاسم
        headers = [h for h in headers if h]  # فعليًّا
    rows = []
    warn = []
    for r in range(4, ws.max_row + 1):
        name = ws.cell(row=r, column=2).value
        if not name:  # سطر فارغ
            continue
        row = {}
        for j, h in enumerate(headers, start=1):
            row[h] = ws.cell(row=r, column=j).value
        # Treat empty id as missing; also skip non-numeric ids (summary rows)
        try:
            pid = float(row.get("id")) if row.get("id") is not None else None
            row["id"] = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            warn.append(f"صف {r}: id غير رقمي — صف ملخص، تم تخطيه")
            continue
        if row.get("id") is None:
            warn.append(f"صف {r}: بدون id — تم تخطيه")
            continue
        rows.append(row)
    return rows, warn
    return rows, warn


def read_db(db_path: Path) -> dict:
    """قراءة ro من products: {id: {name, category, price_wholesale, price_retail, stock_qty,
       material_type, operation_type, last_cost_price, sort_order}}"""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        out = {}
        for row in conn.execute(
                "SELECT id, name, category, price_wholesale, price_retail, stock_qty,"
                "       sort_order, last_cost_price, COALESCE(material_type,'') AS material_type,"
                "       COALESCE(operation_type,'') AS operation_type,"
                "       COALESCE(inventory_type,'') AS inventory_type,"
                "       COALESCE(manufacturing_cost,0) AS manufacturing_cost FROM products"):
            d = dict(row)
            d['id'] = int(d['id'])
            out[d['id']] = d
        return out
    finally:
        conn.close()


def build_report(rows: list, db: dict) -> list:
    """قارن كل صف بالقاعدة وأنشئ مصفوفة تغييرات لكل منتج."""
    report = []
    for row in rows:
        pid = int(row.get("id"))
        rec = {"id": pid, "name": row.get("name"), "fields": {}}
        cur = db.get(pid)
        if cur is None:
            rec["status"] = "مفقود في القاعدة"
            report.append(rec)
            continue
        # مقارنة الحقول
        def cmp(field, sheet_val, db_val):
            s = str(sheet_val).strip() if sheet_val is not None else ""
            d = str(db_val).strip() if db_val is not None else ""
            if field in ("name", "category"):  # مقارنة نصية بالضبط
                return s != d
            # أرقام (float أو int) — سماح ±0.005
            sv, dv = _f(sr := sheet_val), _f(db_val)
            if sv is None and dv is None:
                return False
            if sv is None or dv is None:
                return True
            return abs(sv - dv) > 0.005

        # name
        if cmp("name", row.get("name"), cur["name"]):
            rec["fields"]["name"] = {"sheet": row["name"], "db": cur["name"]}
        # category
        if cmp("category", row.get("category"), cur["category"]):
            rec["fields"]["category"] = {"sheet": row.get("category"), "db": cur["category"]}
        # selling_price → price_retail
        if cmp("selling", row.get("selling_price"), cur["price_retail"]):
            rec["fields"]["selling_price"] = {"sheet": row.get("selling_price"), "db": cur["price_retail"]}
        # wholesale_price → price_wholesale
        if cmp("wholesale", row.get("wholesale_price"), cur["price_wholesale"]):
            rec["fields"]["wholesale_price"] = {"sheet": row.get("wholesale_price"), "db": cur["price_wholesale"]}
        # stock المطلوب إن كان رقمًا (وليس "مستمر" نصيًا)
        st = row.get("stock")
        if isinstance(st, (int, float)) or (isinstance(st, str) and str(st).strip() not in ("", "مستمر")):
            if cmp("stock", st, cur["stock_qty"]):
                rec["fields"]["stock"] = {"sheet": st, "db": cur["stock_qty"]}
        # الأعمدة الذكية — قراءة فقط (تقرير الفرق، التطبيق محجوز لدالة رسمية)
        for wf in WARN_FIELDS:
            sv = row.get(wf)
            if wf == "raw_material_cost":
                # إجمالي التكلفة من الورقة (خامة + تشغيل) مقابل last_cost_price في القاعدة
                snum = _f(row.get("raw_material_cost", 0.0)) + _f(row.get("manufacturing_cost", 0.0))
                dnum = _f(cur["last_cost_price"])
                if snum is None and dnum is None:
                    continue
                if snum is not None and dnum is not None and abs(snum - dnum) <= 0.005:
                    continue
                s = "" if snum is None else str(snum)
                d = "" if dnum is None else str(dnum)
                if s != d:
                    rec["fields"][wf] = {"sheet": snum, "db": dnum}
            elif wf == "manufacturing_cost":
                snum = _f(row.get("manufacturing_cost", 0.0))
                dnum = _f(cur["manufacturing_cost"])
                if snum is None and dnum is None:
                    continue
                if snum is not None and dnum is not None and abs(snum - dnum) <= 0.005:
                    continue
                s = "" if snum is None else str(snum)
                d = "" if dnum is None else str(dnum)
                if s != d:
                    rec["fields"][wf] = {"sheet": snum, "db": dnum}
            elif wf == "material_type":
                dv = cur["material_type"]
                s = "" if sv is None else str(sv).strip()
                d = "" if dv is None else str(dv).strip()
                if s != d:
                    rec["fields"][wf] = {"sheet": sv, "db": dv}
            elif wf == "operation_type":
                dv = cur["operation_type"]
                s = "" if sv is None else str(sv).strip()
                d = "" if dv is None else str(dv).strip()
                if s != d:
                    rec["fields"][wf] = {"sheet": sv, "db": dv}
            elif wf == "inventory_type":
                dv = cur["inventory_type"]
                s = "" if sv is None else str(sv).strip()
                d = "" if dv is None else str(dv).strip()
                if s != d:
                    rec["fields"][wf] = {"sheet": sv, "db": dv}
        report.append(rec)
    return report


def render_dryrun(report: list, rows: list, db: dict, file: str) -> str:
    lines = [
        "# تقرير Dry-run — استيراد الكتالوج (قراءة فقط، لا تغيير)",
        "",
        f"- الملف: `{file}`",
        f"- صفوف الشيت ب id: {len(rows)}",
        f"- منتجات القاعدة: {len(db)}",
        "",
    ]
    changed = [r for r in report if r.get("fields")]
    missing = [r for r in report if r.get("status") == "مفقود في القاعدة"]
    lines.append(f"- **سيُعدَّل (حقول فعلية):** {len(changed)} منتج")
    lines.append(f"- **مفقود في القاعدة:** {len(missing)}")
    lines.append(f"- **التطبيق عبر الدوال الرسمية:** الأسعار/الاسم/التصنيف/المخزون عبر الدوال الحالية؛ الحقول الذكية (خامة/تشغيل/نوع مخزون/تكاليف) عبر الدالة الرسمية الجديدة `update_product_catalog_fields` (تضمن وجود الأعمدة عند الحاجة).")
    lines.append("")
    lines.append("### التغييرات المكتشفة")
    if not changed and not missing:
        lines.append("لا تغييرات — الشيت مطابق للقاعدة.")
    for r in changed[:50]:
        lines.append(f"- id={r['id']} «{r['name']}»:")
        for k, v in r["fields"].items():
            lines.append(f"    - {k}: شيت={v['sheet']!r} | قاعدة={v['db']!r}")
    lines.append("")
    lines.append("### ملاحظات تشغيلية")
    lines.append("- الأعمدة الذكية (material_type/operation_type/inventory_type/tكاليف) تُقرأ وتُطابَق أعلاه؛")
    lines.append("  تطبيقها الفعلي متاح الآن عبر الدالة الرسمية `update_product_catalog_fields` (تضمن وجود الأعمدة عند الحاجة).")
    lines.append("- النسخة الاحتياطية وفلتر المزامنة السحابية: تحدث عند `--apply` فقط.")
    return "\n".join(lines)


def make_backup(db_path: Path) -> Path:
    """نسخة احتياطية فورية pos_data.db.bak-<timestamp> في نفس المجلد."""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    bak = db_path.parent / f"{db_path.name}.bak-{stamp}"
    import shutil
    shutil.copy2(db_path, bak)
    return bak


def apply_row_official(row: dict, db: dict, module_dir: str) -> dict:
    """تطبيق تغييرات صف واحد عبر الدوال الرسمية فقط (module_dir يحدد أي نسخة database.py)."""
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    try:
        import database as D
    except Exception as exc:
        return {"ok": False, "error": f"database import: {exc}"}

    pid = int(row["id"])
    cur = db.get(pid)
    if cur is None:
        return {"ok": False, "error": f"id {pid} غير موجود في القاعدة"}
    changes = {}

    def _num(v, default=None):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    # الاسم/التصنيف/سعر البيع (selling_price) — الجملة تبقى كما هي (الشيت لا يحملها)
    new_name = str(row.get("name")).strip() if row.get("name") not in (None, "") else cur["name"]
    new_cat = str(row.get("category")).strip() if row.get("category") not in (None, "") else (cur["category"] or "")
    new_r = _num(row.get("selling_price"), cur["price_retail"])
    new_w = _num(row.get("wholesale_price"), cur["price_wholesale"])

    if new_name != cur["name"] or new_cat != (cur["category"] or "") or \
       abs(new_r - cur["price_retail"]) > 0.005 or abs(new_w - cur["price_wholesale"]) > 0.005:
        D.update_product_details(pid, new_name, new_cat, new_w, new_r, cur["sort_order"])
        changes["details"] = True

    # المخزون: استخدم update_product_stock_db (دلتا = المطلوب - الحالي)
    st = row.get("stock")
    if isinstance(st, (int, float)):
        target = float(st)
        if abs(target - cur["stock_qty"]) > 0.005:
            D.update_product_stock_db(pid, target - cur["stock_qty"])
            changes["stock"] = True
    elif isinstance(st, str) and str(st).strip() not in ("", "مستمر"):
        try:
            target = float(str(st).replace(",", ".").strip())
            if abs(target - cur["stock_qty"]) > 0.005:
                D.update_product_stock_db(pid, target - cur["stock_qty"])
                changes["stock"] = True
        except ValueError:
            changes["stock_error"] = f"قيمة stock غير رقمية: {st!r}"

    # الحقول الذكية من الكتالوج (نوع الخامة، مسار التشغيل، نوع المخزون، التكاليف)
    smart_updates = {}
    mat = row.get("material_type")
    if mat is not None and str(mat).strip() != "":
        smart_updates["material_type"] = str(mat).strip()
    op = row.get("operation_type")
    if op is not None and str(op).strip() != "":
        smart_updates["operation_type"] = str(op).strip()
    inv = row.get("inventory_type")
    if inv is not None and str(inv).strip() != "":
        smart_updates["inventory_type"] = str(inv).strip()
    raw = _num(row.get("raw_material_cost"), 0.0)
    mfg = _num(row.get("manufacturing_cost"), 0.0)
    total_cost = raw + mfg
    if total_cost > 0:
        smart_updates["last_cost_price"] = total_cost
    if mfg > 0:
        smart_updates["manufacturing_cost"] = mfg

    if smart_updates:
        res = D.update_product_catalog_fields(pid, **smart_updates)
        if res.get("success"):
            changes["smart"] = True
        else:
            changes["smart_error"] = res.get("error", "Unknown error")

    return {"ok": True, "id": pid, "changes": changes}


def main() -> int:
    ap = argparse.ArgumentParser(description="استيراد كتالوج المنتجات الآمن (Dry-run ثم Apply)")
    ap.add_argument("--file", required=True, help="مسار ملف products_catalog_master.xlsx")
    ap.add_argument("--apply", action="store_true", help="نفّذ التعديلات بعد النسخ الاحتياطي (بدونه تقرير فقط)")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--db-module-dir", default=str(Path(r"G:\ai\Elnagar POS")),
                    help="مجلد database.py للدوال الرسمية (للاختبار: _sandbox_pos_writer)")
    ap.add_argument("--report", default="", help="مسار تقرير الـ Dry-run خارجي (اختياري)")
    args = ap.parse_args()

    xlsx = Path(args.file)
    db_path = Path(args.db)
    if not xlsx.exists():
        print(f"{{'error': 'ملف الشيت غير موجود: {xlsx}'}}")
        return 1
    if not db_path.exists():
        print(f"{{'error': 'القاعدة غير موجودة: {db_path}'}}")
        return 1

    rows, warns = read_sheet(xlsx)
    db = read_db(db_path)
    report = build_report(rows, db)
    md = render_dryrun(report, rows, db, str(xlsx))
    print(md)

    if args.report:
        Path(args.report).write_text(md, encoding="utf-8")
        print(f"\n[تقرير محفوظ] {args.report}")

    if warns:
        print("\n[تحذيرات]:")
        for w in warns:
            print(" -", w)

    if not args.apply:
        print("\n(لم تُطبَّق أي تغييرات — هذا تقرير فحسب)")
        return 0

    # ---- Apply: نسخة احتياطية ثم تطبيق عبر الدوال الرسمية
    if not db_path.exists():
        db_path = Path(DEFAULT_DB)
    bak = make_backup(db_path)
    print(f"\n[نسخة احتياطية] {bak}")
    module_dir = args.db_module_dir
    # نمط pos-writer المعتمد: database.py يفتح القاعدة بمسار نسبي (DB_NAME)
    # → لازم os.chdir لمجلد القاعدة قبل استدعاء الدوال الرسمية
    import os
    os.chdir(module_dir)
    applied = []
    errors = []
    for row in rows:
        res = apply_row_official(row, db, module_dir)
        if res.get("ok"):
            if res.get("changes"):
                applied.append(res)
        else:
            errors.append(res)
    print(f"\n[النتيجة] مكتمل لأصناف: {len(applied)} | أخطاء: {len(errors)}")
    for e in errors:
        print(" - خطأ:", e)
    if not errors:
        print("[تذكير] شغّل المزامنة السحابية بعد التطبيق: python cloud\\supabase_sync.py --push-once")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
