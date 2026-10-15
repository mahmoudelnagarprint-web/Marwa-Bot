# -*- coding: utf-8 -*-
r"""pos-writer — خادم كتابة محكوم لبرنامج النجار برنت (أمر المالك 2026-10-11، مستوى 1).

القواعد:
- كل كتابة عبر الدوال الرسمية (database.py / financial_engine.py) — لا SQL مباشر.
- خطوتان: mode='preview' (يعرض قبل/بعد وينشئ عملية معلقة op_id في logs/pending_ops.json،
  صالحة 12 ساعة)، ثم mode='execute' بـ op_id + confirm='نعم' (كلمة تأكيد المالك في المحادثة).
- كل عملية (معاينة/تنفيذ) تُسجَّل في logs/audit_trail.log.
- الهدف الافتراضي نسخة الاختبار (_sandbox_pos_writer)؛ الحي يتطلب POS_WRITER_TARGET=live
  (بأمر المالك فقط) — العملية المعلقة مقيدة بهدفها فلا تنفَّذ على هدف آخر.
- التشغيل: نفس venv الخاص بـ pos-reader (مكتبة mcp جاهزة فيه).
  & "G:\ai\Naggar Print POS Agent\mcp\pos-reader\.venv\Scripts\python.exe" mcp\pos-writer\server.py
"""
import os
import sys
import json
import time
import secrets
import datetime

WORKSPACE = r"G:\ai\Naggar Print POS Agent"
SANDBOX = os.path.join(WORKSPACE, "_sandbox_pos_writer")
LIVE = r"G:\ai\Elnagar POS"
AUDIT_LOG = os.path.join(WORKSPACE, "logs", "audit_trail.log")
PENDING_FILE = os.path.join(WORKSPACE, "logs", "pending_ops.json")
PENDING_TTL = 12 * 3600  # 12 ساعة — المعاينة تتحمل فرق التوقيت بين الرسائل

TARGET = os.environ.get("POS_WRITER_TARGET", "sandbox").strip().lower()
if TARGET not in ("sandbox", "live"):
    raise SystemExit("POS_WRITER_TARGET must be 'sandbox' or 'live'")
DB_DIR = SANDBOX if TARGET == "sandbox" else LIVE

# database.DB_NAME نسبي — chdir يوجّه الاتصال للقاعدة المطلوبة بدون تعديل database.py
os.chdir(DB_DIR)
sys.path.insert(0, DB_DIR)
import database as db  # الدوال الرسمية فقط

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("pos-writer")

VALID_TYPES = ("Retail", "Wholesale")


# ---------- بنية تحتية: تدقيق + عمليات معلقة (ملف يصمد بين الرسائل) ----------

def _audit(action, tool, detail):
    line = json.dumps({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": TARGET,
        "tool": tool,
        "action": action,
        **detail,
    }, ensure_ascii=False)
    with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _load_pending():
    if not os.path.exists(PENDING_FILE):
        return {}
    try:
        with open(PENDING_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_pending(ops):
    os.makedirs(os.path.dirname(PENDING_FILE), exist_ok=True)
    with open(PENDING_FILE, "w", encoding="utf-8") as fh:
        json.dump(ops, fh, ensure_ascii=False, indent=1)


def _new_op(tool, payload, summary):
    ops = _load_pending()
    now = time.time()
    for k in [k for k, v in ops.items()
              if v.get("target") == TARGET and now - v.get("created", 0) > PENDING_TTL]:
        ops.pop(k, None)
    op_id = "OP-" + secrets.token_hex(3).upper()
    ops[op_id] = {"tool": tool, "target": TARGET, "payload": payload,
                  "summary": summary, "created": now}
    _save_pending(ops)
    _audit("preview", tool, {"op_id": op_id, **summary})
    return op_id


def _take_op(tool, op_id, confirm):
    if (confirm or "").strip() != "نعم":
        raise ValueError("التنفيذ يحتاج confirm='نعم' بعد موافقة المالك الصريحة في المحادثة")
    ops = _load_pending()
    op = ops.get(op_id or "")
    if not op or op["tool"] != tool:
        raise ValueError("op_id غير صالح — اعمل معاينة (mode='preview') أولًا")
    if op.get("target") != TARGET:
        raise ValueError("العملية المعلقة لهدف آخر (%s) وليست %s" % (op.get("target"), TARGET))
    if time.time() - op["created"] > PENDING_TTL:
        ops.pop(op_id, None)
        _save_pending(ops)
        raise ValueError("انتهت صلاحية المعاينة (12 ساعة) — أعد المعاينة")
    ops.pop(op_id, None)
    _save_pending(ops)
    return op


def _exec_result(tool, op_id, result):
    _audit("execute", tool, {"op_id": op_id, **result})
    return {"step": "executed", "op_id": op_id, **result}


# ---------- قراءات مساعدة (SELECT فقط) ----------

def _client_row(client_id):
    conn = db.get_db_connection()
    try:
        r = conn.execute(
            "SELECT id, name, phone, type, notes, balance FROM clients WHERE id = ?",
            (client_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _client_count():
    conn = db.get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    finally:
        conn.close()


def _find_duplicates(name, phone):
    """تداخلات الاسم/الهاتف داخل جدول العملاء (قراءة فقط) — درس 2026-10-11: البحث بالاثنين."""
    hits = []
    conn = db.get_db_connection()
    try:
        if name:
            rows = conn.execute(
                "SELECT id, name, phone, balance FROM clients WHERE name = ?", (name,)).fetchall()
            hits += [{"matched_by": "name", "id": r["id"], "name": r["name"],
                      "phone": r["phone"], "balance": r["balance"]} for r in rows]
        if phone and str(phone).strip():
            rows = conn.execute(
                "SELECT id, name, phone, balance FROM clients WHERE phone = ?",
                (str(phone).strip(),)).fetchall()
            hits += [{"matched_by": "phone", "id": r["id"], "name": r["name"],
                      "phone": r["phone"], "balance": r["balance"]} for r in rows]
        return hits
    finally:
        conn.close()


def _normalize_type(c_type):
    t = (c_type or "").strip().lower()
    if t in ("retail", "قطاعي"):
        return "Retail"
    if t in ("wholesale", "جملة"):
        return "Wholesale"
    raise ValueError("النوع لازم يكون Retail أو Wholesale (وصل: %r)" % c_type)


def _client_blast_radius(client_id):
    """حجم ما سيحذفه delete_client الرسمي: طلبات، أصناف طلبات، حركات، رصيد، مجلد تصاميم."""
    conn = db.get_db_connection()
    try:
        orders = conn.execute("SELECT COUNT(*) FROM orders WHERE client_id = ?",
                              (client_id,)).fetchone()[0]
        items = conn.execute(
            "SELECT COUNT(*) FROM order_items WHERE order_id IN "
            "(SELECT id FROM orders WHERE client_id = ?)", (client_id,)).fetchone()[0]
        txns = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE client_id = ?",
            (client_id,)).fetchone()[0]
        debt = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN type='debt' THEN amount ELSE 0 END),0) "
            "FROM transactions WHERE client_id = ?", (client_id,)).fetchone()[0]
        row = conn.execute("SELECT id, name, phone, type, balance FROM clients WHERE id = ?",
                           (client_id,)).fetchone()
        return {
            "client": dict(row) if row else None,
            "orders": orders, "order_items": items, "transactions": txns,
            "debt_amount": debt,
            "design_folder": "مجلد تصاميم العميل يبقى على القرص (الدالة الرسمية لا تمسحه)",
            "stock_note": "الدالة الرسمية لا ترجع مخزون الطلبات المحذوفة — مثل سلوك البرنامج نفسه",
        }
    finally:
        conn.close()


# ---------- أدوات العملاء (الدوال الرسمية فقط) ----------

def _add_client_impl(name: str, phone: str = "", c_type: str = "Retail",
                     notes: str = "", mode: str = "preview", op_id: str = "",
                     confirm: str = ""):
    """إضافة عميل عبر الدالة الرسمية add_new_client. preview يعرض قبل/بعد؛ execute يحتاج op_id + confirm='نعم'."""
    tool = "posw_add_client"
    c_type = _normalize_type(c_type)
    name = (name or "").strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    dups = _find_duplicates(name, phone)
    summary = {
        "operation": "إضافة عميل (الدالة الرسمية add_new_client)",
        "new_values": {"name": name, "phone": (phone or "").strip(), "type": c_type, "notes": notes},
        "warnings": ["%s: id=%s name=%r phone=%r" % (d["matched_by"], d["id"], d["name"], d["phone"])
                     for d in dups],
        "clients_count_now": _client_count(),
    }
    if mode == "preview":
        op_id = _new_op(tool, {"name": name, "phone": (phone or "").strip(),
                               "c_type": c_type, "notes": notes}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        new_id = db.add_new_client(p["name"], p["phone"], p["c_type"], p["notes"])
        return _exec_result(tool, op_id, {"new_client": _client_row(new_id),
                                          "clients_count_after": _client_count()})
    raise ValueError("mode لازم يكون preview أو execute")


def _update_client_impl(client_id: int, name: str, phone: str, c_type: str,
                        notes: str, mode: str = "preview", op_id: str = "",
                        confirm: str = ""):
    """تعديل بيانات عميل عبر الدالة الرسمية update_client_details (أُصلحت 2026-10-11 ونُقلت للحي بعدها)."""
    tool = "posw_update_client"
    c_type = _normalize_type(c_type)
    name = (name or "").strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    before = _client_row(client_id)
    if before is None:
        raise ValueError("لا يوجد عميل برقم %s" % client_id)
    planned = {"id": client_id, "name": name, "phone": (phone or "").strip(),
               "type": c_type, "notes": notes}
    warnings = []
    if c_type != before["type"]:
        warnings.append("تغيير نوع عميل موجود = مستوى 2 في الميثاق (احترام نوع العميل) — تأكيد صريح")
    if (phone or "").strip() and (phone or "").strip() != (before["phone"] or ""):
        for d in _find_duplicates("", phone):
            warnings.append("الهاتف الجديد يطابق عميلًا موجودًا: id=%s name=%r" % (d["id"], d["name"]))
    summary = {
        "operation": "تعديل عميل (الدالة الرسمية update_client_details)",
        "before": before,
        "planned_after": planned,
        "warnings": warnings,
        "note": "الرصيد لا يتغير بتعديل البيانات",
    }
    if mode == "preview":
        op_id = _new_op(tool, planned, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.update_client_details(p["id"], p["name"], p["phone"], p["type"], p["notes"])
        if not res.get("success"):
            raise ValueError("الدالة الرسمية رفضت التعديل: %s" % res.get("error"))
        return _exec_result(tool, op_id, {"before": before, "after": _client_row(client_id)})
    raise ValueError("mode لازم يكون preview أو execute")


def _delete_client_impl(client_id: int, mode: str = "preview", op_id: str = "",
                        confirm: str = ""):
    """حذف عميل عبر الدالة الرسمية delete_client — preview يعرض كل ما سيُمحى أولًا."""
    tool = "posw_delete_client"
    before = _client_row(client_id)
    if before is None:
        raise ValueError("لا يوجد عميل برقم %s" % client_id)
    radius = _client_blast_radius(client_id)
    summary = {
        "operation": "حذف عميل (الدالة الرسمية delete_client)",
        "client": before,
        "will_delete": {
            "orders": radius["orders"],
            "order_items": radius["order_items"],
            "transactions": radius["transactions"],
            "debt_amount": radius["debt_amount"],
            "balance_at_delete": before["balance"],
        },
        "warnings": [radius["design_folder"], radius["stock_note"],
                     "حذف نهائي — كل حركات العميل وطلباته وأصنافها تُمحى من القاعدة"],
        "irreversible": True,
    }
    if mode == "preview":
        op_id = _new_op(tool, {"client_id": client_id}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        ok = db.delete_client(op["payload"]["client_id"])
        return _exec_result(tool, op_id, {"deleted_client": before,
                                          "deleted_counts": {k: radius[k] for k in ("orders", "order_items", "transactions")},
                                          "clients_count_after": _client_count()})
    raise ValueError("mode لازم يكون preview أو execute")


# ---------- أدوات المنتجات (الدوال الرسمية فقط) ----------

def _product_row(p_id):
    conn = db.get_db_connection()
    try:
        r = conn.execute(
            "SELECT id, name, category, price_retail, price_wholesale, stock_qty, "
            "sort_order, stock, last_cost_price FROM products WHERE id = ?", (p_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _product_count():
    conn = db.get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    finally:
        conn.close()


def _find_duplicate_products(name):
    conn = db.get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, category, price_retail, price_wholesale, stock_qty "
            "FROM products WHERE name = ?", ((name or "").strip(),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _product_usage(p_id):
    """عدد مرات ظهور المنتج في أصناف الطلبات (قراءة فقط) — لتحذير الحذف."""
    conn = db.get_db_connection()
    try:
        n = conn.execute("SELECT COUNT(*) FROM order_items WHERE product_id = ?",
                         (p_id,)).fetchone()[0]
        return n
    finally:
        conn.close()


def _add_product_impl(name: str, cat: str = "", price_r: float = 0.0, price_w: float = 0.0,
                      mode: str = "preview", op_id: str = "", confirm: str = ""):
    """إضافة منتج عبر الدالة الرسمية add_quick_product (المخزون يبدأ 0 مثل البرنامج تمامًا)."""
    tool = "posw_add_product"
    name = (name or "").strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    dups = _find_duplicate_products(name)
    summary = {
        "operation": "إضافة منتج (الدالة الرسمية add_quick_product)",
        "new_values": {"name": name, "category": (cat or "").strip() or "(تُستنتج تلقائيًا بواسطة infer_category)",
                       "price_retail": price_r, "price_wholesale": price_w, "stock_start": 0},
        "warnings": ["منتج بنفس الاسم موجود: id=%s %r (سعر قطاعي %s)" % (d["id"], d["name"], d["price_retail"])
                     for d in dups],
        "products_count_now": _product_count(),
        "note": "المخزون يبدأ 0 (مثل سلوك البرنامج) — تسوية المخزون اليدوية مؤجلة (4.5)",
    }
    if mode == "preview":
        op_id = _new_op(tool, {"name": name, "cat": (cat or "").strip(),
                               "price_r": float(price_r), "price_w": float(price_w)}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        new_id = db.add_quick_product(p["name"], p["cat"], p["price_r"], p["price_w"])
        return _exec_result(tool, op_id, {"new_product": _product_row(new_id),
                                          "products_count_after": _product_count()})
    raise ValueError("mode لازم يكون preview أو execute")


def _update_product_impl(p_id: int, name: str, cat: str, price_r: float, price_w: float,
                         sort_order: int = 0, mode: str = "preview", op_id: str = "",
                         confirm: str = ""):
    """تعديل منتج عبر الدالة الرسمية update_product_details. تغيير الأسعار = مستوى 2 (تحذير صريح)."""
    tool = "posw_update_product"
    name = (name or "").strip()
    if not name:
        raise ValueError("الاسم مطلوب")
    before = _product_row(p_id)
    if before is None:
        raise ValueError("لا يوجد منتج برقم %s" % p_id)
    planned = {"id": p_id, "name": name, "category": (cat or "").strip(),
               "price_retail": float(price_r), "price_wholesale": float(price_w),
               "sort_order": int(sort_order)}
    warnings = []
    if planned["price_retail"] != before["price_retail"] or planned["price_wholesale"] != before["price_wholesale"]:
        warnings.append("تغيير سعر في الكتالوج = مستوى 2 في الميثاق (تأكيد مضاعف) — قديم: قطاعي %s / جملة %s → جديد: قطاعي %s / جملة %s"
                        % (before["price_retail"], before["price_wholesale"], planned["price_retail"], planned["price_wholesale"]))
    summary = {
        "operation": "تعديل منتج (الدالة الرسمية update_product_details)",
        "before": before,
        "planned_after": planned,
        "warnings": warnings,
        "note": "المخزون لا يتغير من هذه الأداة — تسوية المخزون مؤجلة (4.5) ولا تُلمس last_cost_price",
    }
    if mode == "preview":
        op_id = _new_op(tool, planned, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        db.update_product_details(p["id"], p["name"], p["category"], p["price_wholesale"],
                                  p["price_retail"], p["sort_order"])
        return _exec_result(tool, op_id, {"before": before, "after": _product_row(p_id)})
    raise ValueError("mode لازم يكون preview أو execute")


def _delete_product_impl(p_id: int, mode: str = "preview", op_id: str = "",
                         confirm: str = ""):
    """حذف منتج عبر الدالة الرسمية delete_product — preview يعرض الاستخدام في الطلبات أولًا."""
    tool = "posw_delete_product"
    before = _product_row(p_id)
    if before is None:
        raise ValueError("لا يوجد منتج برقم %s" % p_id)
    usage = _product_usage(p_id)
    summary = {
        "operation": "حذف منتج (الدالة الرسمية delete_product)",
        "product": before,
        "will_delete": {"order_items_references": usage},
        "warnings": (["المنتج مستخدم في %s صنف طلبات — سجلات الأصناف القديمة تبقى بلا منتج مرتبط" % usage]
                     if usage else []),
        "irreversible": True,
    }
    if mode == "preview":
        op_id = _new_op(tool, {"p_id": p_id}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        db.delete_product(op["payload"]["p_id"])
        return _exec_result(tool, op_id, {"deleted_product": before,
                                          "products_count_after": _product_count()})
    raise ValueError("mode لازم يكون preview أو execute")


# ---------- أدوات الطلبات (الدوال الرسمية فقط) ----------

def _order_row(order_id):
    conn = db.get_db_connection()
    try:
        r = conn.execute("SELECT id, client_id, total_amount, status, date, delivery_date, notes "
                         "FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _order_items(order_id):
    conn = db.get_db_connection()
    try:
        rows = conn.execute("SELECT product_id, product_name, qty, price, total "
                            "FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _duplicate_orders_check(client_id, items):
    """منع تكرار الطلب (عميل + أصناف + نفس اليوم) — تحذير فقط، القرار للمالك."""
    hits = []
    conn = db.get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, total_amount, date FROM orders "
            "WHERE client_id = ? AND date >= date('now', 'localtime')",
            (client_id,)).fetchall()
        new_ids = {i["product_id"] for i in items if i.get("product_id") is not None}
        for o in rows:
            its = conn.execute("SELECT product_id, qty FROM order_items WHERE order_id = ?",
                               (o["id"],)).fetchall()
            if new_ids & {r["product_id"] for r in its}:
                hits.append({"order_id": o["id"], "total": o["total_amount"],
                             "today_items": [{"product_id": r["product_id"], "qty": r["qty"]} for r in its]})
        return hits
    finally:
        conn.close()


def _add_order_impl(client_id: int, items: list, payment_method: str = "Cash",
                    payment_amount: float = None, notes: str = "",
                    delivery_date=None, mode: str = "preview", op_id: str = "",
                    confirm: str = ""):
    """إنشاء طلب عبر الدالة الرسمية save_order_transaction.
    العناصر [{product_id, qty, price?}] — السعر الفاضي من الكتالوج حسب نوع العميل (مثل البرنامج)."""
    tool = "posw_add_order"
    if not items or not isinstance(items, list):
        raise ValueError("العناصر مطلوبة: [{product_id, qty, price?}]")
    before = _client_row(client_id)
    if before is None:
        raise ValueError("لا يوجد عميل برقم %s" % client_id)
    prepared = []
    warnings = []
    for it in items:
        pid = int(it.get("product_id") or 0)
        prod = _product_row(pid)
        if prod is None:
            raise ValueError("لا يوجد منتج برقم %s" % it.get("product_id"))
        qty = float(it.get("qty") or 0)
        if qty <= 0:
            raise ValueError("كمية غير صالحة للمنتج: %s" % prod["name"])
        price = it.get("price")
        if price in (None, "", 0):
            price = prod["price_wholesale"] if before["type"] == "Wholesale" else prod["price_retail"]
        price = float(price)
        cat_price = prod["price_wholesale"] if before["type"] == "Wholesale" else prod["price_retail"]
        if price != cat_price:
            warnings.append("سعر مختلف عن الكتالوج: %s (قطاعي %s / جملة %s) — طلبك %s"
                            % (prod["name"], prod["price_retail"], prod["price_wholesale"], price))
        prepared.append({"id": pid, "name": prod["name"], "qty": qty,
                         "price": price, "total": round(qty * price, 2)})
    net_total = round(sum(x["total"] for x in prepared), 2)
    paid = round(float(payment_amount or 0.0), 2)
    remaining = round(net_total - paid, 2)
    if remaining < 0:
        raise ValueError("الدفعة (%s) أكبر من الإجمالي (%s) — راجع الحالة" % (paid, net_total))
    for d in _duplicate_orders_check(client_id, [{"product_id": x["id"]} for x in prepared]):
        warnings.append("احتمال تكرار: طلب اليوم #%s بنفس الأصناف (إجمالي %s) — منع التكرار (4.3)"
                        % (d["order_id"], d["total"]))
    if remaining > 0:
        warnings.append("متبقي %s → رصيد العميل من %s إلى %s وينشأ قيد دين 'Order #? - Remaining'"
                        % (remaining, before["balance"], round(before["balance"] + remaining, 2)))
    for x in prepared:
        prod = _product_row(x["id"])
        if prod["stock_qty"] < x["qty"]:
            warnings.append("مخزون %s = %s أقل من الكمية %s — المخزون هيصبح سالبًا مثل البرنامج"
                            % (prod["name"], prod["stock_qty"], x["qty"]))
    summary = {
        "operation": "إنشاء طلب (الدالة الرسمية save_order_transaction — الحالة تبدأ 'Under Preparation')",
        "client": {"id": client_id, "name": before["name"], "type": before["type"],
                   "balance_now": before["balance"],
                   "balance_after": round(before["balance"] + remaining, 2)},
        "items": prepared,
        "net_total": net_total,
        "payment_method": payment_method,
        "paid_amount": paid,
        "remaining": remaining,
        "stock_impact": [{"product_id": x["id"], "name": x["name"], "qty": x["qty"],
                          "stock_now": _product_row(x["id"])["stock_qty"]} for x in prepared],
        "warnings": warnings,
        "images_note": "الطلب الجديد بلا صور — الصور تُنقل عند تغيير الحالة (أداة الحالة لاحقًا)",
    }
    if mode == "preview":
        payload = {"client_id": client_id, "items": prepared, "payment_method": payment_method,
                   "paid": paid, "remaining": remaining, "notes": notes,
                   "delivery_date": delivery_date, "net_total": net_total}
        op_id = _new_op(tool, payload, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.save_order_transaction(client_id, p["net_total"], 0.0, p["net_total"],
                                        p["paid"], p["remaining"], p["items"],
                                        p["payment_method"], p["notes"], p.get("delivery_date"))
        if not res.get("success"):
            raise ValueError("الدالة الرسمية رفضت الطلب: %s" % res.get("error"))
        oid = res["order_id"]
        conn = db.get_db_connection()
        try:
            txns = conn.execute("SELECT type, amount, notes FROM transactions WHERE notes LIKE ?",
                                ("Order #%d%%" % oid,)).fetchall()
        finally:
            conn.close()
        return _exec_result(tool, op_id, {
            "order": _order_row(oid),
            "order_items": _order_items(oid),
            "client_after": _client_row(client_id),
            "txns_created": [dict(t) for t in txns],
            "stock_after": {x["name"]: _product_row(x["id"])["stock_qty"] for x in p["items"]},
        })
    raise ValueError("mode لازم يكون preview أو execute")

def _order_financial_effect(order_id):
    """قيود الدخل/الدين المرتبطة بالطلب (قراءة فقط) — للمعاينة قبل الحذف."""
    conn = db.get_db_connection()
    try:
        rows = conn.execute(
            "SELECT id, type, amount, notes, related_ref FROM transactions "
            "WHERE notes LIKE ? OR related_ref = ?",
            ("Order #%d%%" % order_id, "Order #%d" % order_id)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _delete_order_impl(order_id: int, mode: str = "preview", op_id: str = "",
                       confirm: str = ""):
    """حذف طلب عبر الدالة الرسمية delete_order (المُصلحة 2026-10-11): ترجع المخزون وتلغي القيود.
    تأكيد الحذف في المحادثة لازم يذكر اسم العميل والمبلغ وأن الصور ستُمسح (أمر المالك)."""
    tool = "posw_delete_order"
    order = _order_row(order_id)
    if order is None:
        raise ValueError("لا يوجد طلب برقم %s" % order_id)
    client = _client_row(order["client_id"])
    items = _order_items(order_id)
    txns = _order_financial_effect(order_id)
    total_from_items = round(sum(i["total"] for i in items), 2)
    summary = {
        "operation": "حذف طلب (الدالة الرسمية delete_order — ترجع المخزون وتُلغي قيود الدين/الدفعات)",
        "order": {"id": order_id, "status": order["status"], "date": order["date"],
                  "total_amount": order["total_amount"], "notes": order["notes"]},
        "client": {"id": client["id"], "name": client["name"], "balance_now": client["balance"]},
        "items": items,
        "transactions_to_cancel": txns,
        "warnings": [
            "الصور المرتبطة بالطلب (مجلد تصميم العميل) ستُمسح من القرص",
            "المخزون سيُرجع: %s" % ", ".join("%s +%s" % (i["product_name"], int(i["qty"])) for i in items),
            "رصيد العميل سينقص بقيمة الدين المعلق (%s) ثم تُحذف قيوده والدفعات المسجلة عليه"
            % round(sum(t["amount"] for t in txns if t["type"] == "debt"), 2),
            "إجمالي الأصناف %s" % total_from_items,
        ],
        "irreversible": True,
    }
    if mode == "preview":
        op_id = _new_op(tool, {"order_id": order_id}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        ok = db.delete_order(op["payload"]["order_id"])
        if not ok:
            raise ValueError("الدالة الرسمية رفضت الحذف (الطلب غير موجود أو خطأ)")
        return _exec_result(tool, op_id, {
            "deleted_order": {"id": order["id"], "total_amount": order["total_amount"],
                              "client_name": client["name"]},
            "client_after": _client_row(order["client_id"]),
            "order_after": _order_row(order_id),
        })
    raise ValueError("mode لازم يكون preview أو execute")


# ---------- أداة الحالة (تغيير حالة الطلب + نقل مجلد التصاميم) ----------

ALLOWED_ORDER_STATUSES = ("Under Preparation", "Ready", "Delivered")


def _update_status_impl(order_id: int, new_status: str, payment: float = 0.0,
                        method: str = "Cash", mode: str = "preview",
                        op_id: str = "", confirm: str = ""):
    """تغيير حالة طلب عبر الدالة الرسمية update_order_status:
    يسجل العملية + ينقل مجلد التصاميم (Forward: Ready/Delivered، Undo: Under Preparation)
    ولو التوصيل وفيه دفعة يسجل قيد 'Delivery Order #-' ويخفض الرصيد — مثل البرنامج تمامًا."""
    tool = "posw_update_status"
    if new_status not in ALLOWED_ORDER_STATUSES:
        raise ValueError("الحالة لازم تكون من: %s (وصلت: %s)" % (" / ".join(ALLOWED_ORDER_STATUSES), new_status))
    order = _order_row(order_id)
    if order is None:
        raise ValueError("لا يوجد طلب برقم %s" % order_id)
    client = _client_row(order["client_id"])
    items = _order_items(order_id)
    conn = db.get_db_connection()
    try:
        cur_path = conn.execute("SELECT local_image_path FROM orders WHERE id = ?",
                                (order_id,)).fetchone()
        cur_path = cur_path["local_image_path"] if cur_path else None
    finally:
        conn.close()
    warnings = []
    direction = "forward" if new_status in ("Ready", "Delivered") else ("backward" if new_status == "Under Preparation" else None)
    if direction == "forward":
        warnings.append("مجلد التصاميم الحالي سينتقل إلى مرحلة '%s' (FileOpsEngine move_to_stage)" % new_status)
    elif direction == "backward":
        warnings.append("تراجع إلى Under Preparation: إرجاع المجلد من السجل (restore_to_previous_path)")
    if new_status == "Delivered" and payment > 0:
        warnings.append("قيد 'Delivery Order #%s - %s' (دخل) سيُضاف ورصيد العميل ينقص %s بموجب شحنة التوصيل"
                        % (order_id, method, payment))
    if not cur_path:
        warnings.append("الطلب بلا مجلد صور معرّف (local_image_path فارغ) — النقل سيعالج المسار تلقائيًا")
    summary = {
        "operation": "تغيير حالة طلب (الدالة الرسمية update_order_status + manage_file_system)",
        "order": {"id": order_id, "status_now": order["status"], "status_next": new_status,
                  "date": order["date"], "total_amount": order["total_amount"]},
        "client": {"id": client["id"], "name": client["name"], "balance_now": client["balance"]},
        "items": [{"product_id": i["product_id"], "name": i["product_name"],
                   "qty": i["qty"], "total": i["total"]} for i in items],
        "images_folder": cur_path,
        "balance_effect": None if not (new_status == "Delivered" and payment > 0)
                          else {"old": client["balance"], "new": round(client["balance"] - payment, 2)},
        "warnings": warnings,
        "operation_log_note": "تُسجَّل عملية في operation_logs بالنظام 'System'",
    }
    if mode == "preview":
        payload = {"order_id": order_id, "new_status": new_status,
                   "payment": float(payment or 0.0), "method": method}
        op_id = _new_op(tool, payload, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.update_order_status(p["order_id"], p["new_status"], p["payment"], p["method"])
        if res is not True:
            raise ValueError("الدالة الرسمية رفضت تغيير الحالة: %s" % res)
        conn = db.get_db_connection()
        try:
            row = conn.execute("SELECT local_image_path FROM orders WHERE id = ?",
                              (p["order_id"],)).fetchone()
            new_path = row["local_image_path"] if row else None
        finally:
            conn.close()
        return _exec_result(tool, op_id, {
            "order_after": _order_row(p["order_id"]),
            "client_after": _client_row(client["id"]),
            "images_folder_before": cur_path,
            "images_folder_after": new_path,
        })
    raise ValueError("mode لازم يكون preview أو execute")


# ---------- أداة الدفعة (تسجيل سداد من عميل) ----------

def _payment_preview_effect(client_id, amount, notes):
    client = _client_row(client_id)
    if client is None:
        raise ValueError("لا يوجد عميل برقم %s" % client_id)
    warnings = []
    if amount > client["balance"]:
        warnings.append("السداد (%s) أكبر من الرصيد (%s) — الرصيد هيصبح سالبًا (%s) (البرنامج يسمح به)"
                        % (amount, client["balance"], round(client["balance"] - amount, 2)))
    conn = db.get_db_connection()
    try:
        last = conn.execute(
            "SELECT id, amount, date FROM transactions WHERE client_id = ? "
            "ORDER BY id DESC LIMIT 1", (client_id,)).fetchone()
    finally:
        conn.close()
    return {
        "operation": "تسجيل دفعة/سداد من عميل (الدالة الرسمية update_client_transaction — t_type='payment')",
        "client": {"id": client["id"], "name": client["name"], "type": client["type"],
                   "balance_now": client["balance"],
                   "balance_after": round(client["balance"] - amount, 2)},
        "amount": round(amount, 2),
        "notes": notes,
        "txn_created": {"type": "Income", "category": "Debt Collection",
                        "amount": round(amount, 2), "notes": notes,
                        "user": "System", "related_ref": "Client Balance"},
        "warnings": warnings,
        "no_stock_no_orders": "الدفعة لا تلمس المخزون ولا شأنها بالطلبات (قيد مستقل عن الطلبات)",
    }


def _add_payment_impl(client_id: int, amount: float, notes: str = "دفع نقدي",
                      mode: str = "preview", op_id: str = "", confirm: str = ""):
    """تسجيل دفعة/سداد من عميل عبر الدالة الرسمية update_client_transaction.
    تُنقص رصيد العميل وتُدرج قيد دخل (تحصيل دين) — نفس سلوك برنامج الحي."""
    tool = "posw_add_payment"
    if amount <= 0:
        raise ValueError("المبلغ لازم أكبر من 0 (اتلفت: %s)" % amount)
    eff = _payment_preview_effect(client_id, amount, notes)
    summary = {
        "operation": eff["operation"],
        "client": eff["client"],
        "amount": eff["amount"],
        "notes": eff["notes"],
        "txn_created": eff["txn_created"],
        "warnings": eff["warnings"],
        "no_stock_no_orders": eff["no_stock_no_orders"],
    }
    if mode == "preview":
        payload = {"client_id": client_id, "amount": round(amount, 2), "notes": notes}
        op_id = _new_op(tool, payload, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        db.update_client_transaction(p["client_id"], p["amount"], "payment",
                                     p["notes"], 0.0, p["amount"])
        conn = db.get_db_connection()
        try:
            rows = conn.execute(
                "SELECT id, type, category, amount, notes, user, related_ref, date "
                "FROM transactions WHERE client_id = ? ORDER BY id DESC LIMIT 3",
                (p["client_id"],)).fetchall()
        finally:
            conn.close()
        return _exec_result(tool, op_id, {
            "client_after": _client_row(p["client_id"]),
            "txn_created": [dict(t) for t in rows],
            "stock": "بدون تغيير",
        })
    raise ValueError("mode لازم يكون preview أو execute")


# ---------- أدوات فاتورة المشتريات (دوال رسمية فقط) ----------

def _invoice_row(invoice_id):
    conn = db.get_db_connection()
    try:
        r = conn.execute("SELECT id, supplier_id, supplier_name, total_cost, status, date, notes "
                         "FROM purchase_invoices WHERE id = ?", (invoice_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _invoice_items(invoice_id):
    conn = db.get_db_connection()
    try:
        rows = conn.execute("SELECT product_id, product_name, qty, cost_price, total "
                            "FROM purchase_items WHERE invoice_id = ?", (invoice_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _add_purchase_invoice_impl(supplier_name: str, items: list,
                               supplier_id: int = None, notes: str = "",
                               mode: str = "preview", op_id: str = "", confirm: str = ""):
    """فاتورة مشتريات جديدة عبر save_purchase_invoice (الحالة 'Pending' — لا تغيير مخزون حتى الاستلام).
    العناصر [{product_id, qty, cost}]."""
    tool = "posw_add_purchase_invoice"
    if not items or not isinstance(items, list):
        raise ValueError("العناصر مطلوبة: [{product_id, qty, cost}]")
    if not supplier_name:
        raise ValueError("اسم المورد مطلوب")
    prepared = []
    warnings = []
    for it in items:
        pid = int(it.get("product_id") or 0)
        prod = _product_row(pid)
        if prod is None:
            raise ValueError("لا يوجد منتج برقم %s" % it.get("product_id"))
        qty = float(it.get("qty") or 0)
        if qty <= 0:
            raise ValueError("كمية غير صالحة للمنتج: %s" % prod["name"])
        cost = float(it.get("cost") or 0)
        if cost < 0:
            raise ValueError("تكلفة سالبة مرفوضة للمنتج: %s" % prod["name"])
        prepared.append({"product_id": pid, "product_name": prod["name"],
                         "qty": qty, "cost": cost, "total": round(qty * cost, 2)})
        if cost == 0:
            warnings.append("تكلفة صفر للمنتج %s — تأكيدك مطلوب (سعر غير واقعي)" % prod["name"])
    total_cost = round(sum(i["total"] for i in prepared), 2)
    if total_cost == 0:
        warnings.append("الإجمالي 0 — لا مصروف سيتسجل عند الاستلام")
    summary = {
        "operation": "فاتورة مشتريات جديدة (save_purchase_invoice — الحالة 'Pending': لا مخزون ولا مصروف حتى الاستلام)",
        "supplier": {"id": supplier_id, "name": supplier_name},
        "items": prepared,
        "total_cost": total_cost,
        "notes": notes,
        "warnings": warnings,
        "next_step_note": "خطوة الاستلام (بعدها) بتزيد المخزون وتكتب مصروف — الاختبار على النسخة (قرار المالك للمخزون)",
    }
    if mode == "preview":
        payload = {"supplier_name": supplier_name, "supplier_id": supplier_id,
                   "items": [{"product_id": i["product_id"], "product_name": i["product_name"],
                              "qty": i["qty"], "cost": i["cost"]} for i in prepared],
                   "notes": notes, "total_cost": total_cost,
                   # 2026-10-12 fix: بدون تاريخ تُخزَّن الفاتورة date=NULL فتظهر آخر القائمة
                   "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        op_id = _new_op(tool, payload, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.save_purchase_invoice(p)
        if not res.get("success"):
            raise ValueError("الدالة الرسمية رفضت الفاتورة: %s" % res.get("error"))
        inv_id = res["invoice_id"]
        return _exec_result(tool, op_id, {
            "invoice": _invoice_row(inv_id),
            "items": _invoice_items(inv_id),
            "stock_note": "لا تغيير مخزون (الحالة Pending)",
        })
    raise ValueError("mode لازم يكون preview أو execute")


def _receive_purchase_impl(invoice_id: int, mode: str = "preview", op_id: str = "",
                           confirm: str = ""):
    """استلام فاتورة مشتريات عبر toggle_purchase_status('Received'):
    إضافة قيد مصروف + زيادة المخزون وlast_cost_price — أثر على المخزون → تُختبر على النسخة."""
    tool = "posw_receive_purchase"
    inv = _invoice_row(invoice_id)
    if inv is None:
        raise ValueError("لا توجد فاتورة برقم %s" % invoice_id)
    if inv["status"] == "Received":
        raise ValueError("الفاتورة #%s مستلمة أصلًا (لا تغيير)" % invoice_id)
    items = _invoice_items(invoice_id)
    conn = db.get_db_connection()
    try:
        exp = conn.execute("SELECT count(*) AS n FROM transactions WHERE related_ref = ? AND type='Expense'",
                           ("Supplier #%s" % inv["supplier_id"],)).fetchone()
        duplicate_supplier_expense = (exp["n"] if exp else 0) > 0
    finally:
        conn.close()
    warnings = ["زيادة المخزون لكل صنف: +كمية",
                "قيد مصروف (Raw Materials) بمبلغ الإجمالي %s" % inv["total_cost"]]
    if duplicate_supplier_expense:
        warnings.append("تحذير: فواتير أخرى لنفس المورد لها قيود Expense — التراجع لاحقًا ('Pending') يحذف كل قيود المصروف لهذا المورد (سلوك الدالة)")
    summary = {
        "operation": "استلام فاتورة مشتريات (toggle_purchase_status → Received): +مخزون + مصروف",
        "invoice": inv,
        "items": items,
        "stock_impact": [{"product_id": i["product_id"], "name": i["product_name"],
                          "qty": i["qty"], "stock_now": (_product_row(i["product_id"]) or {}).get("stock_qty")}
                         for i in items],
        "expense_txn": {"type": "Expense", "category": "Raw Materials",
                        "amount": inv["total_cost"],
                        "notes": "Purchase Invoice #%s" % invoice_id,
                        "related_ref": "Supplier #%s" % inv["supplier_id"]},
        "warnings": warnings,
        "sandbox_only": "أثر على المخزون → الاختبار على النسخة (قرار المالك: المخزون على النسخة)",
    }
    if mode == "preview":
        payload = {"invoice_id": invoice_id}
        op_id = _new_op(tool, payload, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.toggle_purchase_status(p["invoice_id"], "Received")
        if not res.get("success"):
            raise ValueError("الدالة الرسمية رفضت الاستلام: %s" % res.get("error"))
        return _exec_result(tool, op_id, {
            "invoice_after": _invoice_row(p["invoice_id"]),
            "items": _invoice_items(p["invoice_id"]),
            "stock_after": {i["product_name"]: (_product_row(i["product_id"]) or {}).get("stock_qty")
                            for i in _invoice_items(p["invoice_id"])},
            "expense_row_added": inv["total_cost"],
        })
    raise ValueError("mode لازم يكون preview أو execute")


def _delete_purchase_impl(invoice_id: int, mode: str = "preview", op_id: str = "",
                          confirm: str = ""):
    """حذف فاتورة مشتريات عبر delete_purchase. تحذير سطحي: لو Received، يُرجع المخزون لكن
    قيد المصروف يبقى في السجل (سلوك البرنامج — سأستخدمه وض Proof)."""
    tool = "posw_delete_purchase"
    inv = _invoice_row(invoice_id)
    if inv is None:
        raise ValueError("لا توجد فاتورة برقم %s" % invoice_id)
    items = _invoice_items(invoice_id)
    warnings = []
    if inv["status"] == "Received":
        warnings.append("المخزون سيُرجع (−كمية كل صنف)")
        warnings.append("قيد المصروف (Expense Raw Materials) سيبقى في السجل — الدالة لا تحذف قيود المصروف عند الحذف")
    warnings.append("حذف نهائي للفاتورة وأصنافها")
    summary = {
        "operation": "حذف فاتورة مشتريات (delete_purchase)",
        "invoice": inv,
        "items": items,
        "warnings": warnings,
        "images_matrix": "المشتريات بلا صور",
    }
    if mode == "preview":
        op_id = _new_op(tool, {"invoice_id": invoice_id}, summary)
        return {"step": "preview", "op_id": op_id, "ttl_seconds": PENDING_TTL,
                "execute_with": {"op_id": op_id, "confirm": "نعم"}, **summary}
    if mode == "execute":
        op = _take_op(tool, op_id, confirm)
        p = op["payload"]
        res = db.delete_purchase(p["invoice_id"])
        if not res.get("success"):
            raise ValueError("الدالة الرسمية رفضت الحذف: %s" % res.get("error"))
        return _exec_result(tool, op_id, {
            "deleted_invoice": inv,
            "invoice_after": _invoice_row(p["invoice_id"]),
            "stock_after": {i["product_name"]: (_product_row(i["product_id"]) or {}).get("stock_qty")
                            for i in items},
        })
    raise ValueError("mode لازم يكون preview أو execute")


mcp.tool(name="posw_add_purchase_invoice")(_add_purchase_invoice_impl)
mcp.tool(name="posw_receive_purchase")(_receive_purchase_impl)
mcp.tool(name="posw_delete_purchase")(_delete_purchase_impl)
mcp.tool(name="posw_add_client")(_add_client_impl)
mcp.tool(name="posw_update_client")(_update_client_impl)
mcp.tool(name="posw_delete_client")(_delete_client_impl)
mcp.tool(name="posw_add_product")(_add_product_impl)
mcp.tool(name="posw_update_product")(_update_product_impl)
mcp.tool(name="posw_delete_product")(_delete_product_impl)
mcp.tool(name="posw_add_order")(_add_order_impl)
mcp.tool(name="posw_delete_order")(_delete_order_impl)
mcp.tool(name="posw_update_status")(_update_status_impl)
mcp.tool(name="posw_add_payment")(_add_payment_impl)


if __name__ == "__main__":
    _audit("server_start", "pos-writer", {"target": TARGET, "db_dir": DB_DIR})
    print("[pos-writer] target=%s db=%s" % (TARGET, os.path.abspath(db.DB_NAME)), file=sys.stderr)
    mcp.run()
