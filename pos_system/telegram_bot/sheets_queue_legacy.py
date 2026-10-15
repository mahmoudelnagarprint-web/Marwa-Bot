from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build
from google.oauth2 import service_account

from config import ROOT_DIR, TelegramBotSettings


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CAIRO_TZ = ZoneInfo("Africa/Cairo")
QUEUE_STATUS_PENDING = "pending"
IMAGE_STATUS_PENDING = "pending"
SOURCE_NAME = "telegram"
DEFAULT_PAYMENT_METHOD = "Telegram"
MAX_CLIENT_RESULTS = 10
MAX_PRODUCT_RESULTS = 20
MAX_ORDER_RESULTS = 15
DEFAULT_LOW_STOCK_LIMIT = 0

STATUS_GROUPS = {
    "under_preparation": {"under preparation", "جاري التجهيز", "جارى التجهيز"},
    "ready": {"ready", "جاهز", "جاهزه", "جاهزة"},
    "delivery": {"delivery", "out for delivery", "جاري التسليم", "جارى التسليم"},
    "delivered": {"delivered", "تم التنفيذ", "تم التسليم"},
}

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
    "telegram_inbox": [
        "queue_id",
        "source",
        "chat_id",
        "message_id",
        "external_order_id",
        "received_at",
        "client_name",
        "client_phone",
        "client_type",
        "notes",
        "payment_method",
        "paid_amount",
        "discount",
        "total_amount",
        "remaining_amount",
        "status",
        "items_json",
        "imported_order_id",
        "error_message",
    ],
    "telegram_images": [
        "image_row_id",
        "external_order_id",
        "message_id",
        "item_index",
        "telegram_file_id",
        "original_name",
        "mime_type",
        "caption",
        "import_status",
        "local_saved_path",
    ],
    "telegram_payments_queue": [
        "payment_queue_id",
        "source",
        "chat_id",
        "message_id",
        "external_payment_id",
        "received_at",
        "client_id",
        "client_name",
        "client_phone",
        "amount",
        "payment_method",
        "notes",
        "status",
        "imported_transaction_id",
        "error_message",
    ],
    "telegram_admin_actions_queue": [
        "admin_action_queue_id",
        "source",
        "chat_id",
        "message_id",
        "external_action_id",
        "received_at",
        "action_type",
        "target_scope",
        "payload_json",
        "notes",
        "status",
        "imported_ref",
        "error_message",
    ],
}


@dataclass
class ParsedItem:
    product_id: str
    product_name: str
    qty: float
    unit_price: float
    total: float
    item_index: int
    matched_existing_product: bool
    needs_review: bool
    price_source: str
    explicit_price: float | None

    def as_json(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "qty": self.qty,
            "price": self.unit_price,
            "total": self.total,
            "item_index": self.item_index,
            "matched_existing_product": self.matched_existing_product,
            "needs_review": self.needs_review,
            "price_source": self.price_source,
            "explicit_price": self.explicit_price,
        }


class TelegramSheetsQueue:
    def __init__(self, settings: TelegramBotSettings):
        self.settings = settings
        self.spreadsheet_id = settings.google_sheet_id
        self.sheets_service = None
        self._sheet_titles: set[str] = set()
        self._tab_cache: Dict[str, List[List[str]]] = {}
        self._headers_checked = False

    def authenticate(self) -> None:
        credentials_file = ROOT_DIR / "credentials.json"
        if not credentials_file.exists():
            raise RuntimeError(f"Missing Google credentials file: {credentials_file}")
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_file),
            scopes=SCOPES,
        )
        self.sheets_service = build("sheets", "v4", credentials=credentials)

    def ensure_read_ready(self) -> None:
        if self.sheets_service is None:
            self.authenticate()

    def ensure_ready(self) -> None:
        self.ensure_read_ready()
        self._ensure_tabs_exist()
        self._ensure_headers()

    def _ensure_tabs_exist(self) -> None:
        meta = self.sheets_service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        self._sheet_titles = {sheet["properties"]["title"] for sheet in meta.get("sheets", [])}
        requests = []
        for tab_name in TAB_HEADERS:
            if tab_name not in self._sheet_titles:
                requests.append({"addSheet": {"properties": {"title": tab_name}}})
                self._sheet_titles.add(tab_name)
        if requests:
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()

    def _ensure_headers(self) -> None:
        if self._headers_checked:
            return
        for tab_name, headers in TAB_HEADERS.items():
            first_row = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab_name}!1:1",
            ).execute()
            values = first_row.get("values", [])
            if not values or not any(str(cell).strip() for cell in values[0]):
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{tab_name}!A1",
                    valueInputOption="RAW",
                    body={"values": [headers]},
                ).execute()
        self._headers_checked = True

    def _get_tab_values(self, tab_name: str, force_refresh: bool = False) -> List[List[str]]:
        self.ensure_read_ready()
        if not force_refresh and tab_name in self._tab_cache:
            return self._tab_cache[tab_name]
        response = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab_name}!A:Z",
        ).execute()
        values = response.get("values", [])
        self._tab_cache[tab_name] = values
        return values

    def invalidate_cache(self, tab_name: str | None = None) -> None:
        if tab_name is None:
            self._tab_cache.clear()
            return
        self._tab_cache.pop(tab_name, None)

    def read_rows(self, tab_name: str, force_refresh: bool = False) -> List[Dict[str, str]]:
        values = self._get_tab_values(tab_name, force_refresh=force_refresh)
        headers = TAB_HEADERS.get(tab_name, [])
        if not values:
            return []

        raw_headers = values[0]
        effective_headers = raw_headers if raw_headers else headers
        rows = []
        for raw_row in values[1:]:
            row_map = {}
            for index, header in enumerate(effective_headers):
                row_map[header] = raw_row[index] if index < len(raw_row) else ""
            rows.append(row_map)
        return rows

    def append_row(self, tab_name: str, row: Dict[str, Any]) -> None:
        self.ensure_ready()
        headers = TAB_HEADERS[tab_name]
        values = [[row.get(header, "") for header in headers]]
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab_name}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        ).execute()
        self.invalidate_cache(tab_name)

    def search_clients(self, query: str, limit: int = MAX_CLIENT_RESULTS) -> List[Dict[str, str]]:
        normalized = self.normalize_text(query)
        phone_query = self.normalize_phone(query)
        rows = self.read_rows("clients")
        if not normalized and not phone_query:
            return rows[:limit]

        scored = []
        for row in rows:
            name_value = row.get("name", "")
            phone_value = row.get("phone", "")
            score = max(
                self._score_text_match(normalized, self.normalize_text(name_value)),
                self._score_phone_match(phone_query, self.normalize_phone(phone_value)),
            )
            if score >= 0.45:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
        return [row for _score, row in scored[:limit]]

    def search_products(self, query: str = "", limit: int = MAX_PRODUCT_RESULTS) -> List[Dict[str, str]]:
        matches = self.find_product_candidates(query, limit=limit)
        return [item["row"] for item in matches]

    def find_product_candidates(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        normalized = self.normalize_text(query)
        rows = self.read_rows("products")
        if not normalized:
            return [{"row": row, "score": 1.0} for row in rows[:limit]]

        scored = []
        for row in rows:
            score = self._score_text_match(normalized, self.normalize_text(row.get("name", "")))
            if score >= 0.45:
                scored.append({"row": row, "score": round(score, 4)})
        scored.sort(key=lambda item: (-item["score"], item["row"].get("name", "")))
        return scored[:limit]

    def search_orders(self, query: str, limit: int = MAX_ORDER_RESULTS) -> List[Dict[str, str]]:
        normalized = self.normalize_text(query)
        rows = self.read_rows("orders")
        results = []
        for row in rows:
            haystacks = [
                self.normalize_text(row.get("client_name", "")),
                self.normalize_text(row.get("notes", "")),
                self.normalize_text(row.get("order_id", "")),
            ]
            best_score = max((self._score_text_match(normalized, hay) for hay in haystacks), default=0.0)
            if best_score >= 0.45:
                results.append((best_score, row))
        results.sort(key=lambda item: (-item[0], self._safe_int(item[1].get("order_id", "0")) * -1))
        return [row for _score, row in results[:limit]]

    def list_orders_for_today(self) -> List[Dict[str, str]]:
        today = datetime.now(CAIRO_TZ).date()
        rows = self.read_rows("orders")
        matches = []
        for row in rows:
            row_date = self.parse_sheet_date(row.get("date", ""))
            if row_date and row_date.date() == today:
                matches.append(row)
        return self._sort_orders_desc(matches)

    def list_orders_by_status_group(self, group_name: str, limit: int = MAX_ORDER_RESULTS) -> List[Dict[str, str]]:
        rows = self.read_rows("orders")
        target_statuses = {self.normalize_status(value) for value in STATUS_GROUPS.get(group_name, set())}
        matches = []
        for row in rows:
            if self.normalize_status(row.get("status", "")) in target_statuses:
                matches.append(row)
        return self._sort_orders_desc(matches)[:limit]

    def list_recent_orders(self, limit: int = 10) -> List[Dict[str, str]]:
        return self._sort_orders_desc(self.read_rows("orders"))[:limit]

    def list_recent_clients(self, limit: int = 10) -> List[Dict[str, str]]:
        rows = self.read_rows("clients")
        rows.sort(key=lambda row: self._safe_int(row.get("client_id", "0")), reverse=True)
        return rows[:limit]

    def list_telegram_inbox(self, statuses: Sequence[str] | None = None, limit: int = 10) -> List[Dict[str, str]]:
        rows = self.read_rows("telegram_inbox")
        if statuses:
            normalized_statuses = {self.normalize_status(status) for status in statuses}
            rows = [row for row in rows if self.normalize_status(row.get("status", "")) in normalized_statuses]
        rows.sort(
            key=lambda row: (
                row.get("received_at", ""),
                self._safe_int(row.get("message_id", "0")),
            ),
            reverse=True,
        )
        return rows[:limit]

    def list_payment_queue(self, statuses: Sequence[str] | None = None, limit: int = 10) -> List[Dict[str, str]]:
        rows = self.read_rows("telegram_payments_queue")
        if statuses:
            normalized_statuses = {self.normalize_status(status) for status in statuses}
            rows = [row for row in rows if self.normalize_status(row.get("status", "")) in normalized_statuses]
        rows.sort(key=lambda row: row.get("received_at", ""), reverse=True)
        return rows[:limit]

    def list_admin_actions_queue(self, statuses: Sequence[str] | None = None, limit: int = 10) -> List[Dict[str, str]]:
        rows = self.read_rows("telegram_admin_actions_queue")
        if statuses:
            normalized_statuses = {self.normalize_status(status) for status in statuses}
            rows = [row for row in rows if self.normalize_status(row.get("status", "")) in normalized_statuses]
        rows.sort(key=lambda row: row.get("received_at", ""), reverse=True)
        return rows[:limit]

    def get_order_by_id(self, order_id: int | str) -> Dict[str, str] | None:
        order_id_text = str(order_id).strip()
        for row in self.read_rows("orders"):
            if row.get("order_id", "").strip() == order_id_text:
                return row
        return None

    def get_order_items(self, order_id: int | str) -> List[Dict[str, str]]:
        order_id_text = str(order_id).strip()
        rows = [row for row in self.read_rows("order_items") if row.get("order_id", "").strip() == order_id_text]
        rows.sort(key=lambda row: self._safe_int(row.get("order_item_id", "0")))
        return rows

    def get_order_details(self, order_id: int | str) -> Dict[str, Any] | None:
        order_row = self.get_order_by_id(order_id)
        if order_row is None:
            return None
        items = self.get_order_items(order_id)
        return {
            "order": order_row,
            "items": items,
        }

    def get_last_sync_log(self) -> Dict[str, str] | None:
        rows = self.read_rows("sync_log")
        if not rows:
            return None
        rows.sort(key=lambda row: row.get("timestamp", ""), reverse=True)
        return rows[0]

    def get_client_summary(self, query: str) -> Dict[str, Any] | None:
        rows = self.search_clients(query, limit=5)
        if not rows:
            return None
        client = rows[0]
        return {
            "client": client,
            "matches": rows,
        }

    def get_accounts_summary(self) -> Dict[str, Any]:
        orders = self.read_rows("orders")
        clients = self.read_rows("clients")
        products = self.read_rows("products")
        pending_inbox = self.list_telegram_inbox(statuses=["pending"], limit=1000)
        today_orders = self.list_orders_for_today()

        def group_totals(group_name: str) -> Dict[str, float]:
            matched = self.list_orders_by_status_group(group_name, limit=1000)
            total_value = round(sum(self.parse_money(row.get("total_amount", 0)) or 0 for row in matched), 2)
            return {
                "count": len(matched),
                "total": total_value,
            }

        under_preparation = group_totals("under_preparation")
        delivery = group_totals("delivery")
        delivered = group_totals("delivered")
        today_total = round(sum(self.parse_money(row.get("total_amount", 0)) or 0 for row in today_orders), 2)
        total_balance = round(sum(self.parse_money(row.get("balance", 0)) or 0 for row in clients), 2)
        top_debts = sorted(
            clients,
            key=lambda row: self.parse_money(row.get("balance", 0)) or 0,
            reverse=True,
        )
        top_debts = [row for row in top_debts if (self.parse_money(row.get("balance", 0)) or 0) > 0][:10]
        low_stock = self.list_low_stock_products(limit=50, threshold=0)
        return {
            "under_preparation": under_preparation,
            "delivery": delivery,
            "delivered": delivered,
            "today_orders_count": len(today_orders),
            "today_orders_total": today_total,
            "pending_inbox_count": len(pending_inbox),
            "clients_count": len(clients),
            "products_count": len(products),
            "total_client_balance": total_balance,
            "top_debt_clients": top_debts,
            "low_stock_count": len(low_stock),
            "low_stock_products": low_stock[:10],
        }

    def get_telegram_sync_status_summary(self) -> Dict[str, Any]:
        pending_rows = self.list_telegram_inbox(statuses=["pending"], limit=50)
        failed_rows = self.list_telegram_inbox(statuses=["failed"], limit=20)
        imported_rows = self.list_telegram_inbox(statuses=["imported"], limit=20)
        recent_rows = self.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=20)
        last_sync_log = self.get_last_sync_log()

        status_code = "complete"
        status_text = "✅ المزامنة مكتملة"
        if failed_rows:
            status_code = "failed"
            status_text = "❌ فشل آخر استيراد"
        elif pending_rows:
            status_code = "pending"
            status_text = "⏳ يوجد طلبات تليجرام منتظرة"

        last_event_at = ""
        if recent_rows:
            last_event_at = recent_rows[0].get("received_at", "")
        if last_sync_log and last_sync_log.get("timestamp", "") > last_event_at:
            last_event_at = last_sync_log.get("timestamp", "")

        last_error = ""
        if failed_rows:
            last_error = failed_rows[0].get("error_message", "")
        elif last_sync_log and self.normalize_status(last_sync_log.get("level", "")) in {"error", "failed"}:
            last_error = last_sync_log.get("message", "")

        return {
            "status_code": status_code,
            "status_text": status_text,
            "pending_count": len(pending_rows),
            "failed_count": len(failed_rows),
            "imported_count": len(imported_rows),
            "last_event_at": last_event_at,
            "last_error": last_error,
            "pending_rows": pending_rows[:10],
            "failed_rows": failed_rows[:10],
            "recent_rows": recent_rows[:10],
            "last_sync_log": last_sync_log or {},
        }

    def search_order_items(self, query: str, limit: int = MAX_ORDER_RESULTS) -> List[Dict[str, str]]:
        normalized = self.normalize_text(query)
        rows = self.read_rows("order_items")
        if not normalized:
            return rows[:limit]
        scored = []
        for row in rows:
            haystacks = [
                self.normalize_text(row.get("product_name", "")),
                self.normalize_text(row.get("order_id", "")),
            ]
            best_score = max((self._score_text_match(normalized, hay) for hay in haystacks), default=0.0)
            if best_score >= 0.45:
                scored.append((best_score, row))
        scored.sort(key=lambda item: (-item[0], self._safe_int(item[1].get("order_item_id", "0")) * -1))
        return [row for _score, row in scored[:limit]]

    def search_telegram_inbox(self, query: str, limit: int = MAX_ORDER_RESULTS) -> List[Dict[str, str]]:
        normalized = self.normalize_text(query)
        rows = self.read_rows("telegram_inbox")
        if not normalized:
            return rows[:limit]
        scored = []
        for row in rows:
            haystacks = [
                self.normalize_text(row.get("client_name", "")),
                self.normalize_text(row.get("notes", "")),
                self.normalize_text(row.get("external_order_id", "")),
            ]
            best_score = max((self._score_text_match(normalized, hay) for hay in haystacks), default=0.0)
            if best_score >= 0.45:
                scored.append((best_score, row))
        scored.sort(key=lambda item: (-item[0], item[1].get("received_at", "")), reverse=False)
        return [row for _score, row in scored[:limit]]

    def partial_search_everywhere(self, query: str, limit_per_section: int = 5) -> Dict[str, List[Dict[str, str]]]:
        return {
            "clients": self.search_clients(query, limit=limit_per_section),
            "products": self.search_products(query, limit=limit_per_section),
            "orders": self.search_orders(query, limit=limit_per_section),
            "order_items": self.search_order_items(query, limit=limit_per_section),
            "telegram_inbox": self.search_telegram_inbox(query, limit=limit_per_section),
        }

    def list_low_stock_products(self, limit: int = 20, threshold: int = DEFAULT_LOW_STOCK_LIMIT) -> List[Dict[str, str]]:
        rows = self.read_rows("products")
        matches = []
        for row in rows:
            stock_value = self.parse_money(row.get("stock_qty", 0)) or 0
            if stock_value <= threshold:
                matches.append(row)
        matches.sort(key=lambda row: self.parse_money(row.get("stock_qty", 0)) or 0)
        return matches[:limit]

    def parse_items_text(self, items_text: str, client_type: str) -> Dict[str, Any]:
        catalog = self.read_rows("products")
        parsed_items: List[ParsedItem] = []
        needs_review = False

        for index, raw_line in enumerate(items_text.splitlines()):
            line = raw_line.strip()
            if not line:
                continue
            parsed = self._parse_single_item(line, client_type=client_type, catalog=catalog, item_index=index)
            parsed_items.append(parsed)
            needs_review = needs_review or parsed.needs_review

        if not parsed_items:
            raise ValueError("At least one product line is required.")

        total_amount = round(sum(item.total for item in parsed_items), 2)
        return {
            "items": [item.as_json() for item in parsed_items],
            "total_amount": total_amount,
            "needs_review": needs_review,
        }

    def _parse_single_item(
        self,
        line: str,
        client_type: str,
        catalog: Sequence[Dict[str, str]],
        item_index: int,
    ) -> ParsedItem:
        explicit_price = None
        working_line = line

        if "@" in working_line:
            working_line, raw_price = working_line.rsplit("@", 1)
            explicit_price = self.parse_money(raw_price.strip())
            if explicit_price is None:
                raise ValueError(f"Invalid explicit price in line: {line}")

        match = re.match(r"^(?P<name>.+?)\s*(?:x|\*)\s*(?P<qty>[0-9]+(?:[.,][0-9]+)?)$", working_line.strip(), re.IGNORECASE)
        if not match:
            raise ValueError(
                "Invalid item format. Use one product per line like 'Product Name x 2' or 'Product Name x 2 @ 150'."
            )

        product_name = match.group("name").strip()
        qty = self.parse_money(match.group("qty"))
        if qty is None or qty <= 0:
            raise ValueError(f"Invalid quantity in line: {line}")

        product_row = self._find_product_by_name(product_name, catalog)
        if product_row:
            unit_price = self._pick_price_from_product(product_row, client_type, explicit_price)
            price_source = "sheet_product_price" if explicit_price is None else "user_override"
            needs_review = False
            if unit_price in (None, 0) and explicit_price is not None:
                unit_price = explicit_price
                needs_review = True
                price_source = "user_override_missing_sheet_price"
            if unit_price is None:
                unit_price = explicit_price if explicit_price is not None else 0.0
                needs_review = True
                price_source = "missing_sheet_price"
            return ParsedItem(
                product_id=str(product_row.get("product_id", "")),
                product_name=product_row.get("name", product_name),
                qty=qty,
                unit_price=round(unit_price, 2),
                total=round(qty * unit_price, 2),
                item_index=item_index,
                matched_existing_product=True,
                needs_review=needs_review,
                price_source=price_source,
                explicit_price=explicit_price,
            )

        unit_price = explicit_price if explicit_price is not None else 0.0
        return ParsedItem(
            product_id="",
            product_name=product_name,
            qty=qty,
            unit_price=round(unit_price, 2),
            total=round(qty * unit_price, 2),
            item_index=item_index,
            matched_existing_product=False,
            needs_review=True,
            price_source="user_supplied_unknown_product" if explicit_price is not None else "unknown_product_missing_price",
            explicit_price=explicit_price,
        )

    def _find_product_by_name(self, product_name: str, catalog: Sequence[Dict[str, str]]) -> Dict[str, str] | None:
        normalized = self.normalize_text(product_name)
        candidates: List[tuple[float, Dict[str, str]]] = []
        for row in catalog:
            row_normalized = self.normalize_text(row.get("name", ""))
            score = self._score_text_match(normalized, row_normalized)
            if score >= 0.45:
                candidates.append((score, row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1].get("name", "")))
        return candidates[0][1]

    def _pick_price_from_product(self, product_row: Dict[str, str], client_type: str, explicit_price: float | None) -> float | None:
        preferred_key = "wholesale_price" if client_type == "Wholesale" else "retail_price"
        preferred_price = self.parse_money(product_row.get(preferred_key, ""))
        if preferred_price is not None and preferred_price > 0:
            return preferred_price
        if explicit_price is not None:
            return explicit_price
        return None

    def queue_order(
        self,
        chat_id: int,
        root_message_id: int,
        client_name: str,
        client_phone: str,
        client_type: str,
        items: Sequence[Dict[str, Any]],
        paid_amount: float,
        notes: str,
        images: Sequence[Dict[str, Any]],
        discount: float = 0.0,
    ) -> Dict[str, Any]:
        self.ensure_ready()

        external_order_id = self.build_external_order_id(chat_id=chat_id, message_id=root_message_id)
        if self.external_order_exists(external_order_id):
            return {
                "success": False,
                "duplicate": True,
                "external_order_id": external_order_id,
                "message": "Duplicate external_order_id blocked.",
            }

        total_amount = round(sum(self.parse_money(item.get("total", 0)) or 0 for item in items), 2)
        remaining_amount = round(total_amount - discount - paid_amount, 2)
        received_at = self.now_iso()
        needs_review = any(bool(item.get("needs_review")) for item in items)
        items_payload = {
            "needs_review": needs_review,
            "pricing_mode": "wholesale_price" if client_type == "Wholesale" else "retail_price",
            "items": list(items),
        }

        inbox_row = {
            "queue_id": self.make_queue_id(chat_id, root_message_id),
            "source": SOURCE_NAME,
            "chat_id": str(chat_id),
            "message_id": str(root_message_id),
            "external_order_id": external_order_id,
            "received_at": received_at,
            "client_name": client_name,
            "client_phone": client_phone,
            "client_type": client_type,
            "notes": notes,
            "payment_method": DEFAULT_PAYMENT_METHOD,
            "paid_amount": self.format_number(paid_amount),
            "discount": self.format_number(discount),
            "total_amount": self.format_number(total_amount),
            "remaining_amount": self.format_number(remaining_amount),
            "status": QUEUE_STATUS_PENDING,
            "items_json": json.dumps(items_payload, ensure_ascii=False),
            "imported_order_id": "",
            "error_message": "needs_review=true" if needs_review else "",
        }
        self.append_row("telegram_inbox", inbox_row)

        for image in images:
            self.append_telegram_image(external_order_id, image)

        return {
            "success": True,
            "duplicate": False,
            "external_order_id": external_order_id,
            "queue_id": inbox_row["queue_id"],
            "received_at": received_at,
            "needs_review": needs_review,
            "total_amount": total_amount,
            "remaining_amount": remaining_amount,
            "images_count": len(images),
        }

    def payment_exists(self, external_payment_id: str) -> bool:
        for row in self.read_rows("telegram_payments_queue"):
            if row.get("external_payment_id", "").strip() == external_payment_id:
                return True
        return False

    def queue_payment(
        self,
        chat_id: int,
        message_id: int,
        client_id: str,
        client_name: str,
        client_phone: str,
        amount: float,
        payment_method: str,
        notes: str,
    ) -> Dict[str, Any]:
        self.ensure_ready()
        external_payment_id = f"tgp-{chat_id}-{message_id}"
        if self.payment_exists(external_payment_id):
            return {"success": False, "duplicate": True, "external_payment_id": external_payment_id}
        row = {
            "payment_queue_id": f"pq-{chat_id}-{message_id}",
            "source": SOURCE_NAME,
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "external_payment_id": external_payment_id,
            "received_at": self.now_iso(),
            "client_id": str(client_id or ""),
            "client_name": client_name,
            "client_phone": client_phone,
            "amount": self.format_number(amount),
            "payment_method": payment_method or DEFAULT_PAYMENT_METHOD,
            "notes": notes,
            "status": QUEUE_STATUS_PENDING,
            "imported_transaction_id": "",
            "error_message": "",
        }
        self.append_row("telegram_payments_queue", row)
        return {"success": True, "duplicate": False, "external_payment_id": external_payment_id, "payment_queue_id": row["payment_queue_id"]}

    def admin_action_exists(self, external_action_id: str) -> bool:
        for row in self.read_rows("telegram_admin_actions_queue"):
            if row.get("external_action_id", "").strip() == external_action_id:
                return True
        return False

    def queue_admin_action(
        self,
        chat_id: int,
        message_id: int,
        action_type: str,
        target_scope: str,
        payload: Dict[str, Any],
        notes: str,
    ) -> Dict[str, Any]:
        self.ensure_ready()
        external_action_id = f"tga-{chat_id}-{message_id}"
        if self.admin_action_exists(external_action_id):
            return {"success": False, "duplicate": True, "external_action_id": external_action_id}
        row = {
            "admin_action_queue_id": f"aq-{chat_id}-{message_id}",
            "source": SOURCE_NAME,
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "external_action_id": external_action_id,
            "received_at": self.now_iso(),
            "action_type": action_type,
            "target_scope": target_scope,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "notes": notes,
            "status": QUEUE_STATUS_PENDING,
            "imported_ref": "",
            "error_message": "",
        }
        self.append_row("telegram_admin_actions_queue", row)
        return {"success": True, "duplicate": False, "external_action_id": external_action_id, "admin_action_queue_id": row["admin_action_queue_id"]}

    def external_order_exists(self, external_order_id: str) -> bool:
        rows = self.read_rows("telegram_inbox")
        for row in rows:
            if row.get("external_order_id", "").strip() == external_order_id:
                return True
        return False

    def build_external_order_id(self, chat_id: int, message_id: int | None = None) -> str:
        if message_id is not None:
            return f"tg-{chat_id}-{message_id}"
        return f"tg-{chat_id}-{int(datetime.now(CAIRO_TZ).timestamp())}"

    def make_queue_id(self, chat_id: int, message_id: int) -> str:
        return f"q-{chat_id}-{message_id}"

    def make_image_row_id(self, external_order_id: str, message_id: Any) -> str:
        suffix = str(message_id or int(datetime.now(CAIRO_TZ).timestamp()))
        return f"img-{external_order_id}-{suffix}"

    def telegram_image_exists(self, external_order_id: str, message_id: Any) -> bool:
        message_id_text = str(message_id or "").strip()
        for row in self.read_rows("telegram_images"):
            if (
                row.get("external_order_id", "").strip() == external_order_id
                and row.get("message_id", "").strip() == message_id_text
            ):
                return True
        return False

    def append_telegram_image(self, external_order_id: str, image: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_ready()
        message_id = image.get("message_id", "")
        if self.telegram_image_exists(external_order_id, message_id):
            return {
                "success": False,
                "duplicate": True,
                "external_order_id": external_order_id,
                "message_id": str(message_id),
            }

        image_row = {
            "image_row_id": self.make_image_row_id(external_order_id, message_id),
            "external_order_id": external_order_id,
            "message_id": str(message_id),
            "item_index": str(image.get("item_index", "")),
            "telegram_file_id": image.get("telegram_file_id", ""),
            "original_name": image.get("original_name", ""),
            "mime_type": image.get("mime_type", ""),
            "caption": image.get("caption", ""),
            "import_status": IMAGE_STATUS_PENDING,
            "local_saved_path": "",
        }
        self.append_row("telegram_images", image_row)
        return {
            "success": True,
            "duplicate": False,
            "external_order_id": external_order_id,
            "message_id": str(message_id),
            "image_row_id": image_row["image_row_id"],
        }

    def healthcheck(self) -> Dict[str, Any]:
        self.ensure_read_ready()
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "tabs_checked": list(TAB_HEADERS.keys()),
            "clients_count": len(self.read_rows("clients")),
            "products_count": len(self.read_rows("products")),
            "orders_count": len(self.read_rows("orders")),
            "telegram_inbox_count": len(self.read_rows("telegram_inbox")),
            "telegram_images_count": len(self.read_rows("telegram_images")),
        }

    @staticmethod
    def normalize_text(value: str) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = unicodedata.normalize("NFKD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        text = text.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
        text = re.sub(r"(?<=\d)\s*[x×*ف]\s*(?=\d)", "x", text, flags=re.IGNORECASE)
        text = text.replace("،", " ").replace(",", " ")
        text = re.sub(r"[^\w\s@./+-]", " ", text)
        text = re.sub(r"_", " ", text)
        return " ".join(text.split())

    @staticmethod
    def normalize_phone(value: str) -> str:
        return re.sub(r"\D+", "", value or "")

    @staticmethod
    def normalize_status(value: str) -> str:
        return TelegramSheetsQueue.normalize_text(value)

    @staticmethod
    def parse_money(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        translation_table = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")
        cleaned = str(value).strip().translate(translation_table).replace(",", ".")
        cleaned = cleaned.replace("..", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def format_number(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(CAIRO_TZ).isoformat(timespec="seconds")

    @staticmethod
    def parse_sheet_date(raw_value: str) -> datetime | None:
        if not raw_value:
            return None
        raw_value = raw_value.strip()
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%m/%d/%Y",
            "%d/%m/%Y",
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(raw_value, fmt)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=CAIRO_TZ)
                return parsed.astimezone(CAIRO_TZ)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(raw_value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=CAIRO_TZ)
            return parsed.astimezone(CAIRO_TZ)
        except ValueError:
            return None

    @staticmethod
    def format_clients_for_reply(rows: Iterable[Dict[str, str]]) -> str:
        rows = list(rows)
        if not rows:
            return "مفيش عملاء مطابقين دلوقتي."
        return "\n".join(
            f"- {row.get('name', '')} | موبايل: {row.get('phone', '') or '-'} | النوع: {row.get('type', '') or '-'} | الرصيد: {row.get('balance', '') or '0'}"
            for row in rows
        )

    @staticmethod
    def format_products_for_reply(rows: Iterable[Dict[str, str]], client_type: str = "Retail") -> str:
        rows = list(rows)
        if not rows:
            return "مفيش منتجات مطابقة دلوقتي."
        price_key = "wholesale_price" if client_type == "Wholesale" else "retail_price"
        label = "سعر الجملة" if client_type == "Wholesale" else "سعر القطاعي"
        return "\n".join(
            f"- {row.get('name', '')} | {label}: {row.get(price_key, '') or '0'} | المخزون: {row.get('stock_qty', '') or '0'}"
            for row in rows
        )

    @staticmethod
    def format_orders_for_reply(rows: Iterable[Dict[str, str]]) -> str:
        rows = list(rows)
        if not rows:
            return "مفيش طلبات مطابقة حاليًا."
        return "\n".join(
            f"- طلب #{row.get('order_id', '')} | {row.get('client_name', '')} | الإجمالي: {row.get('total_amount', '') or '0'} | الحالة: {row.get('status', '') or '-'}"
            for row in rows[:15]
        )

    @staticmethod
    def _score_phone_match(query: str, candidate: str) -> float:
        if not query or not candidate:
            return 0.0
        if query == candidate:
            return 1.0
        if query in candidate or candidate in query:
            return 0.85
        return 0.0

    @staticmethod
    def _score_text_match(query: str, candidate: str) -> float:
        if not query or not candidate:
            return 0.0
        compact_query = query.replace(" ", "")
        compact_candidate = candidate.replace(" ", "")
        if query == candidate:
            return 1.0
        if len(compact_query) <= 3 and compact_query not in compact_candidate and compact_candidate not in compact_query:
            return 0.0
        if query in candidate:
            ratio = min(len(query) / max(len(candidate), 1), 1.0)
            return 0.88 + (0.08 * ratio)
        if candidate in query:
            ratio = min(len(candidate) / max(len(query), 1), 1.0)
            return 0.84 + (0.06 * ratio)
        query_tokens = set(query.split())
        candidate_tokens = set(candidate.split())
        intersection = len(query_tokens & candidate_tokens)
        token_score = intersection / max(len(query_tokens | candidate_tokens), 1)
        ratio_score = SequenceMatcher(None, query, candidate).ratio()
        if len(query_tokens) == 1 and len(compact_query) <= 4:
            ratio_score *= 0.65
        return max(ratio_score, token_score * 0.95)

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return 0

    def _sort_orders_desc(self, rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
        return sorted(
            rows,
            key=lambda row: (
                self.parse_sheet_date(row.get("date", "")) or datetime.min.replace(tzinfo=CAIRO_TZ),
                self._safe_int(row.get("order_id", "0")),
            ),
            reverse=True,
        )
