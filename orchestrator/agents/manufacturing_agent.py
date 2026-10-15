# -*- coding: utf-8 -*-
"""Manufacturing Agent (وكيل التصنيع وهندسة التكاليف) — Phase 6 FULL BUILD.
يبني على المرحلة 6 (2026-10-14): خامات حقيقية + وصفات منتجات + معادلات تشغيل.

القدرات (كلها قراءة + حساب — لا كتابة مالية أبدًا):
  • «الخامات» / «قائمة الألواح»        : عرض raw_materials من القاعدة الحقيقية.
  • «تكلفة <منتج>»                      : حساب تكلفة منتج من وصفته وخامته.
  • «احسب ليزر <طول> × <عرض>»           : معادلة استهلاك الألواح المباشرة.
  • «وصفة <منتج>»                       : عرض وصفة المنتج من product_recipes.
  • «بطاقة شغل <منتج>» / «ملف شغل»      : توليد بطاقة تشغيل نصية لماكينة RDWorks.

معادلات المالك المعتمدة:
  • ألواح الليزر : (الطول × العرض × سعر السم²) × (1 + الهالك٪) + وقت الماكينة × معدل التشغيل.
  • التابلوهات   : خشب MDF + ورق فوتو + سلوفان حراري.
  • المجات       : المج الخام + الحبر والكبس.
الصدق أولًا: أي بيانات ناقصة تُعرض كما هي — لا تخمين ولا تسعير مخترع.
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..base import SubAgent

ROOT = Path(__file__).resolve().parent.parent.parent          # G:\ai\Elnagar POS
DB_PATH = ROOT / "pos_data.db"
JOBS_DIR = ROOT / "cloud" / "jobs"                            # بطاقات الشغل
WASTE_DEFAULT = 5.0                                           # هالك افتراضي 5% حتى تعريف المالك


def _ro_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt(n) -> str:
    try:
        f = float(n)
        return str(int(f)) if f == int(f) else f"{f:.2f}"
    except (TypeError, ValueError):
        return str(n)


class ManufacturingAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="manufacturing",
            name="وكيل التصنيع وهندسة التكاليف (Manufacturing)",
            keywords=[
                "خامات", "خامة", "الخامات", "ألواح", "الواح", "لوح",
                "استهلاك", "هالك", "تكلفة", "تكلفه", "احسب تكلفة", "حساب التكلفة",
                "وصفة", "وصفه", "recipe", "بطاقة شغل", "بطاقه شغل", "ملف شغل",
                "job card", "rdworks", "وقت تشغيل", "الماكينة", "ماكينة",
                "صناعة", "تصنيع", "manufacturing",
            ],
            phase=6,
        )

    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"🏭 {title}\n{body}", "action": "manufacturing", "payload": {}}

    # ------------------------------------------------------------- قراءات أساسية
    def _find_product(self, text: str) -> Optional[sqlite3.Row]:
        """مطابقة اسم منتج داخل نص الرسالة (أطول اسم يطابق الأول)."""
        conn = _ro_conn()
        try:
            rows = conn.execute("SELECT id, name, category, material_type, operation_type "
                                 "FROM products ORDER BY id").fetchall()
        finally:
            conn.close()
        best = None
        for r in rows:
            nm = (r["name"] or "").strip()
            if nm and nm in text:
                if best is None or len(nm) > len((best["name"] or "").strip()):
                    best = r
        return best

    def _list_materials(self) -> Dict[str, Any]:
        conn = _ro_conn()
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT code, name, category, material_kind, width_cm, height_cm, "
                "sheet_price, price_per_cm2, unit FROM raw_materials ORDER BY code"
            ).fetchall()]
        finally:
            conn.close()
        if not rows:
            return self._reply(
                "قائمة الخامات",
                "خانات جدول raw_materials لسه فاضية — دي الأسئلة التشغيلية اللي محتاج "
                "إجابتها منك عشان أملأها (مقاسات الألواح وأسعارها والخامات الجاهزة).\n"
                "بعد ما تعتمدها بتشوف «الخامات» بتعرضها كاملة بالسعر لكل سم²."
            )
        lines = []
        for r in rows:
            price = f"{_fmt(r['price_per_cm2'])} ج.م/سم²" if r["price_per_cm2"] else "بلا سعر"
            dims = f"{_fmt(r['width_cm'])}×{_fmt(r['height_cm'])} سم" if r["width_cm"] else "—"
            lines.append(
                f"• [{r['code']}] {r['name']} — {r['material_kind']} — {dims} — "
                f"سعر اللوح {_fmt(r['sheet_price'])} ج.م — {price}")
        return self._reply("قائمة الخامات المسعّرة", "\n".join(lines))

    # ------------------------------------------------------------- معادلات التكلفة
    def _get_setup_fee(self) -> float:
        """فتحة شغل الليزر (حد أدنى للطلب) من raw_materials — المعتمد من المالك: 30 ج."""
        try:
            conn = _ro_conn()
            try:
                r = conn.execute(
                    "SELECT sheet_price FROM raw_materials WHERE code = 'laser_setup_fee'"
                ).fetchone()
                return float(r["sheet_price"]) if r else 0.0
            finally:
                conn.close()
        except Exception:
            return 0.0

    def _laser_sheet_cost(self, length_cm: float, width_cm: float,
                          price_per_cm2: float, waste_pct: float,
                          setup_fee: float = 0.0) -> Dict[str, float]:
        """معادلة المالك المعتمدة (2026-10-14):
        (الطول × العرض × سعر السم²) × (1 + الهالك٪) + فتحة شغل الليزر الثابتة."""
        area = length_cm * width_cm
        material = area * price_per_cm2 * (1 + waste_pct / 100.0)
        return {
            "area_cm2": round(area, 2),
            "material_cost": round(material, 2),
            "waste_pct": waste_pct,
            "setup_fee": round(setup_fee, 2),
            "total": round(material + setup_fee, 2),
        }

    def _product_cost(self, text: str) -> Dict[str, Any]:
        prod = self._find_product(text)
        if prod is None:
            return self._reply(
                "حساب تكلفة منتج",
                "ما عرفش المنتج من اسمه — اكتب: «تكلفة كاب تخرج» مثلًا.")
        conn = _ro_conn()
        try:
            recipe = conn.execute(
                "SELECT * FROM product_recipes WHERE product_id = ?", (prod["id"],)).fetchone()
            material = None
            if recipe is not None and recipe["material_code"]:
                material = conn.execute(
                    "SELECT * FROM raw_materials WHERE code = ?",
                    (recipe["material_code"],)).fetchone()
        finally:
            conn.close()
        if recipe is None:
            return self._reply(
                f"تكلفة «{prod['name']}»",
                f"المنتج موجود (id {prod['id']}) لكن **وصفته مش معرّفة** في product_recipes.\n"
                "محتاج منك: الخامة (كود اللوح) + الأبعاد + الهالك٪ — وأول ما تعتمدها بحفظها بوصفة دائمة.")
        if material is None:
            return self._reply(
                f"تكلفة «{prod['name']}»",
                "الوصفة موجودة لكن الخامة نفسها لسه مش مسعّرة في raw_materials — "
                "ما بخترعش أسعار. عرّفلي سعر اللوح وأحسب فورًا.")
        ln, wd = float(recipe["length_cm"] or 0), float(recipe["width_cm"] or 0)
        op = (recipe["operation_type"] or "").strip()
        pp2 = float(material["price_per_cm2"] or 0)
        area = ln * wd

        # ---- نموذج 1: ليزر (ألواح) — مساحة × سعر السم² × (1+هالك) + فتحة الشغل ----
        if op == "laser":
            waste = float(recipe["waste_pct"] or WASTE_DEFAULT)
            fee = self._get_setup_fee()
            c = self._laser_sheet_cost(ln, wd, pp2, waste, fee)
            return self._reply(
                f"تكلفة «{prod['name']}» (ليزر)",
                f"• الخامة: [{material['code']}] {material['name']} — {pp2} ج.م/سم²\n"
                f"• المساحة: {c['area_cm2']} سم² ({_fmt(ln)}×{_fmt(wd)} سم)\n"
                f"• تكلفة الخامة (بهالك {c['waste_pct']}٪): {c['material_cost']} ج.م\n"
                f"• فتحة شغل الليزر (ثابتة للطلب): {c['setup_fee']} ج.م\n"
                f"**إجمالي التكلفة: {c['total']} ج.م**\n"
                f"📋 ملاحظة الوصفة: {recipe['notes'] or '—'}")

        # ---- نموذج 2: تابلوه مركب (BOM) — شاسيه + طباعة بحماية، بالمعدل بالمساحة ----
        if op in ("composite", "framing"):
            c = self._laser_sheet_cost(ln, wd, pp2, 0.0, 0.0)
            return self._reply(
                f"تكلفة «{prod['name']}» (BOM مركب)",
                f"• الخامة: [{material['code']}] {material['name']} — {pp2} ج.م/سم²\n"
                f"• المساحة: {c['area_cm2']} سم² ({_fmt(ln)}×{_fmt(wd)} سم)\n"
                f"• مكونات: {recipe['extra_parts'] or '—'}\n"
                f"**إجمالي التكلفة: {c['total']} ج.م** (بمعدل المساحة لباقي المقاسات)\n"
                f"📋 ملاحظة الوصفة: {recipe['notes'] or '—'}")

        # ---- نموذج 3: سبلميشن — خام + طباعة وكبس ----
        if op == "sublimation":
            blank = float(material["sheet_price"] or 0)
            print_cost = 0.0
            extra = (recipe["extra_parts"] or "").strip()
            if extra:
                conn = _ro_conn()
                try:
                    pm = conn.execute(
                        "SELECT sheet_price FROM raw_materials WHERE code = ?", (extra,)).fetchone()
                    if pm:
                        print_cost = float(pm["sheet_price"] or 0)
                finally:
                    conn.close()
            return self._reply(
                f"تكلفة «{prod['name']}» (سبلميشن)",
                f"• الخامة الخام: [{material['code']}] {material['name']} — {blank} ج.م\n"
                f"• الطباعة والكبس: {print_cost} ج.م\n"
                f"**إجمالي التكلفة: {round(blank + print_cost, 2)} ج.م**")

        return self._reply(
            f"تكلفة «{prod['name']}»",
            f"مسار التشغيل «{op}» مش معرّف في المعادلات بعد — قولي المسار الصحيح (ليزر/تابلوه/سبلميشن).")

    def _direct_laser_calc(self, text: str) -> Dict[str, Any]:
        """«احسب ليزر 30 20» — معادلة مباشرة بأرقام من الرسالة + أسعار القاعدة."""
        nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text) if float(x) > 0]
        if len(nums) < 2:
            return self._reply(
                "حساب استهلاك الليزر",
                "اكتبها كده: «احسب ليزر 30 20» (الطول ثم العرض بالسنتيمتر).\n"
                f"المعادلة: (الطول × العرض × سعر السم²) × (1 + الهالك٪) — الهالك الافتراضي {WASTE_DEFAULT}٪.")
        ln, wd = nums[0], nums[1]
        conn = _ro_conn()
        try:
            mats = conn.execute(
                "SELECT code, name, price_per_cm2 FROM raw_materials "
                "WHERE price_per_cm2 > 0 ORDER BY code").fetchall()
        finally:
            conn.close()
        if not mats:
            return self._reply(
                "حساب استهلاك الليزر",
                f"المساحة = {ln} × {wd} = {_fmt(ln * wd)} سم² — لكن مفيش خامات مسعّرة بعد. "
                "عرّفلي سعر اللوح الأول (سعر اللوح ÷ مساحته = سعر السم²) وأحسب فورًا.")
        fee = self._get_setup_fee()
        lines = [
            f"المساحة: {ln} × {wd} = {_fmt(ln * wd)} سم²",
            f"فتحة شغل الليزر الثابتة: {_fmt(fee)} ج.م للطلب",
            "",
        ]
        for m in mats[:4]:
            pp2 = float(m["price_per_cm2"])
            c10 = self._laser_sheet_cost(ln, wd, pp2, 10.0, fee)   # مستقيم
            c15 = self._laser_sheet_cost(ln, wd, pp2, 15.0, fee)   # مفرغ/دائري/علب
            lines.append(
                f"• [{m['code']}] {m['name']} ({pp2} ج/سم²):\n"
                f"    مستقيم (هالك 10٪): خامة {c10['material_cost']} + فتحة {c10['setup_fee']} = {c10['total']} ج.م\n"
                f"    مفرغ/دائري/علب (هالك 15٪): خامة {c15['material_cost']} + فتحة {c15['setup_fee']} = {c15['total']} ج.م")
        return self._reply("حساب استهلاك الليزر (بنسبتي الهالك المعتمدتين)", "\n".join(lines))

    # ------------------------------------------------------------- بطاقة الشغل
    def _job_card(self, text: str) -> Dict[str, Any]:
        prod = self._find_product(text)
        if prod is None:
            return self._reply(
                "بطاقة شغل",
                "حدد المنتج: «بطاقة شغل كاب تخرج».")
        conn = _ro_conn()
        try:
            recipe = conn.execute(
                "SELECT * FROM product_recipes WHERE product_id = ?", (prod["id"],)).fetchone()
            material = None
            if recipe is not None and recipe["material_code"]:
                material = conn.execute(
                    "SELECT * FROM raw_materials WHERE code = ?",
                    (recipe["material_code"],)).fetchone()
        finally:
            conn.close()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        path = JOBS_DIR / f"job_{prod['id']}_{ts}.txt"
        lines = [
            "=" * 52,
            f"بطاقة شغل — النجار برنت | {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "=" * 52,
            f"المنتج      : {prod['name']}  (id {prod['id']})",
            f"التصنيف     : {prod['category']} | خامة: {prod['material_type']} | مسار: {prod['operation_type']}",
        ]
        if recipe is not None:
            lines += [
                f"الأبعاد     : {recipe['length_cm']} × {recipe['width_cm']} سم",
                f"الهالك      : {recipe['waste_pct']}%",
                f"وقت الماكينة: {recipe['machine_time_min']} دقيقة",
                f"ملاحظات     : {recipe['notes'] or '—'}",
            ]
        else:
            lines.append("الوصفة      : غير معرّفة — راجع وكيل التصنيع بعد اعتماد الخامات")
        if material is not None:
            lines.append(f"الخامة       : [{material['code']}] {material['name']} — "
                         f"{material['width_cm']}×{material['height_cm']} سم — "
                         f"{material['price_per_cm2']} ج.م/سم²")
        lines += [
            "=" * 52,
            "جهّز التصميم في RDWorks بهذه المواصفات ثم شغّل القص.",
            "(توليد آلي بواسطة وكيل التصنيع — مروة)",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return self._reply(
            "بطاقة شغل جاهزة",
            f"✅ اتولّدت بطاقة الشغل:\n{path}\n"
            + "\n".join(lines[3:9]))

    # ------------------------------------------------------------- الوصفة
    def _recipe_view(self, text: str) -> Dict[str, Any]:
        prod = self._find_product(text)
        if prod is None:
            return self._reply("وصفة منتج", "حدد المنتج: «وصفة كاب تخرج».")
        conn = _ro_conn()
        try:
            recipe = conn.execute(
                "SELECT * FROM product_recipes WHERE product_id = ?", (prod["id"],)).fetchone()
        finally:
            conn.close()
        if recipe is None:
            return self._reply(
                f"وصفة «{prod['name']}»",
                "الوصفة لسه مش معرّفة — بعد اعتماد الخامات والمقاسات أبنيها لك وأحفظها.")
        return self._reply(
            f"وصفة «{prod['name']}»",
            f"• الخامة: {recipe['material_code'] or '—'}\n"
            f"• المسار: {recipe['operation_type'] or '—'}\n"
            f"• الأبعاد: {recipe['length_cm']} × {recipe['width_cm']} سم\n"
            f"• الهالك: {recipe['waste_pct']}%\n"
            f"• وقت الماكينة: {recipe['machine_time_min']} دقيقة\n"
            f"• ملاحظات: {recipe['notes'] or '—'}")

    # ------------------------------------------------------------- التوجيه
    def handle(self, text, ctx=None):
        t = (text or "").lower()
        # 1) قائمة الخامات
        if "خامات" in t or "خامة" in t or "الواح" in t or "ألواح" in t or "لوح" in t:
            if "احسب" in t or "حساب" in t:
                return self._direct_laser_calc(text or "")
            return self._list_materials()
        # 2) احسب ليزر مباشر
        if ("ليزر" in t and ("احسب" in t or "حساب" in t)) or re.search(r"احسب ليزر", t):
            return self._direct_laser_calc(text or "")
        # 3) بطاقة/ملف شغل
        if "بطاقة شغل" in t or "بطاقه شغل" in t or "ملف شغل" in t or "job" in t or "rdworks" in t:
            return self._job_card(text or "")
        # 4) وصفة
        if "وصفة" in t or "وصفه" in t or "recipe" in t:
            return self._recipe_view(text or "")
        # 5) تكلفة منتج
        if "تكلفة" in t or "تكلفه" in t or "استهلاك" in t or "هالك" in t:
            return self._product_cost(text or "")
        # fallback: قدرات
        return self._reply(
            "وكيل التصنيع — قدراتي",
            "• «الخامات» — قائمة الألواح والخامات المسعّرة\n"
            "• «تكلفة <منتج>» — حساب تكلفة من وصفته وخامته\n"
            "• «احسب ليزر 30 20» — معادلة استهلاك مباشرة\n"
            "• «وصفة <منتج>» — عرض وصفة التشغيل\n"
            "• «بطاقة شغل <منتج>» — ملف تشغيل جاهز لـ RDWorks")
