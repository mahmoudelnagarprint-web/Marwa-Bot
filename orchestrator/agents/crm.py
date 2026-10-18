# -*- coding: utf-8 -*-
"""CRM & SCM Agent (مسؤول العلاقات) — Phase 3 FULL BUILD.
- ملف العميل: الرصيد والنوع وعدد الطلبات وآخر طلب وأكثر المنتجات طلبًا وآخر الطلبات.
- متابعة حالات الطلبات: قيد التجهيز / جاهز / تم التسليم (عدد كل حالة + المفتوح بأعماره).
- تنبيهات المتأخر: تعريف المالك المعتمد — طلب مفتوح (قيد تجهيز أو جاهز) مرّ على
  orders.date أكثر من 3 أيام (delivery_date غير مستخدم). عند وجود متأخر: أعرض
  الإجراء المقترح وأنت تأمر — لا أنفّذ شيئًا بنفسي أبدًا.
قواعد صارمة: قراءة فقط 100% (mode=ro)، لا أرقام هواتف في الردود أبدًا،
ولا بيانات مخترعة — فشل القراءة يُبلَّغ بصدق.
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
OPEN_STATUSES = ("Under Preparation", "Ready")
OVERDUE_DAYS = 3        # تعريف المالك المعتمد للمتأخر (من orders.date)
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


def _age_days(date_str: Optional[str]) -> Optional[int]:
    """عمر الطلب بالأيام من orders.date (أول 10 أحرف YYYY-MM-DD)."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat((date_str or "")[:10])
        return (date.today() - d).days
    except ValueError:
        return None


def _cap(items: List[str]) -> str:
    if len(items) <= CAP:
        return "\n".join(items)
    return "\n".join(items[:CAP]) + f"\n… و {len(items) - CAP} أخرى"


class CrmAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="crm",
            name="مسؤول العلاقات (CRM & SCM)",
            keywords=[
                "عميل", "عملاء", "حساب عميل", "رصيد عميل", "ملف العميل", "تاريخ العميل",
                "افضل منتجات", "أفضل منتجات", "الاكثر طلب", "أكثر طلب",
                "حاله الطلب", "حالة الطلب", "طلبات اليوم", "الطلبات", "طلبات",
                "جاهز", "استلام", "تسليم", "متاخر", "متأخر", "متاخره", "متأخرة",
                "تذكير", "reminder", "client", "order status", "crm",
                "فلوس", "مديون",
            ],
            phase=3,
        )

    # -------------------------------------------------------------- مساعدات
    @staticmethod
    def _open_orders(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT o.id, o.status, o.date, o.total_amount, c.name AS client_name "
            "FROM orders o LEFT JOIN clients c ON c.id = o.client_id "
            "WHERE o.status IN (?, ?) ORDER BY o.id",
            OPEN_STATUSES,
        ).fetchall()
        out = []
        for r in rows:
            o = dict(r)
            o["age_days"] = _age_days(o.get("date"))
            out.append(o)
        return out

    def _match_clients(self, conn: sqlite3.Connection, text: str) -> List[Dict[str, Any]]:
        """ابحث عن أسماء عملاء حقيقية داخل نص الرسالة (بلا هواتف)."""
        rows = conn.execute("SELECT id, name FROM clients").fetchall()
        t = (text or "")
        matches = []
        for r in rows:
            nm = (r["name"] or "").strip()
            if nm and len(nm) >= 2 and nm in t:
                matches.append({"id": r["id"], "name": nm})
        return matches

    # -------------------------------------------------------------- تقارير
    def _overdue_report(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        opens = self._open_orders(conn)
        overdue = [o for o in opens if (o["age_days"] or 0) > OVERDUE_DAYS]
        if not overdue:
            return self._reply(
                "تنبيهات المتأخر",
                f"✅ لا طلبات متأخرة. (التعريف المعتمد: طلب مفتوح مرّ عليه أكثر من "
                f"{OVERDUE_DAYS} أيام من تاريخ الطلب. المفتوح حاليًا: {_fmt(len(opens))}).",
            )
        ready_late = [o for o in overdue if o["status"] == "Ready"]
        body = [f"⚠️ تنبيه: {_fmt(len(overdue))} طلب متأخر (أكثر من {OVERDUE_DAYS} أيام وهو مفتوح):"]
        body.append(_cap([
            f"#{o['id']} {o['client_name'] or '—'} | {o['status']} | {_fmt(o['total_amount'])} جنيه"
            f" | عمره {o['age_days']} يوم"
            for o in overdue
        ]))
        if ready_late:
            body.append(f"منها {_fmt(len(ready_late))} جاهزة متأخرة في التسليم.")
        body.append(
            "🔒 ما أنفّذ شيئًا بنفسي — اقتراحي: نأمر بتسليمها أو تحديث حالتها عبر القناة "
            "الرسمية للكتابة بعد تأكيدك. قولي الأمر وأنا أجهزه لك."
        )
        return self._reply("تنبيهات المتأخر", "\n".join(body))

    def _status_overview(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        counts = {dict(r)["status"]: dict(r)["c"] for r in conn.execute(
            "SELECT status, COUNT(*) AS c FROM orders GROUP BY status ORDER BY c DESC"
        ).fetchall()}
        opens = self._open_orders(conn)
        body = ["• حالات الطلبات:"]
        body += [f"  {self._mark(s, c)} {s}: {_fmt(c)}" for s, c in counts.items()] or ["  (لا طلبات)"]
        if opens:
            body.append(f"• المفتوح الآن ({_fmt(len(opens))}):")
            body.append("  " + _cap([
                f"#{o['id']} {o['client_name'] or '—'} | {o['status']} | "
                f"{_fmt(o['total_amount'])} جنيه | عمره {o['age_days'] if o['age_days'] is not None else '؟'} يوم"
                for o in opens
            ]))
        else:
            body.append("• لا طلبات مفتوحة حاليًا — كل شيء مسلَّم.")
        return self._reply("متابعة حالات الطلبات", "\n".join(body))

    @staticmethod
    def _mark(status: str, count: int) -> str:
        if status in OPEN_STATUSES and count:
            return "🟡"
        return "✅" if status == "Delivered" or not count else "•"

    def _today_orders(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        today = date.today().isoformat()
        rows = conn.execute(
            "SELECT o.id, o.status, o.total_amount, c.name AS client_name "
            "FROM orders o LEFT JOIN clients c ON c.id = o.client_id "
            "WHERE o.date LIKE ? ORDER BY o.id",
            (today + "%",),
        ).fetchall()
        items = [dict(r) for r in rows]
        if not items:
            return self._reply(
                "طلبات اليوم",
                f"✅ لا طلبات مسجَّلة اليوم ({today}) — آخر طلب في قاعدة البيانات سليم.",
            )
        total = sum(float(i["total_amount"] or 0) for i in items)
        body = [f"• طلبات اليوم ({today}): {_fmt(len(items))} طلب بإجمالي {_fmt(total)} جنيه"]
        body.append(_cap([
            f"#{i['id']} {i['client_name'] or '—'} | {i['status']} | {_fmt(i['total_amount'])} جنيه"
            for i in items
        ]))
        return self._reply("طلبات اليوم", "\n".join(body))

    def _ready_waiting(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        opens = self._open_orders(conn)
        ready = [o for o in opens if o["status"] == "Ready"]
        if not ready:
            return self._reply(
                "الجاهز بانتظار التسليم",
                "✅ لا طلبات بحالة «جاهز» بانتظار التسليم حاليًا.",
            )
        body = [f"• جاهز بانتظار التسليم: {_fmt(len(ready))} طلب:"]
        body.append(_cap([
            f"#{o['id']} {o['client_name'] or '—'} | {_fmt(o['total_amount'])} جنيه"
            + (f" | ⚠️ متأخر في التسليم ({o['age_days']} يوم)" if (o['age_days'] or 0) > OVERDUE_DAYS
               else f" | عمره {o['age_days']} يوم")
            for o in ready
        ]))
        return self._reply("الجاهز بانتظار التسليم", "\n".join(body))

    def _debtors_overview(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        rows = conn.execute(
            "SELECT id, name, balance FROM clients WHERE balance > 0 ORDER BY balance DESC"
        ).fetchall()
        debtors = [dict(r) for r in rows]
        total = round(sum(float(d["balance"] or 0) for d in debtors), 2)
        if not debtors:
            return self._reply("العملاء اللي عليهم فلوس", "✅ لا مديونيات — كل الأرصدة صفر أو أقل.")
        body = [f"• عملاء عليهم فلوس: {_fmt(len(debtors))} بإجمالي {_fmt(total)} جنيه:"]
        body.append(_cap([
            f"{d['name'].strip()}: {_fmt(d['balance'])} جنيه" for d in debtors
        ]))
        return self._reply("العملاء اللي عليهم فلوس", "\n".join(body))

    def _client_profile(self, conn: sqlite3.Connection, client_id: int, name: str) -> Dict[str, Any]:
        row = conn.execute(
            "SELECT id, name, type, balance FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not row:
            return self._reply("ملف العميل", f"❌ العميل غير موجود — ما افترضتش بيانات.")
        c = dict(row)
        stats = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status IN (?, ?) THEN 1 ELSE 0 END) AS opened "
            "FROM orders WHERE client_id = ?",
            (*OPEN_STATUSES, client_id),
        ).fetchone()
        total_orders = stats["total"] or 0
        open_orders = stats["opened"] or 0
        last = conn.execute(
            "SELECT id, date, status, total_amount FROM orders WHERE client_id = ? ORDER BY id DESC LIMIT 1",
            (client_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT oi.product_name, SUM(oi.qty) AS q FROM order_items oi "
            "JOIN orders o ON o.id = oi.order_id WHERE o.client_id = ? "
            "GROUP BY oi.product_name ORDER BY q DESC LIMIT 5",
            (client_id,),
        ).fetchall()
        recent = conn.execute(
            "SELECT id, status, date, total_amount FROM orders WHERE client_id = ? ORDER BY id DESC LIMIT 5",
            (client_id,),
        ).fetchall()
        body = [
            f"• الاسم: {c['name'].strip()} ({'جملة' if c['type'] == 'Wholesale' else 'قطاعي'})",
            f"• الرصيد الحالي: {_fmt(c['balance'])} جنيه",
            f"• طلباته: {_fmt(total_orders)} (منها {_fmt(open_orders)} مفتوحة الآن)",
        ]
        if last:
            body.append(
                f"• آخر طلب: #{last['id']} بتاريخ {(last['date'] or '')[:10]} "
                f"بحالة {last['status']} بإجمالي {_fmt(last['total_amount'])} جنيه"
            )
        if top:
            body.append("• أكثر المنتجات طلبًا له:")
            body.append("  " + "\n  ".join(
                f"{t['product_name']}: ×{_fmt(t['q'])}" for t in top))
        if recent:
            body.append("• آخر الطلبات:")
            body.append("  " + "\n  ".join(
                f"#{r['id']} | {r['status']} | {(r['date'] or '')[:10]} | {_fmt(r['total_amount'])} جنيه"
                for r in recent))
        return self._reply(f"ملف العميل: {c['name'].strip()}", "\n".join(body))

    def _clients_overview(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        total = conn.execute("SELECT COUNT(*) AS c FROM clients").fetchone()["c"]
        types = {dict(r)["t"]: dict(r)["c"] for r in conn.execute(
            "SELECT type AS t, COUNT(*) AS c FROM clients GROUP BY type"
        ).fetchall()}
        debtors = [dict(r) for r in conn.execute(
            "SELECT name, balance FROM clients WHERE balance > 0 ORDER BY balance DESC LIMIT 5"
        ).fetchall()]
        body = [
            f"• إجمالي العملاء: {_fmt(total)}",
            "• بالأنواع: " + "، ".join(f"{t} = {_fmt(c)}" for t, c in types.items()),
        ]
        if debtors:
            body.append("• أعلى مديونيات: " + "، ".join(
                f"{d['name'].strip()} ({_fmt(d['balance'])})" for d in debtors))
        body.append("لملف عميل بالتفصيل قولي: «شوف ملف عميل [الاسم]».")
        return self._reply("نظرة عامة على العملاء", "\n".join(body))

    # -------------------------------------------------------------- التوجيه
    def handle(self, text, ctx=None):
        t = (text or "")
        try:
            conn = _ro_conn()
        except Exception as exc:
            return {
                "reply": f"❌ تعذر فتح قاعدة البيانات للقراءة ({type(exc).__name__}) — ما افترضشت أي نتيجة.",
                "action": None, "payload": {},
            }
        try:
            tl = t.lower()
            if any(k in tl for k in ("متاخر", "متأخر", "تذكير", "reminder")):
                return self._overdue_report(conn)
            if "طلبات اليوم" in tl:
                return self._today_orders(conn)
            if "جاهز" in tl:
                return self._ready_waiting(conn)
            if ("فلوس" in tl or "مديون" in tl) and "عميل" in tl or "عليهم فلوس" in tl:
                return self._debtors_overview(conn)
            if any(k in tl for k in ("حاله الطلب", "حالة الطلب", "الطلبات", "طلبات", "order status")):
                return self._status_overview(conn)
            # ملف عميل محدد: ابحث عن اسم حقيقي داخل النص
            matches = self._match_clients(conn, t)
            if len(matches) == 1:
                return self._client_profile(conn, matches[0]["id"], matches[0]["name"])
            if len(matches) > 1:
                names = "، ".join(m["name"] for m in matches[:8])
                return self._reply(
                    "ملف العميل",
                    f"لقيت أكتر من عميل في كلامك: {names} — حدد الاسم بدقة وأنا أعرض الملف.",
                )
            if any(k in tl for k in ("عميل", "عملاء", "client")):
                return self._clients_overview(conn)
            return self._clients_overview(conn)
        except Exception as exc:
            return {
                "reply": f"❌ فشل فحص العلاقات ({type(exc).__name__}: {exc}) — ما افترضشت أي نتيجة. التفاصيل في سجل الخبرة.",
                "action": None, "payload": {},
            }
        finally:
            conn.close()

    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"🤝 {title}\n{body}", "action": "crm_report", "payload": {}}
