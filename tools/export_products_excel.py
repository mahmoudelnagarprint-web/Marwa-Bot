#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""export_products_excel.py — تصدير كتالوج المنتجات إلى شيت إكسيل ذكي (أمر المالك 2026-10-13).

الخطوة الأولى في دورة «Master Excel Catalog & Two-Way Sync».
- يقرأ `pos_data.db` بقراءة فقط (mode=ro) — لا كتابة على القاعدة إطلاقًا.
- يجمع بيانات products + product_recipes (BOM) ويُنشئ `products_catalog_master.xlsx`.
- تنسيقات احترافية + حماية الحقل id (مغلق) + قوائم منسدلة (Data Validation)
  لـ material_type / operation_type / inventory_type + معادلات Excel حية:
    total_cost      = raw_material_cost + manufacturing_cost
    profit_margin   = selling_price - total_cost
    profit_percentage = margin / selling_price (نسبة مئوية)
- selling_price = price_retail من البرنامج (سعر البيع المعتمد للقطاعي) — لا مخترَع.

الاستخدام:
  python tools\export_products_excel.py [--db G:\ai\Elnagar POS\pos_data.db] [--out exports\products_catalog_master.xlsx]

القواعد الملتزم بها (AGENT/RULES):
  - قراءة فقط — يفتح pos_data.db با mode=ro عبر uri=file:...?mode=ro.
  - لا يخترع أسعارًا أو تكاليف؛ التكاليف الخام تخرج بصفر (تُملأ من المالك في الشيت).
  - inventory_type تقديري بمنطق واضح (مستمر/رصيد) قابل للتعديل اليدوي في الشيت.
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

# استيراد openpyxl اختياري — يوجه المستخدم للـ pip لو غير موجود
try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side, Protection
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
except ImportError:  # pragma: no cover
    print("خطأ: openpyxl غير مضمّن — شغّل python -m pip install openpyxl")
    sys.exit(1)

# ------- الإعدادات ----------------------------------------------------------

# قيمة استنتاجية منطقية حسب operation_type (التقدير ملحوظ؛ يعدّله المالك من الشيت)
ON_DEMAND_OPS = {"laser", "engraving", "composite"}
PHYSICAL_OPS = {"sublimation", "framing"}  # مجات/شاسيهات/تابلوهات جاهزة

# أسماء أعمدة الشيت (per spec) مع عنوان عربي للصف 2
HEADERS = {
    "id": "كود المنتج (مغلق)",
    "name": "اسم المنتج",
    "category": "التصنيف",
    "material_type": "نوع الخامة",
    "operation_type": "مسار التشغيل",
    "inventory_type": "نوع المخزون",
    "stock": "الكمية الحالية",
    "raw_material_cost": "تكلفة الخامة (EGP)",
    "manufacturing_cost": "تكلفة التشغيل (EGP)",
    "selling_price": "سعر البيع (EGP)",
    "notes": "ملاحظات تشغيلية",
}
FORMULA_COLS = ["total_cost", "profit_margin", "profit_percentage"]
FULL_ORDER = [
    "id", "name", "category", "material_type", "operation_type", "inventory_type",
    "stock", "raw_material_cost", "manufacturing_cost", "total_cost",
    "selling_price", "profit_margin", "profit_percentage", "notes",
]

# --- تنسيقات
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")       # أزرق داكن
ID_FILL = PatternFill("solid", fgColor="F2F2F2")           # رمادي فاتح (مغلق)
EDIT_FILL = PatternFill("solid", fgColor="FFFFFF")
TOTAL_FILL = PatternFill("solid", fgColor="FFF2CC")        # أصفر فاتح للمعادلات
MARGIN_FILL = PatternFill("solid", fgColor="E2EFDA")       # أخضر فاتح
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
ARABIC_FONT = Font(italic=True, color="7F7F7F", size=9)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# قوائم منسدلة
VALID_MATERIAL = ["خشب MDF", "أكريليك", "مج سيراميك", "جلد", "مركب/فوتو+سلوفان",
                 "خشب/خامة", "زجاج", "حفر مباشر", "قطع ليزر", "أخرى"]
VALID_PHYSICAL = ["مستمر", "رصيد بالعدد"]


def classify_inventory(op_type: str | None) -> str:
    """تقدير استنتاجي لنوع المخزون حسب مسار التشغيل — القيمة الافتراضية فقط."""
    op = (op_type or "").strip().lower()
    if not op or op in ("unknown", "needs_review"):
        return ""
    if op in ON_DEMAND_OPS or op == "engraving_ready":
        return "مستمر"
    return "رصيد بالعدد"


def read_products(db_path: Path) -> list[dict]:
    """قراءة ro: منتجات + BOM recipes. لا INSERT/UPDATE/commit."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT p.id, p.name, p.category, p.price_retail, p.price_wholesale,
                      p.stock_qty, p.last_cost_price, p.material_type, p.operation_type
               FROM products p ORDER BY p.sort_order IS NULL, p.sort_order, p.id"""
        ).fetchall()
        # BOM لكل منتج (قد يوجد أكثر من recipe واحدة — نجمع كنص ملاحظات تشغيلية)
        bom = {}
        for r in conn.execute(
                """SELECT product_id, material_code, operation_type, length_cm, width_cm,
                          waste_pct, machine_time_min, extra_parts, notes
                   FROM product_recipes ORDER BY product_id"""
        ):
            pid = r["product_id"]
            parts = []
            if r["material_code"]:
                parts.append(f"خامة:{r['material_code']}")
            if r["length_cm"] and r["width_cm"]:
                parts.append(f"{r['length_cm']}×{r['width_cm']}سم")
            if r["waste_pct"]:
                parts.append(f"هالك {r['waste_pct']}%")
            if r["machine_time_min"] if False else (r["machine_time_min"] or 0):
                parts.append(f"ماكينة≈{r['machine_time_min']}د")
            if r["extra_parts"]:
                parts.append(str(r["extra_parts"]))
            if r["notes"]:
                parts.append(str(r["notes"]))
            bom.setdefault(pid, []).append("؛ ".join(parts))
        out = []
        for r in rows:
            d = dict(r)
            d["recipes_notes"] = " | ".join(bom.get(d["id"], []))
            out.append(d)
        return out
    finally:
        conn.close()


def build_sheet(products: list[dict], out_path: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "الكتالوج الرئيسي"

    # ---- الصف 1: عنوان عربي جامع
    ws.merge_cells("A1:N1")
    c = ws["A1"]
    c.value = "كتالوج منتجات النجار برنت — Master Excel Catalog (تعديل آمن + معادلات حية)"
    c.font = Font(bold=True, size=14, color="1F4E78")
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24

    # ---- الصف 2: رؤوس إنجليزية (المطابقة للـ spec)
    for j, col in enumerate(FULL_ORDER, start=1):
        cell = ws.cell(row=2, column=j, value=col)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        cell.protection = Protection(locked=True)

    # ---- الصف 3: الترجمة العربية للرؤوس (توضيحية)
    for j, col in enumerate(FULL_ORDER, start=1):
        label = HEADERS.get(col)
        cell = ws.cell(row=3, column=j, value=label or FORMULA_LABELS.get(col, ""))
        cell.font = ARABIC_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
        cell.protection = Protection(locked=True)

    # ---- البيانات (تبدأ من الصف 4)
    first_data = 4
    for i, p in enumerate(products):
        r = first_data + i
        ws.cell(row=r, column=1, value=p["id"])            # id مغلق
        ws.cell(row=r, column=2, value=p["name"])
        ws.cell(row=r, column=3, value=p["category"])
        ws.cell(row=r, column=4, value=p["material_type"] or "")
        ws.cell(row=r, column=5, value=p["operation_type"] or "")
        inv_type = classify_inventory(p["operation_type"])
        ws.cell(row=r, column=6, value=inv_type)
        # stock: للأعمال المستمرة = "مستمر" (لا كمية محسوبة)؛ للرصيد بالعدد/غير المصنف = الرقم الفعلي
        ws.cell(row=r, column=7,
                value="مستمر" if inv_type == "مستمر" else (p["stock_qty"] if p["stock_qty"] is not None else 0))
        ws.cell(row=r, column=8, value=p["last_cost_price"] or 0)   # raw cost الحالية (لو كانت)
        ws.cell(row=r, column=9, value=0)                            # manufacturing — يُملأ من المالك
        # total_cost = Raw + Mfg  (معادلة)
        ws.cell(row=r, column=10,
                value=f"=H{r}+I{r}")
        ws.cell(row=r, column=11, value=p["price_retail"])           # سعر البيع — من البرنامج
        # profit_margin = Selling - Total
        ws.cell(row=r, column=12, value=f"=K{r}-J{r}")
        # profit_percentage = margin / selling (نسبة)
        ws.cell(row=r, column=13, value=f'=IF(K{r}>0, J{r}/K{r}*100, "")')
        notes = []
        if p["price_wholesale"] and p["price_wholesale"] != p["price_retail"]:
            notes.append(f"جملة: {p['price_wholesale']} ج")
        if p.get("recipes_notes"):
            notes.append(p["recipes_notes"])
        ws.cell(row=r, column=14, value="؛ ".join(notes))

        # ---- تنسيق الصف
        for j in range(1, len(FULL_ORDER) + 1):
            cell = ws.cell(row=r, column=j)
            cell.border = BORDER
            cell.alignment = Alignment(vertical="center",
                                       horizontal="center" if j in (1, 3, 4, 5, 6, 7, 10, 12, 13) else "left",
                                       wrap_text=(j in (2, 14)))
        # خلية id مغلقة (locked) بلا تعديل
        ws.cell(row=r, column=1).fill = ID_FILL
        ws.cell(row=r, column=1).protection = Protection(locked=True)
        # خلايا المعادلات ملوّنة (total_cost مصفرّ، الهامش أخضر)
        ws.cell(row=r, column=10).fill = TOTAL_FILL
        ws.cell(row=r, column=12).fill = MARGIN_FILL
        ws.cell(row=r, column=13).fill = MARGIN_FILL
        # الحقول القابلة للتعديل تترك unlocked حتى تسمح الحماية
        for j in (4, 5, 6, 7, 8, 9, 11, 14):
            ws.cell(row=r, column=j).protection = Protection(locked=False)

    last = first_data + len(products) - 1

    # ---- قوائم منسدلة
    dv_mat = DataValidation(
        type="list", formula1='"' + ",".join(VALID_MATERIAL) + '"',
        allow_blank=True, showErrorMessage=True,
        errorTitle="قيمة غير صالحة", error="اختر من قائمة أنواع الخامات")
    dv_op = DataValidation(
        type="list", formula1='"ليزر,سبلميشن,حفر مباشر,مركب فوتو وسلوفان,جاهز,قطع"',
        allow_blank=True, showErrorMessage=True,
        errorTitle="قيمة غير صالحة", error="اختر من قائمة مسارات التشغيل")
    dv_inv = DataValidation(
        type="list", formula1='"مستمر,رصيد بالعدد"',
        allow_blank=True, showErrorMessage=True,
        errorTitle="قيمة غير صالحة", error="اختر نوع المخزون")
    ws.add_data_validation(dv_mat); ws.add_data_validation(dv_op); ws.add_data_validation(dv_inv)
    if last >= first_data:
        dv_mat.add(f"D{first_data}:D{last}")
        dv_op.add(f"E{first_data}:E{last}")
        dv_inv.add(f"F{first_data}:F{last}")

    # ---- تجميد + عرض الأعمدة + فلترة
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A2:N{max(last, 3)}"
    widths = {"A": 9, "B": 30, "C": 16, "D": 16, "E": 18, "F": 13, "G": 11,
              "H": 13, "I": 14, "J": 11, "K": 12, "L": 12, "M": 13, "N": 46}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    # ---- حماية الورقة: كل شيء مقفل إلا الحقول القابلة للتعديل (id مقفل بلا كلمة مرور)
    ws.protection.sheet = True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


FORMULA_LABELS = {
    "total_cost": "إجمالي التكلفة (تلقائي)",
    "profit_margin": "صافي الربح (تلقائي)",
    "profit_percentage": "نسبة الربح % (تلقائي)",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="تصدير كتالوج المنتجات إلى إكسيل ذكي")
    ap.add_argument("--db", default=r"G:\ai\Elnagar POS\pos_data.db")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "exports" / "products_catalog_master.xlsx"))
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"خطأ: القاعدة غير موجودة: {db_path}")
        return 1
    products = read_products(db_path)
    out = build_sheet(products, Path(args.out))
    print(f"تم التصدير: {out}")
    print(f"عدد المنتجات: {len(products)}")
    print(f"الوقت: {datetime.now():%Y-%m-%d %H:%M:%S}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
