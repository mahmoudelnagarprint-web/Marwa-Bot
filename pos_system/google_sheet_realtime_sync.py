import datetime as dt
import json
import logging
import os
import re
import threading

from googleapiclient.discovery import build
from google.oauth2 import service_account

CONFIG_FILE = "google_sheet_sync_config.json"
LOG_FILE = "google_sheets_sync.log"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TAB_HEADERS = {
    "clients": ["client_id", "name", "phone", "type", "balance", "notes"],
    "products": [
        "product_id",
        "name",
        "category",
        "stock_qty",
        "retail_price",
        "wholesale_price",
        "cost_price",
        "sort_order",
        "legacy_stock",
    ],
    "orders": ["order_id", "client_id", "client_name", "total_amount", "status", "date", "notes", "local_image_path"],
    "order_items": ["order_item_id", "order_id", "product_id", "product_name", "qty", "price", "total"],
    "sync_log": ["timestamp", "level", "entity_type", "entity_id", "action", "message"],
}

DEFAULT_CONFIG = {
    "enabled": True,
    "spreadsheet_url": "https://docs.google.com/spreadsheets/d/14Du-Cqxdr5r1TDVTog0hUjObAihieIHJOOhGv-scq5Q/edit?usp=sharing",
    "spreadsheet_id": "14Du-Cqxdr5r1TDVTog0hUjObAihieIHJOOhGv-scq5Q",
    "tabs": {
        "clients": "clients",
        "products": "products",
        "orders": "orders",
        "order_items": "order_items",
        "sync_log": "sync_log",
    },
}

_LOGGER = logging.getLogger("google_sheet_sync")
_SYNC_LOCK = threading.Lock()


def _setup_logger():
    if _LOGGER.handlers:
        return
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(logging.INFO)


def log_local(level, message):
    _setup_logger()
    getattr(_LOGGER, level.lower(), _LOGGER.info)(message)


def _extract_sheet_id(url):
    if not url:
        return ""
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    return match.group(1) if match else ""


def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        config.update({k: v for k, v in loaded.items() if k != "tabs"})
        config["tabs"] = dict(DEFAULT_CONFIG["tabs"])
        config["tabs"].update(loaded.get("tabs", {}))

    spreadsheet_id = config.get("spreadsheet_id") or _extract_sheet_id(config.get("spreadsheet_url", ""))
    config["spreadsheet_id"] = spreadsheet_id
    return config


class POSGoogleSheetSync:
    def __init__(self, dry_run=False, allow_interactive_auth=False):
        self.dry_run = dry_run
        self.allow_interactive_auth = allow_interactive_auth
        self.config = load_config()
        self.spreadsheet_id = self.config.get("spreadsheet_id")
        self.tabs = self.config.get("tabs", {})
        self.sheets_service = None
        self._row_cache = {}
        self._sheet_titles = set()

    def is_enabled(self):
        return bool(self.config.get("enabled", True)) and bool(self.spreadsheet_id)

    def authenticate(self):
        if self.dry_run:
            return
        creds = self._build_credentials()
        self.sheets_service = build("sheets", "v4", credentials=creds)

    def _build_credentials(self):
        if os.path.exists("credentials.json"):
            with open("credentials.json", "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if payload.get("type") == "service_account":
                log_local("info", "Using service account credentials for Google Sheets sync.")
                return service_account.Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

        import auth

        if self.allow_interactive_auth:
            log_local("info", "Using OAuth credentials with interactive fallback for Google Sheets sync.")
            return auth.authenticate()

        raise RuntimeError(
            "No usable service-account credentials found for non-interactive sync. "
            "Share the sheet with the service-account email in credentials.json or run a manual OAuth re-auth flow."
        )

    def ensure_ready(self):
        if not self.is_enabled():
            raise RuntimeError("Google Sheet sync is disabled or spreadsheet_id is missing.")
        if self.dry_run:
            return
        self.authenticate()
        self._ensure_tabs_exist()
        self._ensure_headers()
        self._load_row_cache()

    def _ensure_tabs_exist(self):
        meta = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        self._sheet_titles = {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}

        requests = []
        for logical_name, tab_name in self.tabs.items():
            if tab_name not in self._sheet_titles:
                requests.append({"addSheet": {"properties": {"title": tab_name}}})
                self._sheet_titles.add(tab_name)
                log_local("info", f"Creating missing Google Sheet tab: {tab_name}")

        if requests:
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()

    def _ensure_headers(self):
        for logical_name, headers in TAB_HEADERS.items():
            tab_name = self.tabs[logical_name]
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!1:1",
            ).execute()
            values = result.get("values", [])
            if not values or not any(str(cell).strip() for cell in values[0]):
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    body={"values": [headers]},
                ).execute()
                log_local("info", f"Headers initialized for tab: {tab_name}")

    def _load_row_cache(self):
        self._row_cache = {}
        for logical_name, tab_name in self.tabs.items():
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!A2:A",
            ).execute()
            values = result.get("values", [])
            mapping = {}
            for index, row in enumerate(values, start=2):
                if row and str(row[0]).strip():
                    mapping[str(row[0]).strip()] = index
            self._row_cache[logical_name] = mapping

    def _append_sync_log(self, level, entity_type, entity_id, action, message):
        if self.dry_run or not self.sheets_service:
            return
        tab_name = self.tabs["sync_log"]
        row = [[
            dt.datetime.now().isoformat(timespec="seconds"),
            level.upper(),
            entity_type,
            str(entity_id),
            action,
            message,
        ]]
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": row},
        ).execute()

    def _upsert_rows(self, logical_name, rows):
        if self.dry_run or not rows:
            return len(rows), 0

        tab_name = self.tabs[logical_name]
        headers = TAB_HEADERS[logical_name]
        id_index = 0
        update_payloads = []
        append_values = []
        append_ids = []

        for row in rows:
            row_values = [row.get(header, "") for header in headers]
            row_id = str(row_values[id_index]).strip()
            if not row_id:
                continue

            existing_row = self._row_cache[logical_name].get(row_id)
            if existing_row:
                update_payloads.append({
                    "range": f"{tab_name}!A{existing_row}",
                    "values": [row_values],
                })
            else:
                append_values.append(row_values)
                append_ids.append(row_id)

        if update_payloads:
            self.sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": update_payloads,
                },
            ).execute()

        if append_values:
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": append_values},
            ).execute()
            next_row_number = len(self._row_cache[logical_name]) + 2
            for row_id in append_ids:
                self._row_cache[logical_name][row_id] = next_row_number
                next_row_number += 1

        return len(append_values), len(update_payloads)

    def _get_db_connection(self):
        from database import get_db_connection

        return get_db_connection()

    def _fetch_client_by_id(self, client_id):
        conn = self._get_db_connection()
        try:
            row = conn.execute(
                "SELECT id, name, phone, type, balance, notes FROM clients WHERE id = ?",
                (client_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "client_id": row["id"],
                "name": row["name"] or "",
                "phone": row["phone"] or "",
                "type": row["type"] or "",
                "balance": row["balance"] if row["balance"] is not None else "",
                "notes": row["notes"] or "",
            }
        finally:
            conn.close()

    def _map_product_row(self, row):
        if not row:
            return None
        return {
            "product_id": row["id"],
            "name": row["name"] or "",
            "category": row["category"] or "",
            "stock_qty": row["stock_qty"] if row["stock_qty"] is not None else "",
            "retail_price": row["price_retail"] if row["price_retail"] is not None else "",
            "wholesale_price": row["price_wholesale"] if row["price_wholesale"] is not None else "",
            "cost_price": row["last_cost_price"] if row["last_cost_price"] is not None else "",
            "sort_order": row["sort_order"] if row["sort_order"] is not None else "",
            "legacy_stock": row["stock"] if row["stock"] is not None else "",
        }

    def _fetch_order_bundle(self, order_id):
        conn = self._get_db_connection()
        try:
            order = conn.execute(
                """
                SELECT o.id, o.client_id, c.name AS client_name, o.total_amount, o.status,
                       o.date, o.notes, o.local_image_path
                FROM orders o
                LEFT JOIN clients c ON c.id = o.client_id
                WHERE o.id = ?
                """,
                (order_id,),
            ).fetchone()
            if not order:
                return None

            items = conn.execute(
                """
                SELECT id, order_id, product_id, product_name, qty, price, total
                FROM order_items
                WHERE order_id = ?
                ORDER BY id
                """,
                (order_id,),
            ).fetchall()

            product_ids = sorted({item["product_id"] for item in items if item["product_id"] is not None})
            products = []
            if product_ids:
                placeholders = ",".join("?" for _ in product_ids)
                product_rows = conn.execute(
                    f"""
                    SELECT id, name, category, price_wholesale, price_retail,
                           stock_qty, sort_order, stock, last_cost_price
                    FROM products
                    WHERE id IN ({placeholders})
                    ORDER BY id
                    """,
                    product_ids,
                ).fetchall()
                products = [self._map_product_row(row) for row in product_rows]

            client = conn.execute(
                "SELECT id, name, phone, type, balance, notes FROM clients WHERE id = ?",
                (order["client_id"],),
            ).fetchone()

            return {
                "client": {
                    "client_id": client["id"],
                    "name": client["name"] or "",
                    "phone": client["phone"] or "",
                    "type": client["type"] or "",
                    "balance": client["balance"] if client["balance"] is not None else "",
                    "notes": client["notes"] or "",
                } if client else None,
                "order": {
                    "order_id": order["id"],
                    "client_id": order["client_id"] or "",
                    "client_name": order["client_name"] or "",
                    "total_amount": order["total_amount"] if order["total_amount"] is not None else "",
                    "status": order["status"] or "",
                    "date": order["date"] or "",
                    "notes": order["notes"] or "",
                    "local_image_path": order["local_image_path"] or "",
                },
                "products": products,
                "items": [
                    {
                        "order_item_id": item["id"],
                        "order_id": item["order_id"],
                        "product_id": item["product_id"] if item["product_id"] is not None else "",
                        "product_name": item["product_name"] or "",
                        "qty": item["qty"] if item["qty"] is not None else "",
                        "price": item["price"] if item["price"] is not None else "",
                        "total": item["total"] if item["total"] is not None else "",
                    }
                    for item in items
                ],
            }
        finally:
            conn.close()

    def _fetch_all_rows(self):
        conn = self._get_db_connection()
        try:
            clients = conn.execute(
                "SELECT id, name, phone, type, balance, notes FROM clients ORDER BY id"
            ).fetchall()
            products = conn.execute(
                """
                SELECT id, name, category, price_wholesale, price_retail,
                       stock_qty, sort_order, stock, last_cost_price
                FROM products
                ORDER BY sort_order ASC, name ASC
                """
            ).fetchall()
            orders = conn.execute(
                """
                SELECT o.id, o.client_id, c.name AS client_name, o.total_amount, o.status,
                       o.date, o.notes, o.local_image_path
                FROM orders o
                LEFT JOIN clients c ON c.id = o.client_id
                ORDER BY o.id
                """
            ).fetchall()
            items = conn.execute(
                """
                SELECT id, order_id, product_id, product_name, qty, price, total
                FROM order_items
                ORDER BY id
                """
            ).fetchall()
        finally:
            conn.close()

        return {
            "clients": [
                {
                    "client_id": row["id"],
                    "name": row["name"] or "",
                    "phone": row["phone"] or "",
                    "type": row["type"] or "",
                    "balance": row["balance"] if row["balance"] is not None else "",
                    "notes": row["notes"] or "",
                }
                for row in clients
            ],
            "products": [self._map_product_row(row) for row in products],
            "orders": [
                {
                    "order_id": row["id"],
                    "client_id": row["client_id"] or "",
                    "client_name": row["client_name"] or "",
                    "total_amount": row["total_amount"] if row["total_amount"] is not None else "",
                    "status": row["status"] or "",
                    "date": row["date"] or "",
                    "notes": row["notes"] or "",
                    "local_image_path": row["local_image_path"] or "",
                }
                for row in orders
            ],
            "order_items": [
                {
                    "order_item_id": row["id"],
                    "order_id": row["order_id"],
                    "product_id": row["product_id"] if row["product_id"] is not None else "",
                    "product_name": row["product_name"] or "",
                    "qty": row["qty"] if row["qty"] is not None else "",
                    "price": row["price"] if row["price"] is not None else "",
                    "total": row["total"] if row["total"] is not None else "",
                }
                for row in items
            ],
        }

    def dry_run_summary(self):
        rows = self._fetch_all_rows()
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "tabs": self.tabs,
            "counts": {
                "clients": len(rows["clients"]),
                "products": len(rows["products"]),
                "orders": len(rows["orders"]),
                "order_items": len(rows["order_items"]),
            },
            "sample_ids": {
                "clients": [row["client_id"] for row in rows["clients"][:5]],
                "products": [row["product_id"] for row in rows["products"][:5]],
                "orders": [row["order_id"] for row in rows["orders"][:5]],
                "order_items": [row["order_item_id"] for row in rows["order_items"][:5]],
            },
        }

    def sync_order_bundle(self, order_id):
        payload = self._fetch_order_bundle(order_id)
        if not payload:
            raise RuntimeError(f"Order #{order_id} not found for Google Sheet sync.")

        self.ensure_ready()
        client_inserts, client_updates = self._upsert_rows("clients", [payload["client"]] if payload["client"] else [])
        product_inserts, product_updates = self._upsert_rows("products", payload["products"])
        order_inserts, order_updates = self._upsert_rows("orders", [payload["order"]])
        item_inserts, item_updates = self._upsert_rows("order_items", payload["items"])

        summary = (
            f"Realtime sync order #{order_id}: "
            f"clients +{client_inserts}/~{client_updates}, "
            f"products +{product_inserts}/~{product_updates}, "
            f"orders +{order_inserts}/~{order_updates}, "
            f"items +{item_inserts}/~{item_updates}"
        )
        log_local("info", summary)
        self._append_sync_log("INFO", "order", order_id, "realtime_sync", summary)
        return {
            "success": True,
            "order_id": order_id,
            "clients": {"inserted": client_inserts, "updated": client_updates},
            "products": {"inserted": product_inserts, "updated": product_updates},
            "orders": {"inserted": order_inserts, "updated": order_updates},
            "order_items": {"inserted": item_inserts, "updated": item_updates},
        }

    def sync_all_once(self):
        rows = self._fetch_all_rows()
        self.ensure_ready()

        clients_result = self._upsert_rows("clients", rows["clients"])
        products_result = self._upsert_rows("products", rows["products"])
        orders_result = self._upsert_rows("orders", rows["orders"])
        items_result = self._upsert_rows("order_items", rows["order_items"])

        summary = {
            "success": True,
            "spreadsheet_id": self.spreadsheet_id,
            "clients": {"inserted": clients_result[0], "updated": clients_result[1]},
            "products": {"inserted": products_result[0], "updated": products_result[1]},
            "orders": {"inserted": orders_result[0], "updated": orders_result[1]},
            "order_items": {"inserted": items_result[0], "updated": items_result[1]},
        }
        log_local("info", f"Manual sync completed: {summary}")
        self._append_sync_log("INFO", "all", "bulk", "manual_once", json.dumps(summary, ensure_ascii=False))
        return summary


def _safe_sync_order(order_id):
    with _SYNC_LOCK:
        try:
            syncer = POSGoogleSheetSync(dry_run=False)
            if not syncer.is_enabled():
                log_local("warning", f"Skipped realtime sync for order #{order_id}: sync disabled.")
                return
            syncer.sync_order_bundle(order_id)
        except Exception as exc:
            log_local("error", f"Realtime sync failed for order #{order_id}: {exc}")


def schedule_order_sync(order_id):
    worker = threading.Thread(target=_safe_sync_order, args=(order_id,), daemon=True, name=f"sheet-sync-{order_id}")
    worker.start()
