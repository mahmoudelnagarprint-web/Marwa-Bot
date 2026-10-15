import os
import shutil
import base64
import time
import socket
import threading
import json
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Header, Request, Form, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import uvicorn

import database
from openai import OpenAI

app = FastAPI(title="Elnagar POS Local Mobile API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("LOCAL_MOBILE_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    "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",
)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

AI_ORDER_MODEL = "openai/gpt-4o-mini"

def verify_api_key(x_elnagar_api_key: Optional[str] = Header(None)):
    if API_KEY and x_elnagar_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return True

def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Empty model response")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise

def _normalize_client_type(client_name: str) -> str:
    raw = (client_name or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits and len(digits) >= 8:
        return "retail"
    return "wholesale"

def show_windows_toast(title, message):
    import subprocess
    import os
    powershell_code = f"""
    [void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');
    $notification = New-Object System.Windows.Forms.NotifyIcon;
    $notification.Icon = [System.Drawing.SystemIcons]::Information;
    $notification.BalloonTipIcon = 'Info';
    $notification.BalloonTipText = '{message}';
    $notification.BalloonTipTitle = '{title}';
    $notification.Visible = $True;
    $notification.ShowBalloonTip(5000);
    """
    try:
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(["powershell", "-Command", powershell_code], startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(["powershell", "-Command", powershell_code])
    except Exception as e:
        print(f"Failed to show toast: {e}")

def udp_broadcast_daemon():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", 7789))
    udp_socket.settimeout(1.0)

    def current_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "192.168.1.50"

    last_broadcast = 0.0
    while True:
        try:
            now = time.time()
            if now - last_broadcast >= 5:
                payload = json.dumps({
                    "type": "heartbeat",
                    "ip": current_local_ip(),
                    "port": 7788
                }).encode('utf-8')
                udp_socket.sendto(payload, ('255.255.255.255', 7789))
                last_broadcast = now

            try:
                data, addr = udp_socket.recvfrom(4096)
            except socket.timeout:
                continue

            try:
                message = json.loads(data.decode('utf-8', errors='ignore'))
            except Exception:
                message = {}

            if message.get("type") == "discover":
                response = json.dumps({
                    "type": "discovery_response",
                    "ip": current_local_ip(),
                    "port": 7788
                }).encode('utf-8')
                udp_socket.sendto(response, addr)
        except Exception as e:
            print(f"UDP Discovery Error: {e}")
            time.sleep(1)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=udp_broadcast_daemon, daemon=True)
    t.start()

@app.get("/health")
def health_check():
    db_ok = True
    try:
        conn = database.get_db_connection()
        conn.close()
    except Exception:
        db_ok = False
        
    return {
        "ok": True,
        "service": "elnagar-local-mobile-api",
        "version": "1.0",
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "db_ok": db_ok
    }

@app.get("/api/ai/connection-test", dependencies=[Depends(verify_api_key)])
def ai_connection_test():
    try:
        print(f"[AI] Testing connection with model {AI_ORDER_MODEL}")
        response = client.chat.completions.create(
            model=AI_ORDER_MODEL,
            messages=[
                {"role": "system", "content": "Reply with a single word: ok"},
                {"role": "user", "content": "ping"},
            ],
            temperature=0,
            max_tokens=4,
        )
        content = response.choices[0].message.content or ""
        print(f"[AI] Connection test response: {content}")
        return {"success": True, "message": content.strip() or "ok"}
    except Exception as e:
        print(f"[AI] Connection test failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/bootstrap", dependencies=[Depends(verify_api_key)])
def get_bootstrap_data():
    try:
        conn = database.get_db_connection()
        
        clients = [dict(row) for row in conn.execute("SELECT * FROM clients").fetchall()]
        products = [dict(row) for row in conn.execute("SELECT * FROM products").fetchall()]
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        
        query = """
        SELECT
            (SELECT COUNT(*) FROM orders) as orders_total,
            (SELECT COUNT(*) FROM orders WHERE date(date, 'localtime') = date('now', 'localtime')) as orders_today,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing')) as under_preparation_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing')) as under_preparation_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Ready', 'ready')) as ready_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Ready', 'ready')) as ready_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Delivered', 'delivered')) as delivered_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Delivered', 'delivered')) as delivered_value,
            (SELECT COUNT(*) FROM clients) as clients_count,
            (SELECT COUNT(*) FROM clients WHERE balance < 0) as debt_clients_count,
            (SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance < 0) as total_receivables,
            (SELECT COUNT(*) FROM products) as products_count,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date(date, 'localtime') >= date('now', 'localtime', '-7 days')) as weekly_revenue_raw,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date(date, 'localtime') = date('now', 'localtime')) as daily_revenue_raw,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date(date, 'localtime') >= date('now', 'localtime', '-7 days')) as weekly_expenses,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date(date, 'localtime') = date('now', 'localtime')) as daily_expenses
        """
        raw_summary = dict(conn.execute(query).fetchone())
        conn.close()

        # Integrate evolved ERP statistics
        import financial_engine
        weekly_stats = financial_engine.get_weekly_financial_stats()
        raw_summary.update(weekly_stats)
        
        raw_summary['daily_revenue'] = max(0, raw_summary['daily_revenue_raw'] - raw_summary['daily_expenses'])
        raw_summary['daily_expense_target'] = 500.0
        dashboard_summary = raw_summary

        orders = database.get_kanban_orders()

        conn = database.get_db_connection()
        recent_purchases_rows = conn.execute("SELECT * FROM purchase_invoices ORDER BY date DESC LIMIT 50").fetchall()
        purchases = []
        for row in recent_purchases_rows:
            p = dict(row)
            items_rows = conn.execute("SELECT * FROM purchase_items WHERE invoice_id=?", (p['id'],)).fetchall()
            p['items'] = [dict(i) for i in items_rows]
            purchases.append(p)
        conn.close()

        return {
            "success": True,
            "clients": clients,
            "products": products,
            "categories": categories,
            "orders": orders,
            "purchases": purchases,
            "dashboard_summary": dashboard_summary
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/clients", dependencies=[Depends(verify_api_key)])
def get_clients():
    return {"success": True, "clients": database.get_all_clients()}

@app.get("/api/products", dependencies=[Depends(verify_api_key)])
def get_products():
    return {"success": True, "products": database.get_all_products()}

@app.get("/api/categories", dependencies=[Depends(verify_api_key)])
def get_categories():
    try:
        conn = database.get_db_connection()
        cats = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        conn.close()
        return {"success": True, "categories": cats}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/orders", dependencies=[Depends(verify_api_key)])
def get_orders():
    return {"success": True, "orders": database.get_kanban_orders()}

@app.post("/api/ai/parse-order", dependencies=[Depends(verify_api_key)])
async def ai_parse_order(image: UploadFile = File(...)):
    try:
        print(f"[AI] Received order image: filename={image.filename}, content_type={image.content_type}")
        raw_bytes = await image.read()
        if not raw_bytes:
            return JSONResponse(status_code=400, content={"success": False, "error": "Empty image upload"})

        mime_type = image.content_type or "image/jpeg"
        b64_image = base64.b64encode(raw_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_image}"

        system_prompt = (
            "You are an Egyptian POS assistant. Analyze this WhatsApp screenshot. "
            "Extract: client_name, products (names, quantity, specs), total_price (if mentioned), "
            "and delivery_date. Return STRICTLY as valid JSON. If the client name is a phone number, "
            "set client_type to 'retail', otherwise 'wholesale'."
        )

        print("[AI] Sending vision request to OpenRouter...")
        response = client.chat.completions.create(
            model=AI_ORDER_MODEL,
            temperature=0,
            max_tokens=700,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the structured order details from this screenshot."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
        )

        raw_content = response.choices[0].message.content or ""
        print(f"[AI] Raw model response: {raw_content}")
        parsed = _extract_json_object(raw_content)

        client_name = str(parsed.get("client_name", "")).strip()
        parsed["client_type"] = _normalize_client_type(client_name if client_name else str(parsed.get("client_type", "")))
        parsed["products"] = parsed.get("products", []) or []
        parsed["notes"] = parsed.get("notes", "") or ""

        return {
            "success": True,
            "data": parsed,
        }
    except Exception as e:
        print(f"[AI] parse-order failed: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/dashboard-summary", dependencies=[Depends(verify_api_key)])
def get_dashboard_summary():
    try:
        conn = database.get_db_connection()
        query = """
        SELECT
            (SELECT COUNT(*) FROM orders) as orders_total,
            (SELECT COUNT(*) FROM orders WHERE date(date) = date('now')) as orders_today,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing')) as under_preparation_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing')) as under_preparation_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Ready', 'ready')) as ready_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Ready', 'ready')) as ready_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Delivered', 'delivered')) as delivered_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Delivered', 'delivered')) as delivered_value,
            (SELECT COUNT(*) FROM clients) as clients_count,
            (SELECT COUNT(*) FROM clients WHERE balance < 0) as debt_clients_count,
            (SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance < 0) as total_receivables,
            (SELECT COUNT(*) FROM products) as products_count
        """
        dashboard_summary = dict(conn.execute(query).fetchone())
        conn.close()

        import financial_engine
        weekly_stats = financial_engine.get_weekly_financial_stats()
        dashboard_summary.update(weekly_stats)

        return {"success": True, "dashboard_summary": dashboard_summary}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/orders", dependencies=[Depends(verify_api_key)])
async def create_order(request: Request):
    data = await request.json()
    
    client_id = data.get('client_id')
    client_name = data.get('client_name', 'Unknown')
    total_amount = data.get('total_amount', data.get('total', 0))
    discount = data.get('discount', 0)
    net_total = total_amount - discount
    paid_amount = data.get('paid_amount', data.get('paid', 0))
    remaining = data.get('remaining', data.get('remaining_amount', net_total - paid_amount))
    payment_method = data.get('payment_method', 'Cash')
    notes = data.get('notes', '')
    delivery_date = data.get('delivery_date') or data.get('deadline') or data.get('due_date')
    items = data.get('items', [])
    external_order_id = data.get('external_order_id', str(uuid4()))

    if not notes:
        notes = f"Source: LocalApp, ExtID: {external_order_id}"
    else:
        notes += f" | ExtID: {external_order_id}"

    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM orders WHERE notes LIKE ?", (f"%{external_order_id}%",))
    existing = c.fetchone()
    conn.close()
    
    if existing:
        return {"success": True, "order_id": existing['id'], "message": "Order already exists"}

    mapped_items = []
    for item in items:
        p_id = item.get('product_id')
        p_name = item.get('product_name', 'Unknown')
        qty = item.get('qty', item.get('quantity', 1))
        price = item.get('price', 0)
        total = item.get('total', qty * price)
        
        if item.get('needs_product_creation') or not p_id:
            resolved = database.resolve_or_create_product_for_external_order(
                product_id=p_id,
                product_name=p_name,
                client_type=data.get('client_type', 'Retail'),
                external_price=price
            )
            if resolved and resolved.get('success') and resolved.get('product'):
                p_id = resolved['product']['id']
                p_name = resolved['product']['name']
        
        mapped_items.append({
            'id': p_id or 0,
            'name': p_name,
            'qty': qty,
            'price': price,
            'total': total
        })

    res = database.save_order_transaction(
        client_id, total_amount, discount, net_total, 
        paid_amount, remaining, mapped_items, payment_method, notes, delivery_date
    )
    
    if res.get('success'):
        show_windows_toast("Elnagar POS", f"📦 طلب جديد من الجوال: {client_name} بقيمة {net_total} ج.م")
        return {"success": True, "order_id": res.get("order_id")}
    else:
        return JSONResponse(status_code=500, content={"success": False, "error": res.get("error", "Unknown DB error")})

@app.post("/api/products", dependencies=[Depends(verify_api_key)])
async def add_product(request: Request):
    data = await request.json()
    name = data.get('name')
    cat = data.get('category')
    price_r = data.get('price_retail', data.get('retail_price', 0))
    price_w = data.get('price_wholesale', data.get('wholesale_price', 0))
    
    if not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "Name is required"})
        
    new_id = database.add_quick_product(name, cat, price_r, price_w)
    return {"success": True, "product_id": new_id}

@app.post("/api/clients", dependencies=[Depends(verify_api_key)])
async def add_client(request: Request):
    data = await request.json()
    name = data.get('name')
    phone = data.get('phone', '')
    c_type = data.get('type', 'Retail')
    notes = data.get('notes', '')
    
    if not name:
        return JSONResponse(status_code=400, content={"success": False, "error": "Name is required"})
        
    new_id = database.add_new_client(name, phone, c_type, notes)
    return {"success": True, "client_id": new_id}

@app.post("/api/payments", dependencies=[Depends(verify_api_key)])
async def add_payment(request: Request):
    data = await request.json()
    client_id = data.get('client_id')
    order_id = data.get('order_id')
    client_name = data.get('client_name', 'Unknown')
    amount = float(data.get('amount', 0))
    notes = data.get('notes', 'Payment from Mobile App')
    material_cost_recovery = float(data.get('material_cost_recovery', 0.0))
    net_profit_portion = float(data.get('net_profit_portion', amount))
    
    if not client_id and order_id:
        conn = database.get_db_connection()
        row = conn.execute("SELECT client_id FROM orders WHERE id=?", (order_id,)).fetchone()
        conn.close()
        if row:
            client_id = row['client_id']

    if not client_id or amount <= 0:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid client_id or amount"})
        
    res = database.update_client_transaction(
        client_id, amount, 'payment', notes, material_cost_recovery, net_profit_portion
    )
    show_windows_toast("Elnagar POS", f"💰 دفعة من الجوال: {client_name} بقيمة {amount} ج.م")
    return {"success": True}

@app.post("/api/order-status", dependencies=[Depends(verify_api_key)])
async def update_order_status(request: Request):
    data = await request.json()
    order_id = data.get('order_id')
    status = data.get('status')
    payment = data.get('payment', 0)
    method = data.get('method', 'Cash')
    
    if not order_id or not status:
        return JSONResponse(status_code=400, content={"success": False, "error": "Missing order_id or status"})
        
    res = database.update_order_status(order_id, status, payment, method)
    if res is True:
        return {"success": True}
    else:
        return JSONResponse(status_code=500, content={"success": False, "error": str(res)})

@app.post("/api/orders/status", dependencies=[Depends(verify_api_key)])
async def update_order_status_compat(request: Request):
    return await update_order_status(request)

@app.post("/api/order-images")
async def upload_image(
    order_id: int = Form(...),
    file: UploadFile = File(...),
    x_elnagar_api_key: Optional[str] = Header(None)
):
    try:
        verify_api_key(x_elnagar_api_key)
        
        images_dir = os.path.join("runtime", "orders_images", str(order_id))
        os.makedirs(images_dir, exist_ok=True)
        
        filename = f"img_{int(time.time())}_{file.filename}"
        filepath = os.path.join(images_dir, filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        database.update_order_image_path(order_id, images_dir)
        
        show_windows_toast("Elnagar POS", f"📸 تم استقبال صورة للطلب #{order_id} بنجاح")
        return {"success": True, "path": filepath}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/expenses", dependencies=[Depends(verify_api_key)])
async def add_expense(request: Request):
    try:
        data = await request.json()
        amount = float(data.get('amount', 0))
        category = data.get('category', 'نثريات')
        notes = data.get('notes', '')
        expense_type = data.get('expense_type', 'Business')
        
        if amount <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid amount"})
            
        conn = database.get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref, expense_type) 
            VALUES (NULL, 'Expense', ?, ?, ?, 'System', 'Expense', ?)
        """, (category, amount, notes, expense_type))
        conn.commit()
        conn.close()
        
        show_windows_toast("Elnagar POS", f"💸 مصروف من الجوال: بقيمة {amount} ج.م ({expense_type})")
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.post("/api/purchases", dependencies=[Depends(verify_api_key)])
async def add_purchase(request: Request):
    try:
        data = await request.json()
        supplier_name = data.get('supplier_name', 'Unknown Supplier')
        notes = data.get('notes', '')
        items = data.get('items', [])

        # 2026-10-12 fix (owner order): official database functions only.
        # The old body crashed in production: it referenced the missing
        # 'suppliers' table and the non-existent products.cost_price column,
        # and wrote a generic expense ref. Now: save_purchase_invoice ->
        # toggle 'Received' (stock + last_cost_price + per-invoice expense).
        # No invented prices: unknown products are recorded with product_id=NULL
        # (same as the old behavior) and never get invented prices.
        conn = database.get_db_connection()
        c = conn.cursor()
        prepared = []
        for item in items:
            product_id = item.get('product_id')
            product_name = item.get('product_name', 'Unknown')
            qty = float(item.get('quantity', 0))
            cost = float(item.get('cost_price', 0))
            if not product_id:
                p = c.execute("SELECT id FROM products WHERE name = ?", (product_name,)).fetchone()
                product_id = p['id'] if p else None
            prepared.append({"product_id": product_id, "product_name": product_name,
                             "qty": qty, "cost": cost})
        conn.close()

        res = database.save_purchase_invoice({
            "supplier_id": None, "supplier_name": supplier_name, "notes": notes,
            "date": time.strftime("%Y-%m-%d %H:%M:%S"), "items": prepared,
        })
        if not res.get('success'):
            return JSONResponse(status_code=400, content=res)
        purchase_id = res['invoice_id']

        rec = database.toggle_purchase_status(purchase_id, 'Received')
        if not rec.get('success'):
            database.delete_purchase(purchase_id)  # roll back: no orphan invoice/expense
            return JSONResponse(status_code=500, content=rec)

        total = round(sum(i['qty'] * i['cost'] for i in prepared), 2)
        show_windows_toast("Elnagar POS", f"📦 فاتورة مشتريات من الجوال: {supplier_name} بقيمة {total} ج.م")
        return {"success": True, "invoice_id": purchase_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.post("/api/purchases/edit", dependencies=[Depends(verify_api_key)])
async def edit_purchase(request: Request):
    try:
        data = await request.json()
        invoice_id = data.get('invoice_id')
        supplier_name = data.get('supplier_name', 'Unknown Supplier')
        notes = data.get('notes', '')
        items = data.get('items', [])

        if not invoice_id:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invoice ID required"})

        # 2026-10-12 fix (owner order): the edit goes through the official functions.
        # Received invoice -> Pending (official: removes old stock and this
        # invoice's own expense row), update via save_purchase_invoice, then back
        # to Received (adds new stock + a fresh per-invoice expense).
        conn = database.get_db_connection()
        inv = conn.execute("SELECT * FROM purchase_invoices WHERE id=?", (invoice_id,)).fetchone()
        conn.close()
        if not inv:
            return JSONResponse(status_code=404, content={"success": False, "error": "Invoice not found"})
        was_received = inv['status'] == 'Received'
        if was_received:
            database.toggle_purchase_status(invoice_id, 'Pending')

        conn = database.get_db_connection()
        c = conn.cursor()
        prepared = []
        for item in items:
            product_id = item.get('product_id')
            product_name = item.get('product_name', 'Unknown')
            qty = float(item.get('quantity', 0))
            cost = float(item.get('cost_price', 0))
            if not product_id:
                p = c.execute("SELECT id FROM products WHERE name = ?", (product_name,)).fetchone()
                product_id = p['id'] if p else None
            prepared.append({"product_id": product_id, "product_name": product_name, "qty": qty, "cost": cost})
        conn.close()

        payload = {"id": invoice_id, "supplier_id": None, "supplier_name": supplier_name,
                   "notes": notes, "date": inv['date'], "items": prepared}
        res = database.save_purchase_invoice(payload)
        if not res.get('success'):
            return JSONResponse(status_code=400, content=res)

        if was_received:
            rec = database.toggle_purchase_status(invoice_id, 'Received')
            if not rec.get('success'):
                return JSONResponse(status_code=500, content=rec)
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


if __name__ == "__main__":
    reload_enabled = os.environ.get("ELNAGAR_UVICORN_RELOAD", "0") == "1"
    uvicorn.run(
        "mobile_local_api_server:app",
        host="0.0.0.0",
        port=7788,
        reload=reload_enabled,
        log_level="info",
    )
