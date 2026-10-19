# -*- coding: utf-8 -*-
"""CFO / Ledger Agent (المدير المالي) — Phase 4 FULL BUILD.
- الخزينة والدخل والمصروف والربح: بنفس صيغ get_financial_stats الرسمية الفعّالة
  (شيفت مفتوح: daily_shifts.status='open'، دخل = Income/payment، مصروف = Expense،
  ربح = دخل − COGS حيث COALESCE(last_cost_price, price_wholesale, 0) —
  وlast_cost_price=0 لكل الأصناف فـCOGS صفر والربح = الدخل).
- الديون والمستحقات: total_debt (كل الأرصدة) + positive_balance_sum للمقارنة.
- طرق الدفع: من داخل notes (Cash/Vodafone/Instapay/Credit — لا عمود مستقل).
- المصروفات: عرض + تجميع بـexpense_type؛ والتسجيل = اقتراح يمر بالقناة الرسمية فقط.
- التسعير الديناميكي: الأكثر مبيعًا بكمياتهم وأسعارهم الحالية — اقتراح مراجعة
  معلَّق على موافقة المالك. الهوامش الحقيقية غير متاحة (قرار المالك: التكلفة غير مسجلة).
قواعد صارمة: قراءة فقط 100% (mode=ro) — أي عملية مالية حساسة (تسوية/شطب/تخفيض/
تغيير سعر/تسجيل مصروف) لا تُنفَّذ أبدًا إلا بموافقة المالك الصريحة عبر القناة الرسمية،
وكل تقرير يذكر أن الأرقام مرتبطة بالشيفت المفتوح منذ تاريخه.
"""
from __future__ import annotations

import sqlite3
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
CAP = 10


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


def _shift_opened_at(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT opened_at FROM daily_shifts WHERE status = 'open' LIMIT 1"
    ).fetchone()
    return (row["opened_at"] if row else None) or "1970-01-01 00:00:00"


def _accounting_start(conn: sqlite3.Connection) -> Optional[str]:
    """نافذة الحساب المعتمدة (settings.accounting_start_date = 2026-10-01) —
    نفس منطق الإنتاج (database.get_financial_stats) عشان التقرير يطابق الشاشة بالمليم.
    ترجع None لو الإعداد غير موجود (يُرجع حينها سلوك فتح الشيفت)."""
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'accounting_start_date' LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return None
    val = (row["value"] if row else None)
    if not val:
        return None
    val = str(val).strip()
    if len(val) == 10:      # 'YYYY-MM-DD' → بداية اليوم
        val = val + " 00:00:00"
    return val


def _financial_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """حرفيًا منطق get_financial_stats الفعّال (SELECT فقط) — مُتحقق منه في pos-reader."""
    opened_at = _shift_opened_at(conn)
    acc_start = _accounting_start(conn) or opened_at
    income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE type IN ('Income', 'payment') AND date >= ?", (acc_start,),
    ).fetchone()[0]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions "
        "WHERE type = 'Expense' AND date >= ?", (acc_start,),
    ).fetchone()[0]
    cash_on_hand = income - expense
    shift_cogs = conn.execute(
        "SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0) "
        "FROM order_items oi JOIN orders o ON oi.order_id = o.id "
        "JOIN products p ON oi.product_id = p.id "
        "WHERE o.status != 'Cancelled' AND o.date >= ?", (acc_start,),
    ).fetchone()[0]
    profit = income - shift_cogs
    total_debt = conn.execute(
        "SELECT COALESCE(SUM(COALESCE(balance, 0)), 0) FROM clients"
    ).fetchone()[0]
    positive_sum = conn.execute(
        "SELECT COALESCE(SUM(balance), 0) FROM clients WHERE balance > 0"
    ).fetchone()[0]
    return {
        "opened_at": opened_at, "acc_start": acc_start, "income": income, "expense": expense,
        "cash_on_hand": cash_on_hand, "cogs": shift_cogs, "profit": profit,
        "total_debt": total_debt, "positive_sum": positive_sum,
    }


class CfoAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="cfo",
            name="المدير المالي (CFO / Ledger)",
            keywords=[
                "حسابات", "الخزينة", "خزنه", "خزينة", "مالي", "ماليه",
                "ديون", "مديونيه", "مستحقات", "نقدي", "كاش", "فودافون", "instapay",
                "اجل", "طرق الدفع", "عايز اعرف رصيدي", "مصروف", "مصروفات",
                "ملخص المحاسبه", "ربح", "ارباح", "أرباح", "هوامش",
                "ledger", "cfo", "فاتورة", "تسويه", "حركات", "سجل",
                "مبيعات", "تسعير ديناميكي", "الاكثر مبيع", "أكثر مبيع",
                "شطب", "دين", "تخفيض", "خصم دين",
            ],
            phase=4,
        )

    # -------------------------------------------------------------- ردود
    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"💼 {title}\n{body}", "action": "cfo_report", "payload": {}}

    @staticmethod
    def _shift_note(opened_at: str, acc_start: Optional[str] = None) -> str:
        # نافذة الحساب المعتمدة (2026-10-01) تُذكر صراحةً — والرقم المحسوب من
        # الحركات لا يشمل الرصيد الافتتاحي (دفتر فارس §9 هو المرجع للخزنة الفعلية).
        if acc_start and acc_start != opened_at:
            return (f"📌 الأرقام مرتبطة بنافذة الحساب المعتمدة من {acc_start[:10]} "
                    f"(الرصيد الافتتاحي 5,625 غير محسوب هنا — الخزنة الفعلية في دفتر فارس §9).")
        return f"📌 الأرقام مرتبطة بشيفت مفتوح منذ {opened_at[:16]} بدون إغلاق."

    def _summary_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        s = _financial_stats(conn)
        body = [
            f"• النقد المتاح (دخل − مصروف): {_fmt(s['cash_on_hand'])} جنيه",
            f"• الدخل: {_fmt(s['income'])} جنيه",
            f"• المصروف: {_fmt(s['expense'])} جنيه",
            f"• الربح: {_fmt(s['profit'])} جنيه"
            + (" (= الدخل، لأن تكلفة الأصناف COGS صفر — last_cost_price=0 لكل الأصناف)"
               if abs(s["cogs"]) < 0.01 else ""),
            f"• إجمالي الديون (كل الأرصدة): {_fmt(s['total_debt'])} جنيه — "
            f"منها الموجبة {_fmt(s['positive_sum'])} والفرق {_fmt(s['total_debt'] - s['positive_sum'])} (أرصدة سالبة/دائنة).",
            self._shift_note(s["opened_at"], s.get("acc_start")),
            "الأوامر المتاحة: «ديون»، «طرق الدفع»، «مصروفات»، «الأكثر مبيعًا»، «هوامش»، «حركات».",
        ]
        return self._reply("ملخص الخزينة والمحاسبة", "\n".join(body))

    def _debts_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        s = _financial_stats(conn)
        debtors = [dict(r) for r in conn.execute(
            "SELECT name, balance FROM clients WHERE balance > 0 "
            "ORDER BY balance DESC LIMIT 8"
        ).fetchall()]
        body = [
            f"• إجمالي الديون: {_fmt(s['total_debt'])} جنيه (كل الأرصدة).",
            f"• الدائنون فقط (رصيد موجب): {_fmt(s['positive_sum'])} جنيه.",
        ]
        if debtors:
            body.append("• أعلى المستحقات:")
            body.append("  " + "\n  ".join(
                f"{d['name'].strip()}: {_fmt(d['balance'])} جنيه" for d in debtors))
        body.append(self._shift_note(s["opened_at"], s.get("acc_start")))
        body.append("🔒 أي تسوية/شطب/تخفيض مديونية = بموافقتك الصريحة فقط عبر القناة الرسمية.")
        return self._reply("الديون والمستحقات", "\n".join(body))

    def _payment_methods_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        opened_at = _shift_opened_at(conn)
        acc_start = _accounting_start(conn) or opened_at
        rows = conn.execute(
            "SELECT amount, notes FROM transactions "
            "WHERE type IN ('Income', 'payment') AND date >= ?", (acc_start,),
        ).fetchall()

        def detect(notes: Optional[str]) -> str:
            n = (notes or "").lower()
            if "vodafone" in n:
                return "فودافون كاش"
            if "instapay" in n:
                return "إنستاباي"
            if "cash" in n:
                return "نقدي"
            if "credit" in n:
                return "آجل"
            return "غير محدد"

        agg: Dict[str, Dict[str, float]] = {}
        for r in rows:
            m = detect(r["notes"])
            d = agg.setdefault(m, {"count": 0, "sum": 0.0})
            d["count"] += 1
            d["sum"] += float(r["amount"] or 0)
        if not agg:
            return self._reply(
                "طرق الدفع", "لا دفعات مسجَّلة خلال الشيفت المفتوح." )
        body = ["• توزيع الدفعات خلال الشيفت المفتوح (من داخل notes):"]
        for m, d in sorted(agg.items(), key=lambda kv: -kv[1]["sum"]):
            body.append(f"  {m}: {_fmt(d['count'])} دفعة بإجمالي {_fmt(round(d['sum'], 2))} جنيه")
        body.append(self._shift_note(opened_at, acc_start))
        body.append("ملاحظة: طريقة الدفع بلا عمود مستقل — تُقرأ من نص الحركة، فبعضها «غير محدد».")
        return self._reply("طرق الدفع", "\n".join(body))

    def _expenses_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        opened_at = _shift_opened_at(conn)
        s = _financial_stats(conn)
        acc_start = s.get("acc_start") or opened_at
        last = [dict(r) for r in conn.execute(
            "SELECT id, date, amount, notes, expense_type FROM transactions "
            "WHERE type = 'Expense' ORDER BY date DESC LIMIT 8"
        ).fetchall()]
        by_type = [dict(r) for r in conn.execute(
            "SELECT COALESCE(expense_type, 'غير مصنف') AS et, COUNT(*) AS c, "
            "COALESCE(SUM(amount), 0) AS s FROM transactions "
            "WHERE type = 'Expense' AND date >= ? GROUP BY et ORDER BY s DESC",
            (acc_start,),
        ).fetchall()]
        body = [f"• إجمالي المصروفات خلال النافذة المعتمدة: {_fmt(s['expense'])} جنيه"]
        if by_type:
            body.append("• بالأنواع: " + "، ".join(
                f"{b['et']} = {_fmt(round(b['s'], 2))} ({_fmt(b['c'])})" for b in by_type))
        if last:
            body.append("• آخر المصروفات:")
            body.append("  " + "\n  ".join(
                f"#{e['id']} | {(e['date'] or '')[:16]} | {_fmt(e['amount'])} جنيه"
                f" | {(e['notes'] or '')[:40]}"
                for e in last))
        body.append(
            "🔒 لتسجيل مصروف جديد: ابعت التفاصيل (المبلغ + البيان) وأنا أجهزها كاقتراح "
            "يمر بالقناة الرسمية للكتابة بعد تأكيدك — لا أكتب في الفلوس بنفسي أبدًا."
        )
        body.append(self._shift_note(opened_at, acc_start))
        return self._reply("المصروفات", "\n".join(body))

    def _margins_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        s = _financial_stats(conn)
        zero_cost = conn.execute(
            "SELECT COUNT(*) FROM products "
            "WHERE last_cost_price IS NULL OR last_cost_price = 0"
        ).fetchone()[0]
        total_products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        body = [
            f"• الدخل: {_fmt(s['income'])} جنيه | المصروف: {_fmt(s['expense'])} جنيه",
            f"• الربح المحاسبي: {_fmt(s['profit'])} جنيه",
            f"• تحليل الهوامش الحقيقي: غير متاح — last_cost_price = 0 لـ{_fmt(zero_cost)}"
            f" من {_fmt(total_products)} صنفًا (قرارك المعتمد: لا ربح تقديري من سعر الجملة).",
            "• لتشغيل الهوامش: سجّل تكلفة أهم الأصناف (يوجد سؤال مفتوح بذلك في ملف الأسئلة).",
            self._shift_note(s["opened_at"], s.get("acc_start")),
        ]
        return self._reply("الأرباح والهوامش", "\n".join(body))

    def _top_sellers_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = [dict(r) for r in conn.execute(
            "SELECT oi.product_name, SUM(oi.qty) AS q, SUM(oi.total) AS rev, "
            "MAX(p.price_retail) AS retail "
            "FROM order_items oi JOIN orders o ON oi.order_id = o.id "
            "LEFT JOIN products p ON oi.product_id = p.id "
            "WHERE o.status != 'Cancelled' "
            "GROUP BY oi.product_name ORDER BY q DESC LIMIT 8"
        ).fetchall()]
        total_rev = conn.execute(
            "SELECT COALESCE(SUM(oi.total), 0) FROM order_items oi "
            "JOIN orders o ON oi.order_id = o.id WHERE o.status != 'Cancelled'"
        ).fetchone()[0]
        if not rows:
            return self._reply("الأكثر مبيعًا", "لا مبيعات مسجَّلة.")
        body = [
            f"• الأكثر مبيعًا (إجمالي تاريخي، بلا الملغاة) — إجمالي المبيعات {_fmt(total_rev)} جنيه:",
            "  " + "\n  ".join(
                f"{r['product_name']}: ×{_fmt(r['q'])} | مبيعات {_fmt(round(r['rev'] or 0, 2))} جنيه"
                + (f" | السعر الحالي {_fmt(r['retail'])}" if r["retail"] else "")
                for r in rows),
            "💡 التسعير الديناميكي: دي الأصناف الأعلى طلبًا — لو حابب ترفع سعر أي واحد منها "
            "قولي «اعتمد سعر [الصنف] بـ[X]» وبيتم عبر القناة الرسمية بعد تأكيدك. "
            "لا أغيّر أي سعر من نفسي.",
        ]
        return self._reply("الأكثر مبيعًا + اقتراح التسعير الديناميكي", "\n".join(body))

    def _ledger_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        rows = [dict(r) for r in conn.execute(
            "SELECT id, date, type, category, amount, notes FROM transactions "
            "ORDER BY date DESC, id DESC LIMIT 10"
        ).fetchall()]
        body = [f"• آخر الحركات (من إجمالي {_fmt(total)}):"]
        body.append("  " + "\n  ".join(
            f"#{r['id']} | {(r['date'] or '')[:16]} | {r['type']}"
            f"{(' / ' + r['category']) if r['category'] else ''} | {_fmt(r['amount'])} جنيه"
            f"{(' — ' + (r['notes'] or '')[:36]) if r['notes'] else ''}"
            for r in rows))
        return self._reply("سجل الحركات", "\n".join(body))

    @staticmethod
    def _sensitive_block() -> Dict[str, Any]:
        return {
            "reply": (
                "🔒 إجراء مالي حساس (تسوية/شطب/تخفيض مديونية/تغيير سعر) — "
                "لا يتنفذ إلا بموافقتك الصريحة. ابعتلي: العميل + المبلغ + الإجراء بالظبط، "
                "وأجهزه لك كاقتراح نهائي عبر القناة الرسمية للكتابة، وما يتنفذ إلا لما تقول «اعتمد»."
            ),
            "action": None,
            "payload": {},
        }

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
            # 1) الحساس أولًا
            if any(k in t for k in ("تسويه", "شطب", "شطب دين", "تخفيض", "الغاء مديونيه", "إلغاء مديونية")):
                return self._sensitive_block()
            # 2) تسجيل مصروف = اقتراح فقط (قبل فروع العرض)
            if ("سجل مصروف" in t or "سجل مصاريف" in t or "اضف مصروف" in t or "أضف مصروف" in t):
                return {
                    "reply": (
                        "📝 تجهيز تسجيل مصروف: ابعتلي (المبلغ + البيان + النوع لو فيه)، "
                        "وأنا أعرضه عليك كاقتراح كامل وينتظر كلمة «اعتمد» — ثم يُسجَّل عبر "
                        "القناة الرسمية للكتابة (pos-writer) بسجل تدقيق. لا أكتب في الفلوس بنفسي."
                    ),
                    "action": "propose_expense",
                    "payload": {},
                }
            # 3) الهوامش
            if any(k in t for k in ("هوامش", "هامش", "ارباح", "أرباح")):
                return self._margins_report(conn)
            # 4) التسعير الديناميكي / المبيعات
            if any(k in t for k in ("تسعير ديناميكي", "الاكثر مبيع", "أكثر مبيع", "مبيعات")):
                return self._top_sellers_report(conn)
            # 5) طرق الدفع
            if any(k in t for k in ("طرق الدفع", "فودافون", "instapay", "نقدي", "كاش")):
                return self._payment_methods_report(conn)
            # 6) المصروفات (عرض)
            if "مصروف" in t:
                return self._expenses_report(conn)
            # 7) الديون
            if any(k in t for k in ("ديون", "مديون", "مستحقات")):
                return self._debts_report(conn)
            # 8) الحركات (سجل فقط — لا يخطف «سجل درس»/«سجل الخبرة» الخاصة بالميتا)
            if "حركات" in t or ("سجل" in t and not any(k in t for k in ("مصروف", "درس", "خبرة"))):
                return self._ledger_report(conn)
            # 9) الافتراضي: ملخص الخزينة
            return self._summary_report(conn)
        except Exception as exc:
            return {
                "reply": f"❌ فشل التقرير المالي ({type(exc).__name__}: {exc}) — ما افترضشت أي نتيجة. التفاصيل في سجل الخبرة.",
                "action": None, "payload": {},
            }
        finally:
            conn.close()
