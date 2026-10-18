# -*- coding: utf-8 -*-
"""Marketing Genius (مدير التسويق والعروض) — Phase 5 FULL BUILD.
- يحلل المنتجات الراكدة (لم تُبع أبدًا أو آخر بيع قديم) بكميات حقيقية من order_items.
- يقترح باقات (Bundles) تجمع راكدة من تصنيفات مكمّلة + راكدة مع الأكثر مبيعًا،
  بخصم مقترح وسعر نهائي محسوب من الأسعار الحقيقية — كل الباقات اقتراحات
  معلَّقة على اعتماد المالك، ولا يُغيَّر أي سعر فعلي إلا بأمر عبر القناة الرسمية.
قواعد صارمة: قراءة فقط 100% (mode=ro)، لا بيانات مخترعة — كل رقم من القاعدة،
وفشل القراءة يُبلَّغ بصدق.
"""
from __future__ import annotations

import sqlite3
from datetime import date
import sys as _sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SubAgent

# ── طبقة الربط المركزية (task-2): لا مصدر إلا الحي — أي pos_data.db قديم مرفوض ──
_VISION_LAB = Path(__file__).resolve().parent.parent.parent / "Vision-Lab"   # نسبي — يعمل على أي عقدة
if str(_VISION_LAB) not in _sys.path:
    _sys.path.insert(0, str(_VISION_LAB))
from config import data_source as _central  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent          # G:\ai\Naggar Print POS Agent
DB_PATH = _central.db_path()          # المصدر الرسمي الحي (يتجاوزه POS_LIVE_DB فقط)
STAGNANT_DAYS = 90          # تعريف الراكد: لم يُبع أبدًا أو آخر بيع أقدم من 90 يومًا
BUNDLE_DISCOUNT = 0.15      # خصم مقترح للباقة (15%)
CROSS_DISCOUNT = 0.10       # خصم مقترح للباقة المزدوجة مع الأكثر مبيعًا (10%)
CAP = 8


def _ro_conn() -> sqlite3.Connection:
    """اتصال قراءة فقط بالمصدر الرسمي الحي — يرفض أي مسار قديم صراحةً."""
    return _central.open_readonly()


def _fmt(n) -> str:
    try:
        f = float(n)
        return str(int(f)) if f == int(f) else f"{f:.2f}"
    except (TypeError, ValueError):
        return str(n)


def _cap(items: List[str]) -> str:
    if len(items) <= CAP:
        return "\n".join(items)
    return "\n".join(items[:CAP]) + f"\n… و {len(items) - CAP} أخرى"


def _sales_by_product(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """مبيعات كل منتج: مرات البيع + الكمية + آخر بيع (من order_items الحقيقية)."""
    rows = conn.execute(
        "SELECT p.id, p.name, p.category, p.price_retail, "
        "COUNT(oi.id) AS times_sold, COALESCE(SUM(oi.qty), 0) AS total_qty, "
        "MAX(o.date) AS last_sale "
        "FROM products p "
        "LEFT JOIN order_items oi ON oi.product_id = p.id "
        "LEFT JOIN orders o ON oi.order_id = o.id AND o.status != 'Cancelled' "
        "GROUP BY p.id ORDER BY p.id"
    ).fetchall()
    return [dict(r) for r in rows]


def _is_stagnant(row: Dict[str, Any]) -> bool:
    if not row["times_sold"]:
        return True
    ls = (row["last_sale"] or "")[:10]
    try:
        age = (date.today() - date.fromisoformat(ls)).days if ls else None
    except ValueError:
        age = None
    return age is None or age >= STAGNANT_DAYS


class MarketingAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="marketing",
            name="مدير التسويق (Marketing Genius)",
            keywords=[
                "راكد", "راكده", "رواكد", "منتجات راكدة", "باقه", "باقة", "باقات",
                "عرض", "عروض", "خصم", "تسويق", "ترويج", "اعلان", "إعلان",
                "محفظه + بوكس", "محفظة + بوكس", "bundle", "bundles", "marketing",
                "حملة", "campaign", "اليوم الوطني", "مناسبة",
            ],
            phase=5,
        )

    # -------------------------------------------------------------- ردود
    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"🎯 {title}\n{body}", "action": "marketing_report", "payload": {}}

    def _stagnant_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = _sales_by_product(conn)
        stagnant = [r for r in rows if _is_stagnant(r)]
        never = [r for r in stagnant if not r["times_sold"]]
        priced = [r for r in stagnant if (r["price_retail"] or 0) > 0]
        body = [
            f"• إجمالي المنتجات: {_fmt(len(rows))}",
            f"• راكدة (لم تُبع أبدًا أو آخر بيع أقدم من {STAGNANT_DAYS} يومًا): {_fmt(len(stagnant))}"
            f" — منها «لم تُبع أبدًا»: {_fmt(len(never))}",
            f"• الراكدة ذات سعر قطاعي معتبر (مرشحة للباقات): {_fmt(len(priced))}",
        ]
        if priced:
            body.append("• أمثلة من الراكدة (بأسعارها الحقيقية):")
            body.append("  " + _cap([
                f"{r['name'].strip()} ({r['category'] or 'بلا تصنيف'}) — قطاعي {_fmt(r['price_retail'])}"
                + (f" | آخر بيع {(r['last_sale'] or '')[:10]}" if r["times_sold"] else " | لم تُبع أبدًا")
                for r in priced
            ]))
        body.append(
            "💡 قولي «اقترح باقات» وأجمع لك الراكدة في عروض مكمّلة بخصم مقترح — "
            "كلها بانتظار اعتمادك، ولا أغيّر أي سعر من نفسي."
        )
        return self._reply("تحليل المنتجات الراكدة", "\n".join(body))

    def _bundle_proposals(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = _sales_by_product(conn)
        stagnant_priced = [
            r for r in rows if _is_stagnant(r) and (r["price_retail"] or 0) > 0
        ]
        top_sellers = [r for r in rows if r["times_sold"]]  # عليه مبيعات
        top_sellers.sort(key=lambda r: r["total_qty"], reverse=True)
        if not stagnant_priced:
            return self._reply(
                "اقتراح الباقات", "✅ لا منتجات راكدة ذات سعر معتبر — مفيش حاجة نعملها باقات دلوقتي.")

        # أولوية: باقة الهدية الشهيرة (محفظة + بوكس + ميدالية) لو موجودة فعلاً
        proposals: List[Dict[str, Any]] = []

        def find(name_like: str) -> Optional[Dict[str, Any]]:
            hits = [r for r in stagnant_priced if name_like in (r["name"] or "")]
            return hits[0] if hits else None

        gift_hits = [
            find(k) for k in ("محفظ", "بوكس", "ميدالي", "بصام")
        ]
        gift = [g for g in gift_hits if g]
        seen: set = set()
        gift_unique = []
        for g in gift:
            if g["id"] not in seen:
                seen.add(g["id"])
                gift_unique.append(g)
        if len(gift_unique) >= 2:
            total = sum(float(g["price_retail"]) for g in gift_unique[:3])
            proposals.append({
                "name": "باقة الهدية 🎁: " + " + ".join(
                    g["name"].strip() for g in gift_unique[:3]),
                "items": gift_unique[:3],
                "total": total,
                "discount": BUNDLE_DISCOUNT,
            })

        # باقة عامة: 3 راكدة من تصنيفات مختلفة (الأغلى أولًا لتنويع القيمة)
        pool = [r for r in stagnant_priced if r["id"] not in seen]
        pool.sort(key=lambda r: float(r["price_retail"]), reverse=True)
        cats_seen, picked = set(), []
        for r in pool:
            c = (r["category"] or "بلا تصنيف")
            if c in cats_seen:
                continue
            picked.append(r)
            cats_seen.add(c)
            seen.add(r["id"])
            if len(picked) == 3:
                break
        if len(picked) >= 2:
            total = sum(float(r["price_retail"]) for r in picked)
            proposals.append({
                "name": "باقة متنوعة: " + " + ".join(r["name"].strip() for r in picked),
                "items": picked,
                "total": total,
                "discount": BUNDLE_DISCOUNT,
            })

        # باقة جذب: الأكثر مبيعًا + راكدة بخصم أخف
        if top_sellers and pool:
            hero = top_sellers[0]
            side = next((r for r in pool if r["id"] not in seen), None)
            if side:
                total = float(hero["price_retail"] or 0) + float(side["price_retail"])
                proposals.append({
                    "name": f"عرض جذب: {hero['name'].strip()} (الأكثر مبيعًا ×{_fmt(hero['total_qty'])}) "
                            f"+ {side['name'].strip()} (راكد)",
                    "items": [hero, side],
                    "total": total,
                    "discount": CROSS_DISCOUNT,
                })

        if not proposals:
            return self._reply(
                "اقتراح الباقات",
                "الراكدة المتاحة قليلة أو متشابهة التصنيف — ما قدرتش أركّب باقة منطقية. "
                "قولي «المنتجات الراكدة» تشوف القائمة بالتفصيل.",
            )
        body = ["اقتراحات باقات من منتجاتك الحقيقية (كلها معلَّقة على اعتمادك):"]
        for pr in proposals:
            final = round(pr["total"] * (1 - pr["discount"]), 2)
            body.append(
                f"\n🎁 {pr['name']}\n"
                f"   القيمة العادية: {_fmt(pr['total'])} جنيه"
                f" → بخصم {int(pr['discount'] * 100)}%: **{_fmt(final)} جنيه**\n"
                f"   التوفير: {_fmt(round(pr['total'] - final, 2))} جنيه"
            )
        body.append(
            "\n🔒 دي اقتراحات تسويقية فقط — لا تُنشأ باقة ولا يتغير أي سعر فعلي إلا بأمرك "
            "الصريح عبر القناة الرسمية."
        )
        return self._reply("اقتراح الباقات (Bundles)", "\n".join(body))

    def _overview(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = _sales_by_product(conn)
        stagnant = [r for r in rows if _is_stagnant(r)]
        movers = [r for r in rows if r["times_sold"]]
        movers.sort(key=lambda r: r["total_qty"], reverse=True)
        by_cat: Dict[str, int] = {}
        for r in stagnant:
            c = (r["category"] or "بلا تصنيف")
            by_cat[c] = by_cat.get(c, 0) + 1
        body = [
            f"• خريطة الحركة: {_fmt(len(movers))} منتج عليه مبيعات | {_fmt(len(stagnant))} راكد "
            f"(من إجمالي {_fmt(len(rows))})",
        ]
        if movers:
            body.append("• المحرّكات (الأعلى كمية): " + "، ".join(
                f"{m['name'].strip()} ×{_fmt(m['total_qty'])}" for m in movers[:5]))
        if by_cat:
            top_cats = sorted(by_cat.items(), key=lambda kv: -kv[1])[:5]
            body.append("• الراكدة بالتصنيف: " + "، ".join(f"{c} ({n})" for c, n in top_cats))
        body.append(
            "💡 أفكار مبنية على أرقامك: (1) «اقترح باقات» لتجميع الراكدة بخصم، "
            "(2) عرض موسمي على أعلى تصنيف راكد، (3) ربط الراكدة مع الأكثر مبيعًا. "
            "قولي أي واحدة ونفصّلها — والتنفيذ الفعلي (تغيير أسعار/إنشاء أصناف باقة) "
            "لا يتم إلا بأمرك عبر القناة الرسمية."
        )
        return self._reply("نظرة تسويقية عامة", "\n".join(body))

    # -------------------------------------------------------------- التوجيه
    def handle(self, text, ctx=None):
        t = (text or "").lower()
        try:
            conn = _ro_conn()
        except Exception as exc:
            return {
                "reply": f"❌ تعذر فتح قاعدة البيانات للقراءة ({type(exc).__name__}) — ما افترضشت أي نتيجة.",
                "action": None, "payload": {},
            }
        try:
            if any(k in t for k in ("باقه", "باقة", "باقات", "bundle", "محفظه + بوكس", "محفظة + بوكس")):
                return self._bundle_proposals(conn)
            if any(k in t for k in ("راكد", "راكده", "رواكد")):
                return self._stagnant_report(conn)
            # عرض/خصم/تسويق/اعلان/حملة → النظرة العامة + إرشاد
            return self._overview(conn)
        except Exception as exc:
            return {
                "reply": f"❌ فشل التحليل التسويقي ({type(exc).__name__}: {exc}) — ما افترضشت أي نتيجة. التفاصيل في سجل الخبرة.",
                "action": None, "payload": {},
            }
        finally:
            conn.close()
