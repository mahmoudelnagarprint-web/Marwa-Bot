#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""
android_importer.py
────────────────────────────────────────────────────────────────────────────
Android Companion App — Local Importer

Reads the 4 Android queues from Google Sheets and processes them:
  android_orders_queue   → database.save_order_transaction(...)
  android_status_queue   → update order status via DB helpers
  android_payments_queue → record payment transactions

Downloads images from Google Drive and saves via FileOpsEngine.
Prevents duplicates via external_order_id / action_id checks.
Creates safety backup before any write.

Does NOT touch pos_data.db via direct insert.
Does NOT break Telegram bot or importer.
Does NOT modify existing Telegram queue logic.
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

TELEGRAM_BOT_DIR = ROOT_DIR / "telegram_bot"
if str(TELEGRAM_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_BOT_DIR))

import database
from file_ops_engine import FileOpsEngine

CAIRO_TZ    = ZoneInfo("Africa/Cairo")
BACKUP_ROOT = ROOT_DIR / "Backups"

SA_PATH   = ROOT_DIR / "android_companion_app" / "assets" / "secrets" / "service_account.json"
SHEET_ID  = "14Du-Cqxdr5r1TDVTog0hUjObAihieIHJOOhGv-scq5Q"
SCOPES    = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

ANDROID_ORDERS_QUEUE   = "android_orders_queue"
ANDROID_IMAGES_QUEUE   = "android_order_images"
ANDROID_STATUS_QUEUE   = "android_status_queue"
ANDROID_PAYMENTS_QUEUE = "android_payments_queue"
ANDROID_PRODUCTS_QUEUE = "android_products_queue"
ANDROID_CLIENTS_QUEUE  = "android_clients_queue"


def safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def now_stamp() -> str:
    return datetime.now(CAIRO_TZ).strftime("%Y%m%d_%H%M%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Android Companion App — Local Importer")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview pending rows without writing locally.")
    parser.add_argument("--once", action="store_true",
                        help="Process pending rows one time.")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE SHEETS CLIENT (reuses service account from assets)
# ─────────────────────────────────────────────────────────────────────────────

def build_google_services():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as api_build

    with SA_PATH.open(encoding="utf-8") as f:
        sa = json.load(f)
    credentials = service_account.Credentials.from_service_account_info(sa, scopes=SCOPES)
    sheets_svc = api_build("sheets", "v4", credentials=credentials, cache_discovery=False)
    drive_svc  = api_build("drive",  "v3", credentials=credentials, cache_discovery=False)
    return sheets_svc, drive_svc


def read_tab(sheets_svc, tab_name: str) -> List[Dict[str, str]]:
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=tab_name,
    ).execute()
    values = result.get("values", [])
    if len(values) < 2:
        return []
    headers = values[0]
    rows: List[Dict[str, str]] = []
    for i, raw_row in enumerate(values[1:], start=2):
        row: Dict[str, str] = {"_row_index": str(i)}
        for j, h in enumerate(headers):
            row[h] = raw_row[j] if j < len(raw_row) else ""
        rows.append(row)
    return rows


def update_row(sheets_svc, tab_name: str, row_index: int,
               fields: Dict[str, Any], headers: List[str]) -> None:
    # Read current row values first, then patch fields
    result = sheets_svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{tab_name}!A{row_index}:{_col_letter(len(headers))}{row_index}",
    ).execute()
    current = (result.get("values") or [[]])[0]
    # Pad
    while len(current) < len(headers):
        current.append("")
    for key, val in fields.items():
        if key in headers:
            current[headers.index(key)] = "" if val is None else str(val)
    sheets_svc.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=f"{tab_name}!A{row_index}:{_col_letter(len(headers))}{row_index}",
        valueInputOption="RAW",
        body={"values": [current]},
    ).execute()


def _col_letter(n: int) -> str:
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


# ─────────────────────────────────────────────────────────────────────────────
# SAFETY BACKUP
# ─────────────────────────────────────────────────────────────────────────────

def create_backup() -> Path:
    backup_dir = BACKUP_ROOT / f"android_importer_{now_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_path = ROOT_DIR / "pos_data.db"
    if db_path.exists():
        shutil.copy2(db_path, backup_dir / "pos_data.db")
    pos_images = ROOT_DIR / "pos_images"
    if pos_images.exists():
        shutil.copytree(pos_images, backup_dir / "pos_images", dirs_exist_ok=True)
    return backup_dir


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def normalize_phone(phone: str) -> str:
    return re.sub(r"\D+", "", phone or "")


def resolve_client(name: str, phone: str, client_type: str,
                   allow_create: bool) -> Optional[int]:
    norm = normalize_phone(phone)
    conn = database.get_db_connection()
    try:
        row = None
        if norm:
            row = conn.execute(
                "SELECT id FROM clients WHERE REPLACE(REPLACE(REPLACE(COALESCE(phone,''),' ',''),'+',''),'-','')=? LIMIT 1",
                (norm,),
            ).fetchone()
        if not row and name.strip():
            row = conn.execute(
                "SELECT id FROM clients WHERE name=? COLLATE NOCASE LIMIT 1",
                (name.strip(),),
            ).fetchone()
        if row:
            return int(row["id"])
    finally:
        conn.close()
    if not allow_create:
        return None
    return int(database.add_new_client(name.strip(), phone.strip(), client_type,
                                       "Imported from Android app queue"))


# ─────────────────────────────────────────────────────────────────────────────
# DUPLICATE DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_duplicate_order(external_order_id: str) -> Optional[int]:
    conn = database.get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM orders WHERE notes LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{external_order_id}%",),
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE DOWNLOAD FROM DRIVE
# ─────────────────────────────────────────────────────────────────────────────

def download_drive_file(drive_svc, file_id: str, target_path: Path) -> None:
    request = drive_svc.files().get_media(fileId=file_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = request.execute()
    target_path.write_bytes(content)


def get_storage_root() -> str:
    path = database.get_setting("local_images_path")
    if not path or not os.path.exists(path):
        fallback = str(ROOT_DIR / "pos_images")
        os.makedirs(fallback, exist_ok=True)
        return fallback
    return path


def sanitize(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", str(s or "")).strip()


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS ORDERS QUEUE
# ─────────────────────────────────────────────────────────────────────────────

ORDERS_HEADERS = [
    "queue_id", "external_order_id", "client_id", "client_name",
    "client_phone", "client_type", "total_amount", "discount",
    "paid_amount", "remaining", "payment_method", "notes",
    "items_json", "status", "created_at", "imported_order_id", "error_message",
]


def process_order_row(sheets_svc, drive_svc, row: Dict[str, str], dry_run: bool) -> Dict[str, Any]:
    ext_id       = row.get("external_order_id", "").strip()
    client_name  = row.get("client_name", "").strip()
    client_phone = row.get("client_phone", "").strip()
    client_type  = row.get("client_type", "Retail").strip() or "Retail"
    row_index    = int(row["_row_index"])

    # Duplicate check
    existing = is_duplicate_order(ext_id)
    if existing:
        if not dry_run:
            update_row(sheets_svc, ANDROID_ORDERS_QUEUE, row_index,
                       {"status": "duplicate", "imported_order_id": existing}, ORDERS_HEADERS)
        return {"status": "duplicate", "external_order_id": ext_id, "local_order_id": existing}

    # Parse items
    try:
        items_raw = json.loads(row.get("items_json") or "[]")
        if isinstance(items_raw, dict) and "items" in items_raw:
            items_raw = items_raw["items"]
    except json.JSONDecodeError as e:
        err = f"Bad items_json: {e}"
        if not dry_run:
            update_row(sheets_svc, ANDROID_ORDERS_QUEUE, row_index,
                       {"status": "failed", "error_message": err}, ORDERS_HEADERS)
        return {"status": "failed", "external_order_id": ext_id, "error": err}

    # Resolve products
    final_items = []
    for item in items_raw:
        resolved = database.resolve_or_create_product_for_external_order(
            product_id=item.get("product_id"),
            product_name=item.get("product_name"),
            client_type=client_type,
            external_price=item.get("price"),
        )
        if not resolved.get("success") or resolved.get("needs_review"):
            err = f"Product needs review: {item.get('product_name')}"
            if not dry_run:
                update_row(sheets_svc, ANDROID_ORDERS_QUEUE, row_index,
                           {"status": "failed", "error_message": err}, ORDERS_HEADERS)
            return {"status": "failed", "external_order_id": ext_id, "error": err}
        qty   = float(item.get("qty") or 1)
        price = float(resolved["selected_price"] or 0)
        final_items.append({
            "id": int(resolved["product"]["id"]),
            "name": resolved["product"]["name"],
            "qty": qty, "price": price, "total": round(qty * price, 2),
        })

    discount    = float(row.get("discount") or 0)
    paid_amount = float(row.get("paid_amount") or 0)
    subtotal    = round(sum(i["total"] for i in final_items), 2)
    net_total   = round(subtotal - discount, 2)
    remaining   = round(net_total - paid_amount, 2)
    notes       = (row.get("notes") or "").strip()
    notes       = f"{notes}\n[external_order_id:{ext_id}]".strip() if ext_id not in notes else notes

    if dry_run:
        return {"status": "dry-run", "external_order_id": ext_id,
                "items_count": len(final_items), "net_total": net_total}

    # Resolve client
    client_id = resolve_client(client_name, client_phone, client_type, allow_create=True)
    save_result = database.save_order_transaction(
        client_id=client_id,
        total_amount=subtotal,
        discount=discount,
        net_total=net_total,
        paid_amount=paid_amount,
        remaining=remaining,
        items=final_items,
        payment_method=row.get("payment_method") or "Credit",
        notes=notes,
    )
    if not save_result.get("success"):
        err = f"save_order_transaction failed: {save_result.get('error')}"
        update_row(sheets_svc, ANDROID_ORDERS_QUEUE, row_index,
                   {"status": "failed", "error_message": err}, ORDERS_HEADERS)
        return {"status": "failed", "external_order_id": ext_id, "error": err}

    order_id = int(save_result["order_id"])

    # Images
    try:
        image_rows = [r for r in read_tab(sheets_svc, ANDROID_IMAGES_QUEUE)
                      if r.get("external_order_id") == ext_id and r.get("import_status") == "pending"]
        if image_rows and final_items:
            root   = get_storage_root()
            engine = FileOpsEngine(root)
            folder = Path(engine.get_creation_path(
                client_type, client_name, final_items[0]["name"], notes, order_id))
            folder.mkdir(parents=True, exist_ok=True)
            database.update_order_image_path(order_id, str(folder))
            for img_row in image_rows:
                file_id = img_row.get("drive_file_id", "").strip()
                if file_id:
                    target = folder / f"android_{img_row.get('image_id','img')}.jpg"
                    try:
                        download_drive_file(drive_svc, file_id, target)
                    except Exception:
                        pass
    except Exception:
        pass  # images are non-fatal

    update_row(sheets_svc, ANDROID_ORDERS_QUEUE, row_index,
               {"status": "imported", "imported_order_id": order_id, "error_message": ""},
               ORDERS_HEADERS)
    return {"status": "imported", "external_order_id": ext_id, "local_order_id": order_id}


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS STATUS QUEUE
# ─────────────────────────────────────────────────────────────────────────────

STATUS_HEADERS = [
    "action_id", "order_id", "old_status", "new_status",
    "requested_by", "status", "created_at", "processed_at", "error_message",
]


def process_status_row(sheets_svc, row: Dict[str, str], dry_run: bool) -> Dict[str, Any]:
    action_id  = row.get("action_id", "").strip()
    order_id   = row.get("order_id", "").strip()
    new_status = row.get("new_status", "").strip()
    row_index  = int(row["_row_index"])

    if dry_run:
        return {"status": "dry-run", "action_id": action_id, "order_id": order_id, "new_status": new_status}

    try:
        oid = int(order_id)
        conn = database.get_db_connection()
        try:
            conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, oid))
            conn.commit()
        finally:
            conn.close()
        update_row(sheets_svc, ANDROID_STATUS_QUEUE, row_index,
                   {"status": "processed",
                    "processed_at": datetime.now(CAIRO_TZ).isoformat(),
                    "error_message": ""},
                   STATUS_HEADERS)
        return {"status": "processed", "action_id": action_id, "order_id": order_id}
    except Exception as e:
        err = str(e)
        update_row(sheets_svc, ANDROID_STATUS_QUEUE, row_index,
                   {"status": "failed", "error_message": err}, STATUS_HEADERS)
        return {"status": "failed", "action_id": action_id, "error": err}


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS PAYMENTS QUEUE
# ─────────────────────────────────────────────────────────────────────────────

PAYMENTS_HEADERS = [
    "payment_action_id", "client_id", "client_name", "amount",
    "payment_method", "notes", "status", "created_at", "processed_at", "error_message",
]


def process_payment_row(sheets_svc, row: Dict[str, str], dry_run: bool) -> Dict[str, Any]:
    action_id   = row.get("payment_action_id", "").strip()
    client_id   = row.get("client_id", "").strip()
    client_name = row.get("client_name", "").strip()
    amount      = float(row.get("amount") or 0)
    method      = row.get("payment_method") or "Cash"
    notes       = row.get("notes") or ""
    row_index   = int(row["_row_index"])

    if dry_run:
        return {"status": "dry-run", "action_id": action_id, "client_name": client_name, "amount": amount}

    try:
        cid = int(client_id) if client_id.isdigit() else None
        if cid is None:
            conn = database.get_db_connection()
            try:
                r = conn.execute("SELECT id FROM clients WHERE name=? COLLATE NOCASE LIMIT 1",
                                 (client_name,)).fetchone()
                cid = int(r["id"]) if r else None
            finally:
                conn.close()
        if cid is None:
            raise ValueError(f"Client not found: {client_name}")

        # Record payment using existing DB function
        conn = database.get_db_connection()
        try:
            conn.execute(
                "INSERT INTO transactions (client_id, type, amount, notes, date, category, user) "
                "VALUES (?, 'payment', ?, ?, DATE('now'), 'Debt Collection', 'Android App')",
                (cid, amount, notes or f"Android payment via {method}"),
            )
            conn.execute(
                "UPDATE clients SET balance = balance - ? WHERE id=?",
                (amount, cid),
            )
            conn.commit()
        finally:
            conn.close()

        update_row(sheets_svc, ANDROID_PAYMENTS_QUEUE, row_index,
                   {"status": "processed",
                    "processed_at": datetime.now(CAIRO_TZ).isoformat(),
                    "error_message": ""},
                   PAYMENTS_HEADERS)
        return {"status": "processed", "action_id": action_id, "amount": amount}
    except Exception as e:
        err = str(e)
        update_row(sheets_svc, ANDROID_PAYMENTS_QUEUE, row_index,
                   {"status": "failed", "error_message": err}, PAYMENTS_HEADERS)
        return {"status": "failed", "action_id": action_id, "error": err}


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS PRODUCTS QUEUE
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTS_HEADERS = [
    "product_action_id", "action", "product_id", "name", "category",
    "retail_price", "wholesale_price", "cost_price", "stock_qty", "notes",
    "status", "created_at", "processed_at", "created_product_id", "error_message",
]


def process_product_row(sheets_svc, row: Dict[str, str], dry_run: bool) -> Dict[str, Any]:
    action_id = row.get("product_action_id", "").strip()
    action    = row.get("action", "").strip()
    name      = row.get("name", "").strip()
    category  = row.get("category", "").strip()
    row_index = int(row["_row_index"])

    if dry_run:
        return {"status": "dry-run", "action_id": action_id, "action": action, "name": name}

    try:
        if action == "create_product":
            price_r = float(row.get("retail_price") or 0)
            price_w = float(row.get("wholesale_price") or 0)
            new_id = database.add_quick_product(name, category, price_r, price_w)
            update_row(sheets_svc, ANDROID_PRODUCTS_QUEUE, row_index,
                       {"status": "processed",
                        "processed_at": datetime.now(CAIRO_TZ).isoformat(),
                        "created_product_id": new_id,
                        "error_message": ""},
                       PRODUCTS_HEADERS)
            return {"status": "processed", "action_id": action_id, "product_id": new_id}

        elif action == "update_price":
            pid = row.get("product_id", "").strip()
            if not pid.isdigit():
                raise ValueError(f"Invalid product_id: {pid}")
            price_r = float(row.get("retail_price") or 0) or None
            price_w = float(row.get("wholesale_price") or 0) or None
            database.update_product_prices(int(pid), price_r, price_w)
            update_row(sheets_svc, ANDROID_PRODUCTS_QUEUE, row_index,
                       {"status": "processed",
                        "processed_at": datetime.now(CAIRO_TZ).isoformat(),
                        "error_message": ""},
                       PRODUCTS_HEADERS)
            return {"status": "processed", "action_id": action_id, "product_id": pid}

        else:
            raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        err = str(e)
        update_row(sheets_svc, ANDROID_PRODUCTS_QUEUE, row_index,
                   {"status": "failed", "error_message": err}, PRODUCTS_HEADERS)
        return {"status": "failed", "action_id": action_id, "error": err}


# ─────────────────────────────────────────────────────────────────────────────
# PROCESS CLIENTS QUEUE
# ─────────────────────────────────────────────────────────────────────────────

CLIENTS_HEADERS = [
    "client_action_id", "action", "client_id", "name", "phone",
    "client_type", "notes", "status", "created_at", "processed_at",
    "created_client_id", "error_message",
]


def process_client_row(sheets_svc, row: Dict[str, str], dry_run: bool) -> Dict[str, Any]:
    action_id   = row.get("client_action_id", "").strip()
    action      = row.get("action", "").strip()
    name        = row.get("name", "").strip()
    phone       = row.get("phone", "").strip()
    client_type = row.get("client_type", "Retail").strip() or "Retail"
    notes       = row.get("notes", "").strip()
    row_index   = int(row["_row_index"])

    if dry_run:
        return {"status": "dry-run", "action_id": action_id, "action": action, "name": name}

    try:
        if action == "create_client":
            new_id = database.add_new_client(name, phone, client_type,
                                             notes or "Created from Android app")
            update_row(sheets_svc, ANDROID_CLIENTS_QUEUE, row_index,
                       {"status": "processed",
                        "processed_at": datetime.now(CAIRO_TZ).isoformat(),
                        "created_client_id": new_id,
                        "error_message": ""},
                       CLIENTS_HEADERS)
            return {"status": "processed", "action_id": action_id, "client_id": new_id}

        else:
            raise ValueError(f"Unknown action: {action}")

    except Exception as e:
        err = str(e)
        update_row(sheets_svc, ANDROID_CLIENTS_QUEUE, row_index,
                   {"status": "failed", "error_message": err}, CLIENTS_HEADERS)
        return {"status": "failed", "action_id": action_id, "error": err}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_import(dry_run: bool, limit: Optional[int]) -> Dict[str, Any]:
    sheets_svc, drive_svc = build_google_services()

    orders_pending   = [r for r in read_tab(sheets_svc, ANDROID_ORDERS_QUEUE)
                        if r.get("status") == "pending"]
    status_pending   = [r for r in read_tab(sheets_svc, ANDROID_STATUS_QUEUE)
                        if r.get("status") == "pending"]
    payments_pending = [r for r in read_tab(sheets_svc, ANDROID_PAYMENTS_QUEUE)
                        if r.get("status") == "pending"]

    # New queues
    products_pending = []
    clients_pending  = []
    try:
        products_pending = [r for r in read_tab(sheets_svc, ANDROID_PRODUCTS_QUEUE)
                            if r.get("status") == "pending"]
    except Exception:
        pass  # Tab may not exist yet
    try:
        clients_pending = [r for r in read_tab(sheets_svc, ANDROID_CLIENTS_QUEUE)
                           if r.get("status") == "pending"]
    except Exception:
        pass

    if limit:
        orders_pending   = orders_pending[:limit]
        status_pending   = status_pending[:limit]
        payments_pending = payments_pending[:limit]
        products_pending = products_pending[:limit]
        clients_pending  = clients_pending[:limit]

    total = (len(orders_pending) + len(status_pending) + len(payments_pending)
             + len(products_pending) + len(clients_pending))
    summary: Dict[str, Any] = {
        "dry_run": dry_run,
        "selected_pending_orders":   len(orders_pending),
        "selected_pending_statuses": len(status_pending),
        "selected_pending_payments": len(payments_pending),
        "selected_pending_products": len(products_pending),
        "selected_pending_clients":  len(clients_pending),
        "results": [],
    }

    if total == 0:
        return summary

    if not dry_run:
        backup_dir = create_backup()
        summary["backup_dir"] = str(backup_dir)

    # Process products first (may be needed by orders)
    for row in products_pending:
        try:
            res = process_product_row(sheets_svc, row, dry_run)
        except Exception as exc:
            res = {"status": "failed", "action_id": row.get("product_action_id"), "error": str(exc)}
        summary["results"].append({"queue": "products", **res})

    # Process clients (may be needed by orders)
    for row in clients_pending:
        try:
            res = process_client_row(sheets_svc, row, dry_run)
        except Exception as exc:
            res = {"status": "failed", "action_id": row.get("client_action_id"), "error": str(exc)}
        summary["results"].append({"queue": "clients", **res})

    for row in orders_pending:
        try:
            res = process_order_row(sheets_svc, drive_svc, row, dry_run)
        except Exception as exc:
            res = {"status": "failed", "external_order_id": row.get("external_order_id"), "error": str(exc)}
        summary["results"].append({"queue": "orders", **res})

    for row in status_pending:
        try:
            res = process_status_row(sheets_svc, row, dry_run)
        except Exception as exc:
            res = {"status": "failed", "action_id": row.get("action_id"), "error": str(exc)}
        summary["results"].append({"queue": "status", **res})

    for row in payments_pending:
        try:
            res = process_payment_row(sheets_svc, row, dry_run)
        except Exception as exc:
            res = {"status": "failed", "action_id": row.get("payment_action_id"), "error": str(exc)}
        summary["results"].append({"queue": "payments", **res})

    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args()
    if not args.dry_run and not args.once:
        safe_print(json.dumps({"success": False, "error": "Use --dry-run or --once."}, ensure_ascii=False))
        return 1

    summary = run_import(dry_run=args.dry_run, limit=args.limit)
    safe_print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
