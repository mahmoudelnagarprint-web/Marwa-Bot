# -*- coding: utf-8 -*-
"""موديول ورشة النجار برنت — R1 (Elnagar Print).

وحدة أعمال مستقلة تمامًا (Bounded Context): جداول ws_* فقط، خدمة خاصة،
قائمة بوت وصفحة ويب خاصة — صفر تشابك مع منطق المحل (Retail).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from nb import db

STATUS_FLOW = ["quote", "confirmed", "design", "production", "finishing", "ready", "delivered"]
STATUS_LABELS = {
    "quote": "🔖 عرض سعر", "confirmed": "✔️ مؤكد", "design": "🎨 تصميم",
    "production": "⚙️ تشغيل (ليزر/CNC)", "finishing": "🖌️ تشطيب",
    "ready": "📦 جاهز للتسليم", "delivered": "🏁 تم التسليم", "cancelled": "✖️ ملغي",
}
MACHINE_LABELS = {"laser": "🔥 ليزر", "cnc": "🤖 CNC", "print": "🖨️ طباعة",
                  "engraving": "✒️ حفر", "vinyl": "📐 فينيل", "other": "🧩 أخرى"}


# ------------------------------------------------------------------ customers
def ensure_customer(name: str, phone: Optional[str] = None) -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("اسم العميل مطلوب")
    phone = (phone or "").strip() or None
    if phone:
        row = db.q("SELECT id FROM ws_customers WHERE phone = %s", (phone,), one=True)
        if row:
            db.x("UPDATE ws_customers SET name=%s WHERE id=%s", (name, row["id"]))
            return row["id"]
    row = db.q("SELECT id FROM ws_customers WHERE name = %s", (name,), one=True)
    if row:
        if phone:
            db.x("UPDATE ws_customers SET phone=%s WHERE id=%s", (phone, row["id"]))
        return row["id"]
    return db.q("INSERT INTO ws_customers(name, phone) VALUES (%s,%s) RETURNING id",
                (name, phone), one=True)["id"]


def list_customivers(limit: int = 100) -> List[Dict[str, Any]]:
    return db.q("""SELECT c.*, (SELECT COUNT(*) FROM ws_jobs j WHERE j.customer_id = c.id) AS jobs
                   FROM ws_customers c ORDER BY c.id DESC LIMIT %s""", (limit,))


# ------------------------------------------------------------------ jobs
def create_job(title: str, customer: Optional[str] = None, phone: Optional[str] = None,
               description: str = "", machine_type: str = "other", qty: float = 1,
               price: float = 0, due_date: Optional[str] = None,
               priority: str = "normal", notes: str = "") -> int:
    if not (title or "").strip():
        raise ValueError("وصف الشغلانة مطلوب")
    cid = ensure_customer(customer, phone) if customer else None
    jid = db.q(
        """INSERT INTO ws_jobs(customer_id, title, description, machine_type, qty,
                               price, due_date, priority, notes, status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'quote') RETURNING id""",
        (cid, title.strip()[:300], description, machine_type if machine_type in MACHINE_LABELS else "other",
         float(qty or 1), float(price or 0), due_date or None, priority, notes), one=True)["id"]
    db.x("UPDATE ws_jobs SET job_no = %s WHERE id = %s", (f"WS-{jid:04d}", jid))
    db.x("""INSERT INTO ws_job_events(job_id, prev_status, new_status, detail)
             VALUES (%s, NULL, 'quote', %s)""", (jid, "إنشاء الشغلانة"))
    return jid


def advance_job(jid: int, new_status: str, detail: str = "") -> Dict[str, Any]:
    job = db.q("SELECT * FROM ws_jobs WHERE id = %s", (jid,), one=True)
    if not job:
        raise ValueError(f"مفيش شغلانة رقم {jid}")
    if new_status not in STATUS_LABELS:
        raise ValueError("حالة غير معروفة")
    delivered = "now()" if new_status == "delivered" else "NULL"
    db.x(f"""UPDATE ws_jobs SET status=%s, updated_at=now(), delivered_at={delivered}
             WHERE id=%s""", (new_status, jid))
    db.x("""INSERT INTO ws_job_events(job_id, prev_status, new_status, detail)
             VALUES (%s,%s,%s,%s)""",
         (jid, job["status"], new_status, detail or ""))
    return get_job(jid)


def next_statuses(jid_or_status: Any) -> List[str]:
    if isinstance(jid_or_status, int):
        job = db.q("SELECT status FROM ws_jobs WHERE id=%s", (jid_or_status,), one=True)
        status = job["status"] if job else None
    else:
        status = jid_or_status
    try:
        idx = STATUS_FLOW.index(status)
        return STATUS_FLOW[idx + 1: idx + 2] + (["cancelled"] if status != "cancelled" else [])
    except ValueError:
        return []


def get_job(jid: int) -> Dict[str, Any]:
    return db.q("""SELECT j.*, c.name AS customer_name, c.phone AS customer_phone
                   FROM ws_jobs j LEFT JOIN ws_customers c ON c.id = j.customer_id
                   WHERE j.id = %s""", (jid,), one=True)


def list_jobs(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    sql = """SELECT j.*, c.name AS customer_name FROM ws_jobs j
             LEFT JOIN ws_customers c ON c.id = j.customer_id"""
    params: List[Any] = []
    if status:
        sql += " WHERE j.status = %s"
        params.append(status)
    else:
        sql += " WHERE j.status NOT IN ('delivered','cancelled')"
    sql += " ORDER BY j.due_date NULLS LAST, j.id DESC LIMIT %s"
    params.append(limit)
    return db.q(sql, params)


def job_events(jid: int) -> List[Dict[str, Any]]:
    return db.q("SELECT * FROM ws_job_events WHERE job_id=%s ORDER BY id DESC", (jid,))


def pay_job(jid: int, amount: float) -> Dict[str, Any]:
    db.x("UPDATE ws_jobs SET paid = paid + %s, updated_at=now() WHERE id=%s", (float(amount), jid))
    db.x("""INSERT INTO ws_job_events(job_id, prev_status, new_status, detail)
             VALUES (%s, NULL, NULL, %s)""", (jid, f"دفعة {amount}"))
    return get_job(jid)


# ------------------------------------------------------------------ materials
def add_material(name: str, kind: str = "other", unit: str = "قطعة", qty: float = 0,
                 min_qty: float = 0, unit_cost: float = 0, supplier: str = "") -> int:
    if not (name or "").strip():
        raise ValueError("اسم الخامة مطلوب")
    return db.q("""INSERT INTO ws_materials(name, kind, unit, qty, min_qty, unit_cost, supplier)
                   VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (name.strip(), kind, unit, float(qty), float(min_qty),
                 float(unit_cost), supplier), one=True)["id"]


def list_materials(limit: int = 200) -> List[Dict[str, Any]]:
    return db.q("""SELECT *, (qty <= min_qty) AS low FROM ws_materials
                   ORDER BY low DESC, name ASC LIMIT %s""", (limit,))


def adjust_material(mid: int, delta: float, reason: str = "", job_id: Optional[int] = None) -> Dict[str, Any]:
    db.x("UPDATE ws_materials SET qty = qty + %s, updated_at=now() WHERE id=%s", (float(delta), mid))
    db.x("""INSERT INTO ws_material_logs(material_id, job_id, delta, reason)
             VALUES (%s,%s,%s,%s)""", (mid, job_id, float(delta), reason))
    return db.q("SELECT * FROM ws_materials WHERE id=%s", (mid,), one=True)


def use_material(jid: int, mid: int, qty: float) -> None:
    """صرف خامة على شغلانة: خصم من المخزون + تسجيل الاستهلاك."""
    mat = db.q("SELECT * FROM ws_materials WHERE id=%s", (mid,), one=True)
    if not mat:
        raise ValueError("خامة غير موجودة")
    db.x("""INSERT INTO ws_job_materials(job_id, material_id, qty, unit_cost)
             VALUES (%s,%s,%s,%s)""", (jid, mid, float(qty), float(mat["unit_cost"] or 0)))
    adjust_material(mid, -abs(float(qty)), f"صرف على WS-{jid:04d}", job_id=jid)


def low_stock() -> List[Dict[str, Any]]:
    return db.q("""SELECT * FROM ws_materials WHERE qty <= min_qty
                   ORDER BY qty ASC LIMIT 30""")


# ------------------------------------------------------------------ stats
def stats() -> Dict[str, Any]:
    by_status = {r["status"]: r["c"] for r in db.q(
        "SELECT status, COUNT(*) c FROM ws_jobs WHERE status NOT IN ('delivered','cancelled') GROUP BY status")}
    return {
        "open_jobs": sum(by_status.values()),
        "by_status": by_status,
        "customers": db.scalar("SELECT COUNT(*) FROM ws_customers") or 0,
        "materials_low": len(low_stock()),
        "delivered_revenue": db.scalar(
            "SELECT COALESCE(SUM(price),0) FROM ws_jobs WHERE status='delivered'") or 0,
        "unpaid_delivered": db.scalar(
            "SELECT COALESCE(SUM(price - paid),0) FROM ws_jobs WHERE status='delivered'") or 0,
    }


def format_job(j: Dict[str, Any]) -> str:
    line = f"{j.get('job_no') or j['id']} — {STATUS_LABELS.get(j['status'], j['status'])} {j['title'][:50]}"
    if j.get("customer_name"):
        line += f" | 👤 {j['customer_name']}"
    if j.get("due_date"):
        line += f" | 📅 {j['due_date']}"
    if j.get("price"):
        line += f" | 💰 {j['price']}"
    return line
