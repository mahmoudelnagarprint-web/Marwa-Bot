# -*- coding: utf-8 -*-
"""نموذج جرد وإغلاق الشيفت — أمين الصندوق والمخزن (صاصا/مصطفى) — ورشة النجار برنت"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

OUT = r"G:\ai\Naggar Print POS Agent\جرد_وشيفت\نموذج_جرد_وإغلاق_الشيفت.docx"

doc = Document()

# هوامش
for s in doc.sections:
    s.top_margin = Cm(1.5)
    s.bottom_margin = Cm(1.5)
    s.left_margin = Cm(2)
    s.right_margin = Cm(2)

# الترويسة
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("ورشة النجار برنت — برج التلي")
r.bold = True
r.font.size = Pt(18)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("نموذج جرد وإغلاق الشيفت (الخزنة والدرج النقدي)")
r.bold = True
r.font.size = Pt(15)
r.font.color.rgb = RGBColor(0x8B, 0x00, 0x00)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("أمين الصندوق والمخزن: صاصا (SASA) • بالربط مع CFO (فارس) • قواعد الخزينة سارية")
r.font.size = Pt(10)
r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

doc.add_paragraph()

# ==== 1) بيانات الشيفت ====
doc.add_heading("أولاً: بيانات الشيفت", level=2)
tbl = doc.add_table(rows=6, cols=4)
tbl.style = "Table Grid"
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
data = [
    ("رقم الشيفت", "", "تاريخ الفتح", "2026-06-02 00:00:36"),
    ("الحالة", "مفتوح / معلّق (open)", "تاريخ الإغلاق", "______"),
    ("المسؤول عن الإغلاق", "صاصا (سجل الخزنة)", "التوقيع", "______"),
    ("الشاهد (CFO/فارس)", "______", "التوقيع", "______"),
    ("المالك (النوافذ)", "______", "التوقيع", "______"),
]
for i, row in enumerate(data, start=1):
    for j, txt in enumerate(row):
        cell = tbl.cell(i, j)
        cell.text = txt
        for par in cell.paragraphs:
            if j % 2 == 1:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
# ترويسة الجدول
for j, h in enumerate(["البند", "القيمة", "البند", "القيمة"]):
    cell = tbl.cell(0, j)
    cell.text = h
    for par in cell.paragraphs:
        for run in par.runs:
            run.bold = True

doc.add_paragraph()

# ==== 2) جرد الدرج النقدي ====
doc.add_heading("ثانياً: جرد الدرج النقدي (عدد وكمية الفئات)", level=2)
note = doc.add_paragraph()
note.add_run("يُملأ بعد العَدّ اليدوي للدرج — كل فئة تُسجَّل ثم يُجمع المبلغ.").font.size = Pt(10)

tbl2 = doc.add_table(rows=10, cols=5)
tbl2.style = "Table Grid"
hdr = ["الفئة", "العدد", "الإجمالي", "الفئة", "الإجمالي"]
for j, h in enumerate(hdr):
    tbl2.cell(0, j).text = h
denoms = [
    ("500 ج", "200 ج"),
    ("200 ج", "100 ج"),
    ("100 ج", "50 ج"),
    ("100 ج — ورقة جديدة", "20 ج"),
    ("50 ج", "10 ج"),
    ("20 ج", "5 ج"),
    ("10 ج", "1 ج"),
    ("5 ج", "عملات معدنية"),
    ("إجمالي نقدي بالدرج", ""),
]
for i, (a, b) in enumerate(denoms, start=1):
    tbl2.cell(i, 0).text = a
    tbl2.cell(i, 2).text = b
    for col in (0, 2):
        for par in tbl2.cell(i, col).paragraphs:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()

# ==== 3) مطابقة الأرقام الحية ====
doc.add_heading("ثالثاً: مطابقة الأرقام الحية (مصدر الحقيقة: pos_data.db)", level=2)
tbl3 = doc.add_table(rows=7, cols=3)
tbl3.style = "Table Grid"
r3 = [
    ("البند", "قيمة القاعدة الحية", "المعدود يدوياً"),
    ("إجمالي الآجل (أرصدة العملاء الموجبة)", "1,040 ج", "______"),
    ("إجمالي المعلّق (طلبات تحت التجهيز)", "2,115 ج", "______"),
    ("إجمالي الآجل + المعلّق (المستحقات)", "3,155 ج", "______"),
    ("النقد المتاح بالدرج (يُحسب من الجدول السابق)", "______", "______"),
    ("المصروفات (Expense)", "4,995 ج", "______"),
    ("الدخل (Income + Payment)", "15,630 ج", "______"),
]
for i, row in enumerate(r3):
    for j, txt in enumerate(row):
        c = tbl3.cell(i, j)
        c.text = txt
        if i == 0:
            for par in c.paragraphs:
                for run in par.runs:
                    run.bold = True
        elif j == 2:
            for par in c.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()
note2 = doc.add_paragraph()
note2.add_run("ملاحظة: المعلّق (2,115) = 6 طلبات «تحت التجهيز» (Under Preparation) من قاعدة order_pos. "
              "الآجل (1,040) = مجموع أرصدة العملاء الموجبة (زينب 240 + عميل 350 + اسراء هلال 250 + عميل 200). "
              "الأرقام مرتبطة بشيفت مفتوح منذ 2026-06-02 00:00:36 — لم يُغلق بعد.").font.size = Pt(9)

doc.add_paragraph()

# ==== 4) تسوية الخزنة / بنود الإقفال ====
doc.add_heading("رابعاً: تسوية الخزنة البنود الواجب تصفيتها", level=2)
tbl4 = doc.add_table(rows=8, cols=3)
tbl4.style = "Table Grid"
r4 = [
    ("#", "بيان السحب / البند", "المبلغ (ج)"),
    ("1", "سحب آجل من درج النقدية للخزنة الرئيسية", "______"),
    ("2", "مصروفات الشيفت المستحقة (المسجّلة أو المعلّقة)", "______"),
    ("3", "مبالغ أقساط العملاء المتأخرة (آجل)", "______"),
    ("4", "مبالغ طلبات تحت التجهيز المستلمة مقدماً", "______"),
    ("5", "تسوية النقد بالمصروف المعلن", "______"),
    ("6", "أي فروقات درج (عجز / زيادة)", "______"),
    ("7", "إجمالي تصفية الخزنة النهائي", "______"),
]
for i, row in enumerate(r4):
    for j, txt in enumerate(row):
        c = tbl4.cell(i, j)
        c.text = txt
        if i == 0:
            for par in c.paragraphs:
                for run in par.runs:
                    run.bold = True
        elif j == 2:
            for par in c.paragraphs:
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()

# ==== 5) خطة ما بعد الإغلاق ====
doc.add_heading("خامساً: ما بعد الإغلاق — شيفتات يومية نظيفة", level=2)
for item in [
    "• إغلاق الشيفت الحالي (المفتوح منذ 06-02) في قاعدة pos_data.db — بموافقة المالك.",
    "• فتح شيفت جديد نظيف يوميًا لكل يوم عمل فعلي.",
    "• تحويل النقد المُصفّى إلى الخزنة الرئيسية وتسليمه للمالك أو CFO.",
    "• تحديث FARES_CFO_STATE.md بأرقام التسوية لإغلاق الحلقة بين الورشة واللابتوب.",
]:
    doc.add_paragraph(item)

# التذييل
doc.add_paragraph()
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = p.add_run("— نموذج جاهز للاستخدام — طباعة والبدء بالجرد اليدوي —")
r.font.size = Pt(9)
r.font.color.rgb = RGBColor(0x88, 0x88, 0x88)

doc.save(OUT)
print("OK ->", OUT)
