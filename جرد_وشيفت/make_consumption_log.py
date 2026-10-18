# -*- coding: utf-8 -*-
"""سجل استهلاك الخامات اليومي — أمين المخزن (صاصا) — بالربط مع بيبو (الليزر/الإبسون)"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = r"G:\ai\Naggar Print POS Agent\جرد_وشيفت\سجل_استهلاك_الخامات_اليومي.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "سجل استهلاك الخامات اليومي"

# ترويسة
ws.sheet_view.rightToLeft = True
ws["B2"] = "سجل استهلاك الخامات اليومي — ورشة النجار برنت"
ws["B2"].font = Font(bold=True, size=14)
ws["B1"] = "أمين المخزن: صاصا (SASA) بالربط مع بيبو (الإنتاج) — ورشة النجار برنت"
ws["B1"].font = Font(bold=True, size=11)

# رأس الجدول
headers = ["التاريخ", "الطلب/قطعة الشغل", "الخامة (كود)", "الوحدة", "الكمية المصروفة",
           "المساحة (سم²)", "الهالك%", "قيمة الاستهلاك (ج)", "اعتماد بيبو", "ملاحظات"]
ws.append([])  # صف فارغ
header_row = 4
for col, h in enumerate(headers, start=1):
    cell = ws.cell(row=header_row, column=col, value=h)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor="2E7D32")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

# صفوف فارغة قابلة للتعبئة — عمود «قيمة الاستهلاك» = المساحة × سعر السم² (يُدخل السعر يدوياً)
for r in range(header_row + 1, header_row + 26):
    for c in range(1, len(headers) + 1):
        ws.cell(row=r, column=c)
    # H = التكلفة اليدوية الفعلية للخامة المصروفة (يدخلها أمين المخزن بعد الاعتماد)
    ws.cell(row=r, column=8, value="")

# تعيين عروض
widths = [12, 30, 18, 10, 12, 14, 10, 16, 14, 24]
for i, w in enumerate(widths, start=1):
    ws.column_dimensions[get_column_letter(i)].width = w

# أخمص: ملاحظات المرجع
ws.append([])
ws.append([])
ws.cell(row=header_row + 26 + 1, column=1, value="مرجع الخامات المعتمدة (من raw_materials في pos_data.db):").font = Font(bold=True)
mats = [
    ("mdf_3mm_122x244", "لوح MDF 3مم 122×244 — 450 ج/لوح — 0.01512 ج/سم² — هالك 10/15%"),
    ("acrylic_3mm_122x244", "لوح أكريليك 3مم 122×244 — 3,000 ج/لوح — 0.10078 ج/سم²"),
    ("sub_paper_a4", "ورقة سبلميشن A4 — 20 ج/ورقة"),
    ("mug_white_11oz", "مج أبيض خام — 45 ج/قطعة"),
    ("mug_print_press", "طباعة وكبس مج — 10 ج/قطعة"),
    ("coaster_blank", "كوستر خام — 10 ج/قطعة"),
    ("coaster_print", "طباعة الكوستر — 3 ج/قطعة"),
    ("laser_setup_fee", "فتحة شغل ليزر — 30 ج/طلب (ثابتة)"),
    ("tablou_chassis_30x40", "شاسيه تابلوه 30×40 — 30 ج/قطعة"),
    ("photo_print_a3_lam", "طباعة فوتو A3 + سلوفان — 70 ج/ورقة"),
]
start = header_row + 26 + 2
for i, (code, desc) in enumerate(mats):
    ws.cell(row=start + i, column=1, value=code).font = Font(bold=True, size=9)
    ws.cell(row=start + i, column=2, value=desc).font = Font(size=9)

wb.save(OUT)
print("OK ->", OUT)
