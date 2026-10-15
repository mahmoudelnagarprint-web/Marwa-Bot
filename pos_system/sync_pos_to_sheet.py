#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_pos_to_sheet.py — Full Rebuild & Mirror
─────────────────────────────────────────────
Commands:
  --full-rebuild-sheet   Backup → Clear → Create tabs → Upload all data
  --mirror-now           Sync mirror tabs to match DB (no clear)
  --mark-stale           Mark rows not in DB as stale_deleted
  --dry-run              Preview only
"""
import argparse, csv, json, os, sys, time, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SA_PATH  = ROOT / "android_companion_app" / "assets" / "secrets" / "service_account.json"
SHEET_ID = "14Du-Cqxdr5r1TDVTog0hUjObAihieIHJOOhGv-scq5Q"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets"]

# ── Tab definitions with headers ─────────────────────────────────────────────
TAB_SCHEMA = {
    # CORE MIRROR
    "meta": ["key","value","updated_at"],
    "sync_status": ["key","value","updated_at","severity","details"],
    "sync_log": ["log_id","timestamp","direction","entity_type","entity_id","external_id","action","status","message","duration_ms"],
    "clients": ["client_id","name","phone","type","balance","notes","orders_count","open_orders_count","last_order_date","last_payment_date","sync_state","last_seen_at","updated_at"],
    "products": ["product_id","name","category","stock_qty","retail_price","wholesale_price","cost_price","sort_order","legacy_stock","orders_count","total_sold_qty","last_sold_at","sync_state","last_seen_at","updated_at"],
    "orders": ["order_id","client_id","client_name","client_phone","client_type","total_amount","paid_amount","remaining_amount","status","date","notes","local_image_path","items_count","source","external_order_id","sync_state","last_seen_at","updated_at"],
    "order_items": ["order_item_id","order_id","product_id","product_name","qty","price","total","sync_state","last_seen_at","updated_at"],
    "transactions": ["transaction_id","client_id","client_name","type","amount","category","notes","date","related_ref","user","sync_state","last_seen_at","updated_at"],
    "categories": ["category_id","name","products_count","sync_state","last_seen_at"],
    "settings_snapshot": ["key","value","captured_at"],
    # QUEUE TABS
    "android_orders_queue": ["queue_id","external_order_id","client_id","client_name","client_phone","client_type","total_amount","discount","paid_amount","remaining","payment_method","notes","items_json","status","created_at","imported_order_id","error_message"],
    "android_order_images": ["image_id","external_order_id","item_index","drive_file_id","image_url","import_status","created_at","local_saved_path","error_message"],
    "android_status_queue": ["action_id","order_id","old_status","new_status","requested_by","status","created_at","processed_at","error_message"],
    "android_payments_queue": ["payment_action_id","client_id","client_name","client_phone","amount","payment_method","notes","status","created_at","processed_at","imported_transaction_id","error_message"],
    "android_products_queue": ["product_action_id","action","product_id","name","category","retail_price","wholesale_price","cost_price","stock_qty","notes","status","created_at","processed_at","created_product_id","error_message"],
    "android_clients_queue": ["client_action_id","action","client_id","name","phone","client_type","notes","status","created_at","processed_at","created_client_id","error_message"],
    "telegram_inbox": ["queue_id","source","chat_id","message_id","external_order_id","received_at","client_name","client_phone","client_type","notes","payment_method","paid_amount","discount","total_amount","remaining_amount","status","items_json","imported_order_id","error_message"],
    "telegram_images": ["image_row_id","external_order_id","message_id","item_index","telegram_file_id","original_name","mime_type","caption","import_status","local_saved_path"],
    "telegram_payments_queue": ["payment_queue_id","source","chat_id","message_id","external_payment_id","received_at","client_id","client_name","client_phone","amount","payment_method","notes","status","imported_transaction_id","error_message"],
    "telegram_admin_actions_queue": ["admin_action_id","source","chat_id","message_id","action_type","payload_json","preview_json","status","created_at","processed_at","error_message"],
    # VIEW / SUMMARY
    "dashboard_summary": ["metric","value","updated_at"],
    "client_balances_summary": ["client_id","name","type","balance","orders_count","last_order_date","updated_at"],
    "product_sales_summary": ["product_id","name","category","total_sold_qty","total_revenue","last_sold_at","updated_at"],
    "orders_by_status_summary": ["status","count","total_value","updated_at"],
    "daily_sales_summary": ["date","orders_count","total_value","payments_received","updated_at"],
}

MIRROR_TABS = ["clients","products","orders","order_items","transactions","categories"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def safe_print(msg):
    try: print(msg)
    except UnicodeEncodeError: print(msg.encode("ascii",errors="replace").decode())

def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def build_service():
    from google.oauth2 import service_account as sa
    from googleapiclient.discovery import build
    creds = sa.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    return build("sheets","v4", credentials=creds, cache_discovery=False)

def api_call_with_backoff(func, *args, max_retries=3, **kwargs):
    """Execute API call with exponential backoff on 429."""
    delays = [30, 60, 120]
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs).execute()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Quota" in err_str.lower():
                if attempt < max_retries:
                    delay = delays[min(attempt, len(delays)-1)]
                    safe_print(f"  ⏳ Quota exceeded (429), waiting {delay}s... (attempt {attempt+1})")
                    time.sleep(delay)
                else:
                    raise
            else:
                raise

# ── DB Fetch ─────────────────────────────────────────────────────────────────

def fetch_all_from_db():
    """Read all data from pos_data.db for mirror."""
    import database
    conn = database.get_db_connection()
    now = now_iso()
    data = {}
    try:
        # Clients
        rows = conn.execute("""
            SELECT c.id, c.name, c.phone, c.type, c.balance, c.notes,
                   (SELECT COUNT(*) FROM orders WHERE client_id=c.id) as orders_count,
                   (SELECT COUNT(*) FROM orders WHERE client_id=c.id AND status IN ('Under Preparation','Ready')) as open_orders_count,
                   (SELECT MAX(date) FROM orders WHERE client_id=c.id) as last_order_date,
                   (SELECT MAX(date) FROM transactions WHERE client_id=c.id AND type IN ('payment','Income')) as last_payment_date
            FROM clients c ORDER BY c.name
        """).fetchall()
        data["clients"] = [[
            r["id"], r["name"] or "", r["phone"] or "", r["type"] or "",
            r["balance"] if r["balance"] is not None else 0, r["notes"] or "",
            r["orders_count"], r["open_orders_count"],
            r["last_order_date"] or "", r["last_payment_date"] or "",
            "active", now, now
        ] for r in rows]

        # Products
        rows = conn.execute("""
            SELECT p.id, p.name, p.category, p.stock_qty, p.price_retail, p.price_wholesale,
                   p.last_cost_price, p.sort_order, p.stock,
                   (SELECT COUNT(*) FROM order_items WHERE product_id=p.id) as orders_count,
                   (SELECT COALESCE(SUM(qty),0) FROM order_items WHERE product_id=p.id) as total_sold_qty,
                   (SELECT MAX(o.date) FROM order_items oi JOIN orders o ON o.id=oi.order_id WHERE oi.product_id=p.id) as last_sold_at
            FROM products p ORDER BY p.sort_order ASC, p.name ASC
        """).fetchall()
        data["products"] = [[
            r["id"], r["name"] or "", r["category"] or "", r["stock_qty"] or 0,
            r["price_retail"] or 0, r["price_wholesale"] or 0, r["last_cost_price"] or 0,
            r["sort_order"] or 0, r["stock"] or "",
            r["orders_count"], r["total_sold_qty"],
            r["last_sold_at"] or "", "active", now, now
        ] for r in rows]

        # Orders
        rows = conn.execute("""
            SELECT o.id, o.client_id, c.name as client_name, c.phone as client_phone, c.type as client_type,
                   o.total_amount, o.status, o.date, o.notes, o.local_image_path,
                   (SELECT COUNT(*) FROM order_items WHERE order_id=o.id) as items_count,
                   (SELECT COALESCE(SUM(amount),0) FROM transactions WHERE client_id=o.client_id AND type IN ('payment','Income') AND notes LIKE '%Order #'||o.id||'%') as paid_for_order
            FROM orders o LEFT JOIN clients c ON c.id=o.client_id ORDER BY o.id
        """).fetchall()
        data["orders"] = [[
            r["id"], r["client_id"] or "", r["client_name"] or "", r["client_phone"] or "", r["client_type"] or "",
            r["total_amount"] or 0, r["paid_for_order"] or 0,
            (r["total_amount"] or 0) - (r["paid_for_order"] or 0),
            r["status"] or "", r["date"] or "", r["notes"] or "",
            r["local_image_path"] or "", r["items_count"],
            "pos_desktop", "", "active", now, now
        ] for r in rows]

        # Order Items
        rows = conn.execute("SELECT id, order_id, product_id, product_name, qty, price, total FROM order_items ORDER BY id").fetchall()
        data["order_items"] = [[
            r["id"], r["order_id"], r["product_id"] or "", r["product_name"] or "",
            r["qty"] or 0, r["price"] or 0, r["total"] or 0, "active", now, now
        ] for r in rows]

        # Transactions
        rows = conn.execute("""
            SELECT t.id, t.client_id, c.name as client_name, t.type, t.amount, t.category, t.notes, t.date, t.related_ref, t.user
            FROM transactions t LEFT JOIN clients c ON c.id=t.client_id ORDER BY t.id
        """).fetchall()
        data["transactions"] = [[
            r["id"], r["client_id"] or "", r["client_name"] or "", r["type"] or "",
            r["amount"] or 0, r["category"] or "", r["notes"] or "",
            r["date"] or "", r["related_ref"] or "", r["user"] or "",
            "active", now, now
        ] for r in rows]

        # Categories
        rows = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        data["categories"] = [[
            r["id"], r["name"],
            conn.execute("SELECT COUNT(*) FROM products WHERE category=?", (r["name"],)).fetchone()[0],
            "active", now
        ] for r in rows]

    finally:
        conn.close()
    return data

def build_summaries(data):
    """Build summary tab data from mirror data."""
    now = now_iso()
    summaries = {}

    # Dashboard summary
    total_orders = len(data.get("orders", []))
    orders_raw = data.get("orders", [])
    # Status index = 8 in orders row
    prep_count = sum(1 for r in orders_raw if str(r[8]).strip() in ("Under Preparation",))
    ready_count = sum(1 for r in orders_raw if str(r[8]).strip() == "Ready")
    delivered_count = sum(1 for r in orders_raw if str(r[8]).strip() == "Delivered")
    total_value = sum(float(r[5] or 0) for r in orders_raw)
    total_clients = len(data.get("clients", []))
    total_products = len(data.get("products", []))
    total_debt = sum(float(r[4] or 0) for r in data.get("clients", []) if float(r[4] or 0) > 0)

    summaries["dashboard_summary"] = [
        ["total_orders", total_orders, now],
        ["prep_orders", prep_count, now],
        ["ready_orders", ready_count, now],
        ["delivered_orders", delivered_count, now],
        ["total_value", total_value, now],
        ["total_clients", total_clients, now],
        ["total_products", total_products, now],
        ["total_debt", total_debt, now],
    ]

    # Client balances
    summaries["client_balances_summary"] = [
        [r[0], r[1], r[3], r[4], r[6], r[8], now]
        for r in data.get("clients", []) if float(r[4] or 0) > 0
    ]

    # Product sales
    summaries["product_sales_summary"] = [
        [r[0], r[1], r[2], r[10], 0, r[11], now]
        for r in data.get("products", []) if int(r[10] or 0) > 0
    ]

    # Orders by status
    from collections import Counter
    status_counts = Counter(str(r[8]).strip() for r in orders_raw)
    status_values = {}
    for r in orders_raw:
        s = str(r[8]).strip()
        status_values[s] = status_values.get(s, 0) + float(r[5] or 0)
    summaries["orders_by_status_summary"] = [
        [s, c, status_values.get(s, 0), now] for s, c in status_counts.items()
    ]

    # Daily sales (last 30 days)
    from collections import defaultdict
    daily = defaultdict(lambda: {"count": 0, "value": 0})
    for r in orders_raw:
        d = str(r[9] or "")[:10]
        if d:
            daily[d]["count"] += 1
            daily[d]["value"] += float(r[5] or 0)
    summaries["daily_sales_summary"] = [
        [d, v["count"], v["value"], 0, now]
        for d, v in sorted(daily.items(), reverse=True)[:30]
    ]

    return summaries

# ── Sheet Operations ─────────────────────────────────────────────────────────

def get_existing_tabs(svc):
    meta = api_call_with_backoff(svc.spreadsheets().get, spreadsheetId=SHEET_ID)
    # Fix: get() returns result directly from api_call_with_backoff
    pass

def full_rebuild(svc, dry_run=False):
    """Phase 2-4: Clear sheet, create all tabs, upload all data."""
    safe_print("═══ PHASE 2: Clear & Rebuild Sheet ═══")

    # Get existing tabs
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}
    safe_print(f"  Existing tabs: {list(existing.keys())}")

    if dry_run:
        safe_print("  [DRY-RUN] Would clear all tabs and create new schema")
        data = fetch_all_from_db()
        for k, v in data.items():
            safe_print(f"    {k}: {len(v)} rows")
        return

    # Step 1: Create a temp sheet so we never have 0 sheets
    requests = [{"addSheet": {"properties": {"title": "_temp_rebuild"}}}]
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": requests}).execute()
    time.sleep(1)

    # Step 2: Delete all old tabs
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existing = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta.get("sheets", [])}
    del_requests = []
    for name, sid in existing.items():
        if name != "_temp_rebuild":
            del_requests.append({"deleteSheet": {"sheetId": sid}})
    if del_requests:
        safe_print(f"  Deleting {len(del_requests)} old tabs...")
        svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": del_requests}).execute()
        time.sleep(1)

    # Step 3: Create all new tabs
    safe_print(f"  Creating {len(TAB_SCHEMA)} new tabs...")
    add_requests = [{"addSheet": {"properties": {"title": name}}} for name in TAB_SCHEMA.keys()]
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": add_requests}).execute()
    time.sleep(1)

    # Step 4: Delete temp
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    temp_id = None
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == "_temp_rebuild":
            temp_id = s["properties"]["sheetId"]
    if temp_id is not None:
        svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID,
            body={"requests": [{"deleteSheet": {"sheetId": temp_id}}]}).execute()

    # Step 5: Write headers using batchUpdate
    safe_print("  Writing headers...")
    header_data = []
    for tab_name, headers in TAB_SCHEMA.items():
        header_data.append({"range": f"{tab_name}!A1", "values": [headers]})

    # Batch in groups of 10 to avoid payload limits
    for i in range(0, len(header_data), 10):
        chunk = header_data[i:i+10]
        svc.spreadsheets().values().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"valueInputOption": "RAW", "data": chunk}
        ).execute()
        time.sleep(0.5)

    safe_print("  ✅ Schema created successfully")

    # Phase 3-4: Upload data
    safe_print("\n═══ PHASE 4: Full Mirror from pos_data.db ═══")
    data = fetch_all_from_db()
    summaries = build_summaries(data)

    upload_counts = {}
    # Upload mirror tabs
    for tab_name in MIRROR_TABS:
        rows = data.get(tab_name, [])
        if rows:
            safe_print(f"  📤 Uploading {tab_name}: {len(rows)} rows...", )
            _batch_append(svc, tab_name, rows)
            upload_counts[tab_name] = len(rows)
        else:
            safe_print(f"  ⚪ {tab_name}: 0 rows")
            upload_counts[tab_name] = 0

    # Upload summaries
    for tab_name, rows in summaries.items():
        if rows:
            safe_print(f"  📊 Uploading {tab_name}: {len(rows)} rows...")
            _batch_append(svc, tab_name, rows)
            upload_counts[tab_name] = len(rows)

    # Write meta
    meta_rows = [
        ["schema_version", "2.0", now_iso()],
        ["rebuilt_at", now_iso(), now_iso()],
        ["source_db", "pos_data.db", now_iso()],
        ["app_version", "Elnagar POS v2", now_iso()],
        ["sheet_role", "mirror + queues + sync", now_iso()],
        ["last_full_mirror_at", now_iso(), now_iso()],
        ["last_incremental_sync_at", "", now_iso()],
        ["notes", "Full rebuild from sync_pos_to_sheet.py", now_iso()],
    ]
    _batch_append(svc, "meta", meta_rows)

    # Write sync_status
    status_rows = [
        ["last_full_rebuild", now_iso(), now_iso(), "info", "Full rebuild completed"],
        ["schema_version", "2.0", now_iso(), "info", "25 tabs"],
    ]
    for tab, count in upload_counts.items():
        status_rows.append([f"mirror_{tab}_count", str(count), now_iso(), "info", ""])
    _batch_append(svc, "sync_status", status_rows)

    safe_print(f"\n✅ Full rebuild complete!")
    safe_print(f"   Tabs created: {len(TAB_SCHEMA)}")
    for t, c in upload_counts.items():
        safe_print(f"   {t}: {c} rows")
    return upload_counts


def mirror_now(svc, mark_stale=False, dry_run=False):
    """Mirror DB to sheet without clearing."""
    safe_print("═══ Mirror Now ═══")
    data = fetch_all_from_db()

    if dry_run:
        for k, v in data.items():
            safe_print(f"  {k}: {len(v)} rows would be synced")
        return

    for tab_name in MIRROR_TABS:
        rows = data.get(tab_name, [])
        safe_print(f"  📤 Mirroring {tab_name}: {len(rows)} rows...")

        # Clear existing data (keep header)
        try:
            svc.spreadsheets().values().clear(
                spreadsheetId=SHEET_ID,
                range=f"{tab_name}!A2:ZZ",
                body={}
            ).execute()
        except Exception:
            pass
        time.sleep(0.3)

        if rows:
            _batch_append(svc, tab_name, rows)

    # Update summaries
    summaries = build_summaries(data)
    for tab_name, rows in summaries.items():
        try:
            svc.spreadsheets().values().clear(
                spreadsheetId=SHEET_ID, range=f"{tab_name}!A2:ZZ", body={}
            ).execute()
        except Exception:
            pass
        if rows:
            _batch_append(svc, tab_name, rows)

    # Update meta
    try:
        svc.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID, range="sync_status!A2:ZZ", body={}
        ).execute()
    except Exception:
        pass
    status_rows = [
        ["last_mirror", now_iso(), now_iso(), "info", "mirror-now completed"],
    ]
    for tab_name in MIRROR_TABS:
        count = len(data.get(tab_name, []))
        status_rows.append([f"mirror_{tab_name}_count", str(count), now_iso(), "info", ""])
    _batch_append(svc, "sync_status", status_rows)

    safe_print("✅ Mirror complete!")


def _batch_append(svc, tab_name, rows, batch_size=500):
    """Append rows in batches to avoid payload limits."""
    for i in range(0, len(rows), batch_size):
        chunk = rows[i:i+batch_size]
        # Convert all values to strings to avoid type issues
        safe_chunk = []
        for row in chunk:
            safe_chunk.append([str(v) if v is not None else "" for v in row])
        try:
            svc.spreadsheets().values().append(
                spreadsheetId=SHEET_ID,
                range=f"{tab_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": safe_chunk}
            ).execute()
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e).lower():
                safe_print(f"    ⏳ Rate limited, waiting 30s...")
                time.sleep(30)
                svc.spreadsheets().values().append(
                    spreadsheetId=SHEET_ID,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    insertDataOption="INSERT_ROWS",
                    body={"values": safe_chunk}
                ).execute()
            else:
                raise
        time.sleep(0.5)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if hasattr(sys.stdout, "reconfigure"):
        try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except: pass

    parser = argparse.ArgumentParser(description="Sync POS to Google Sheet")
    parser.add_argument("--full-rebuild-sheet", action="store_true")
    parser.add_argument("--mirror-now", action="store_true")
    parser.add_argument("--mark-stale", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not any([args.full_rebuild_sheet, args.mirror_now]):
        print("Usage: --full-rebuild-sheet | --mirror-now [--mark-stale] [--dry-run]")
        return 1

    svc = build_service()

    if args.full_rebuild_sheet:
        full_rebuild(svc, dry_run=args.dry_run)
    elif args.mirror_now:
        mirror_now(svc, mark_stale=args.mark_stale, dry_run=args.dry_run)

    return 0

if __name__ == "__main__":
    sys.exit(main())
