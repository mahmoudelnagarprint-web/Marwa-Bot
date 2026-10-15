from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

ROOT_DIR = Path(__file__).resolve().parent
TELEGRAM_BOT_DIR = ROOT_DIR / "telegram_bot"
if str(TELEGRAM_BOT_DIR) not in sys.path:
    sys.path.insert(0, str(TELEGRAM_BOT_DIR))

from config import load_settings
from sheets_queue import TAB_HEADERS, TelegramSheetsQueue

import database
from file_ops_engine import FileOpsEngine
from google_sheet_realtime_sync import POSGoogleSheetSync


CAIRO_TZ = ZoneInfo("Africa/Cairo")
BACKUP_ROOT = ROOT_DIR / "Backups"


class ImporterError(RuntimeError):
    pass


class ImporterGoogleSheet(TelegramSheetsQueue):
    def __init__(self, settings: Any):
        super().__init__(settings)
        self._import_ready = False

    def ensure_import_ready(self) -> None:
        if not self._import_ready:
            self.ensure_ready()
            self._import_ready = True

    def read_rows_with_index(self, tab_name: str) -> List[Dict[str, str]]:
        self.ensure_import_ready()
        values = self._get_tab_values(tab_name)
        headers = values[0] if values else TAB_HEADERS[tab_name]
        rows: List[Dict[str, str]] = []
        for row_index, raw_row in enumerate(values[1:], start=2):
            row_map: Dict[str, str] = {"_row_index": str(row_index)}
            for idx, header in enumerate(headers):
                row_map[header] = raw_row[idx] if idx < len(raw_row) else ""
            rows.append(row_map)
        return rows

    def update_row_fields(self, tab_name: str, row_index: int, fields: Dict[str, Any]) -> None:
        self.ensure_import_ready()
        rows = self.read_rows_with_index(tab_name)
        row = next((item for item in rows if int(item["_row_index"]) == row_index), None)
        if row is None:
            raise ImporterError(f"Row {row_index} not found in tab {tab_name}")

        headers = TAB_HEADERS[tab_name]
        for key, value in fields.items():
            if key in headers:
                row[key] = "" if value is None else str(value)

        end_column = self._column_letter(len(headers))
        values = [[row.get(header, "") for header in headers]]
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab_name}!A{row_index}:{end_column}{row_index}",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    def get_pending_inbox_rows(self) -> List[Dict[str, str]]:
        rows = self.read_rows_with_index("telegram_inbox")
        pending = []
        for row in rows:
            if row.get("status", "").strip().lower() == "pending":
                pending.append(row)
        return pending

    def get_images_for_external_order(self, external_order_id: str) -> List[Dict[str, str]]:
        rows = self.read_rows_with_index("telegram_images")
        matches = [row for row in rows if row.get("external_order_id", "").strip() == external_order_id]
        matches.sort(key=lambda item: int(item["_row_index"]))
        return matches

    @staticmethod
    def _column_letter(index: int) -> str:
        result = ""
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            result = chr(65 + remainder) + result
        return result


def now_stamp() -> str:
    return datetime.now(CAIRO_TZ).strftime("%Y%m%d_%H%M%S")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Telegram queue rows from Google Sheets into Elnagar POS.")
    parser.add_argument("--dry-run", action="store_true", help="Read pending rows and validate them without writing locally.")
    parser.add_argument("--once", action="store_true", help="Process pending rows one time.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of pending rows to process.")
    return parser.parse_args()


def normalize_phone(phone: str) -> str:
    return re.sub(r"\D+", "", phone or "")


def sanitize_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", str(name or "")).strip()


def get_storage_root() -> str:
    path = database.get_setting("local_images_path")
    if not path or not os.path.exists(path):
        fallback = str(ROOT_DIR / "pos_images")
        os.makedirs(fallback, exist_ok=True)
        return fallback
    return path


def create_safety_backup() -> Path:
    backup_dir = BACKUP_ROOT / f"telegram_importer_{now_stamp()}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_path = ROOT_DIR / "pos_data.db"
    if db_path.exists():
        shutil.copy2(db_path, backup_dir / "pos_data.db")

    pos_images = ROOT_DIR / "pos_images"
    if pos_images.exists():
        shutil.copytree(pos_images, backup_dir / "pos_images", dirs_exist_ok=True)

    laser_images = ROOT_DIR / "web" / "laser_images"
    if laser_images.exists():
        shutil.copytree(laser_images, backup_dir / "web_laser_images", dirs_exist_ok=True)

    return backup_dir


def select_pending_rows(sheet: ImporterGoogleSheet, limit: int | None) -> List[Dict[str, str]]:
    rows = sheet.get_pending_inbox_rows()
    rows.sort(key=lambda item: int(item["_row_index"]))
    if limit is not None:
        rows = rows[:limit]
    return rows


def find_existing_local_order_by_external_id(external_order_id: str) -> int | None:
    conn = database.get_db_connection()
    try:
        row = conn.execute(
            "SELECT id FROM orders WHERE notes LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{external_order_id}%",),
        ).fetchone()
        return int(row["id"]) if row else None
    finally:
        conn.close()


def resolve_client_id(client_name: str, client_phone: str, client_type: str, allow_create: bool = True) -> int | None:
    normalized_phone = normalize_phone(client_phone)
    conn = database.get_db_connection()
    try:
        row = None
        if normalized_phone:
            row = conn.execute(
                """
                SELECT id FROM clients
                WHERE REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(COALESCE(phone, ''), ' ', ''), '+', ''), '-', ''), '(', ''), ')', '') = ?
                ORDER BY id ASC LIMIT 1
                """,
                (normalized_phone,),
            ).fetchone()
        if not row and client_name.strip():
            row = conn.execute(
                "SELECT id FROM clients WHERE name = ? COLLATE NOCASE ORDER BY id ASC LIMIT 1",
                (client_name.strip(),),
            ).fetchone()
        if row:
            return int(row["id"])
    finally:
        conn.close()

    if not allow_create:
        return None

    notes = "Imported safely from Telegram queue"
    return int(database.add_new_client(client_name.strip(), client_phone.strip(), client_type, notes))


def parse_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except ValueError as exc:
        raise ImporterError(f"Invalid numeric value: {value}") from exc


def parse_items_payload(items_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(items_json)
    except json.JSONDecodeError as exc:
        raise ImporterError(f"Invalid items_json payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ImporterError("items_json must decode to an object.")
    if "items" not in payload or not isinstance(payload["items"], list):
        raise ImporterError("items_json must contain an items list.")
    return payload


def build_order_notes(notes: str, external_order_id: str) -> str:
    suffix = f"[external_order_id:{external_order_id}]"
    source_notes = (notes or "").strip()
    if suffix in source_notes:
        return source_notes
    return f"{source_notes}\n{suffix}".strip()


def resolve_items_for_import(items_payload: Dict[str, Any], client_type: str) -> List[Dict[str, Any]]:
    if items_payload.get("needs_review"):
        raise ImporterError("items_json flagged needs_review=true; importer will not save a partial order.")

    final_items: List[Dict[str, Any]] = []
    for item in items_payload["items"]:
        if item.get("needs_review"):
            raise ImporterError(f"Item '{item.get('product_name', '')}' requires manual review.")

        resolved = database.resolve_or_create_product_for_external_order(
            product_id=item.get("product_id"),
            product_name=item.get("product_name"),
            client_type=client_type,
            external_price=item.get("price"),
        )

        if not resolved.get("success"):
            raise ImporterError(f"Failed to resolve product '{item.get('product_name', '')}': {resolved.get('error', 'unknown error')}")
        if resolved.get("needs_review"):
            raise ImporterError(
                f"Resolved product '{item.get('product_name', '')}' still needs review "
                f"(price_source={resolved.get('price_source')})."
            )

        qty = parse_float(item.get("qty"))
        selected_price = parse_float(resolved.get("selected_price"))
        line_total = round(qty * selected_price, 2)
        final_items.append(
            {
                "id": int(resolved["product"]["id"]),
                "name": resolved["product"]["name"],
                "qty": qty,
                "price": selected_price,
                "total": line_total,
                "item_index": item.get("item_index", ""),
            }
        )
    return final_items


def compute_amounts(row: Dict[str, str], final_items: List[Dict[str, Any]]) -> Dict[str, float]:
    subtotal = round(sum(parse_float(item["total"]) for item in final_items), 2)
    paid_amount = round(parse_float(row.get("paid_amount")), 2)
    discount = round(parse_float(row.get("discount")), 2)
    net_total = round(subtotal - discount, 2)
    remaining_amount = round(net_total - paid_amount, 2)
    return {
        "subtotal": subtotal,
        "discount": discount,
        "net_total": net_total,
        "paid_amount": paid_amount,
        "remaining_amount": remaining_amount,
    }


def download_telegram_file(bot_token: str, telegram_file_id: str, target_path: Path) -> None:
    get_file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={urllib.parse.quote(telegram_file_id)}"
    with urllib.request.urlopen(get_file_url, timeout=30) as response:
        metadata = json.load(response)
    if not metadata.get("ok"):
        raise ImporterError(f"Telegram getFile failed for file_id {telegram_file_id}")

    file_path = metadata["result"]["file_path"]
    download_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    with urllib.request.urlopen(download_url, timeout=60) as response:
        content = response.read()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)


def choose_image_target(order_folder: Path, image_row: Dict[str, str], items_by_index: Dict[str, Dict[str, Any]]) -> Path:
    item_index = str(image_row.get("item_index", "")).strip()
    filename = sanitize_name(image_row.get("original_name") or f"telegram_{image_row.get('message_id', 'image')}.jpg")
    if not filename:
        filename = f"telegram_{image_row.get('message_id', 'image')}.jpg"

    if item_index and item_index in items_by_index:
        item = items_by_index[item_index]
        product_folder_name = f"{int(float(item_index)) + 1}_{sanitize_name(item['name'])}"
        return order_folder / product_folder_name / filename
    return order_folder / filename


def save_order_images(
    bot_token: str,
    order_id: int,
    client_type: str,
    client_name: str,
    order_notes: str,
    final_items: List[Dict[str, Any]],
    image_rows: List[Dict[str, str]],
    dry_run: bool,
) -> Dict[str, Any]:
    root_path = get_storage_root()
    engine = FileOpsEngine(root_path)
    first_product = final_items[0]["name"] if final_items else "Product"
    order_folder = Path(engine.get_creation_path(client_type, client_name, first_product, order_notes, order_id))

    if dry_run:
        return {"order_folder": str(order_folder), "saved_images": []}

    order_folder.mkdir(parents=True, exist_ok=True)
    update_result = database.update_order_image_path(order_id, str(order_folder))
    if update_result is not True:
        raise ImporterError(f"update_order_image_path failed: {update_result}")

    items_by_index = {str(item.get("item_index", "")).strip(): item for item in final_items if str(item.get("item_index", "")).strip() != ""}
    saved_images: List[Dict[str, str]] = []
    for image_row in image_rows:
        telegram_file_id = image_row.get("telegram_file_id", "").strip()
        if not telegram_file_id:
            continue
        target_path = choose_image_target(order_folder, image_row, items_by_index)
        download_telegram_file(bot_token, telegram_file_id, target_path)
        saved_images.append(
            {
                "image_row_id": image_row.get("image_row_id", ""),
                "local_saved_path": str(target_path),
            }
        )

    return {"order_folder": str(order_folder), "saved_images": saved_images}


def mark_image_rows(sheet: ImporterGoogleSheet, image_rows: List[Dict[str, str]], status: str, path_map: Dict[str, str] | None = None) -> None:
    path_map = path_map or {}
    for image_row in image_rows:
        fields = {"import_status": status}
        image_row_id = image_row.get("image_row_id", "")
        if image_row_id in path_map:
            fields["local_saved_path"] = path_map[image_row_id]
        sheet.update_row_fields("telegram_images", int(image_row["_row_index"]), fields)


def force_sync_imported_order(order_id: int) -> Dict[str, Any]:
    syncer = POSGoogleSheetSync(dry_run=False)
    return syncer.sync_order_bundle(order_id)


def process_inbox_row(
    sheet: ImporterGoogleSheet,
    settings: Any,
    row: Dict[str, str],
    dry_run: bool,
) -> Dict[str, Any]:
    external_order_id = row.get("external_order_id", "").strip()
    if not external_order_id:
        raise ImporterError("external_order_id is missing.")

    if row.get("imported_order_id", "").strip():
        return {"status": "skipped", "reason": "imported_order_id already set", "external_order_id": external_order_id}

    existing_local_order = find_existing_local_order_by_external_id(external_order_id)
    if existing_local_order:
        if not dry_run:
            sheet.update_row_fields(
                "telegram_inbox",
                int(row["_row_index"]),
                {
                    "status": "duplicate",
                    "imported_order_id": existing_local_order,
                    "error_message": f"Duplicate external_order_id already exists in local order #{existing_local_order}",
                },
            )
        return {
            "status": "duplicate",
            "external_order_id": external_order_id,
            "imported_order_id": existing_local_order,
        }

    items_payload = parse_items_payload(row.get("items_json", ""))
    client_name = row.get("client_name", "").strip()
    client_phone = row.get("client_phone", "").strip()
    client_type = row.get("client_type", "Retail").strip() or "Retail"
    order_notes = build_order_notes(row.get("notes", ""), external_order_id)
    image_rows = sheet.get_images_for_external_order(external_order_id)

    client_id = resolve_client_id(client_name, client_phone, client_type, allow_create=not dry_run)
    final_items = resolve_items_for_import(items_payload, client_type)
    amounts = compute_amounts(row, final_items)

    preview = {
        "external_order_id": external_order_id,
        "client_id": client_id,
        "client_name": client_name,
        "client_type": client_type,
        "client_would_be_created": client_id is None,
        "items_count": len(final_items),
        "amounts": amounts,
        "images_count": len(image_rows),
        "notes": order_notes,
    }

    if dry_run:
        image_preview = save_order_images(
            settings.bot_token,
            order_id=0,
            client_type=client_type,
            client_name=client_name,
            order_notes=order_notes,
            final_items=final_items,
            image_rows=image_rows,
            dry_run=True,
        )
        preview["order_folder_preview"] = image_preview["order_folder"]
        return {"status": "dry-run", **preview}

    save_result = database.save_order_transaction(
        client_id=client_id,
        total_amount=amounts["subtotal"],
        discount=amounts["discount"],
        net_total=amounts["net_total"],
        paid_amount=amounts["paid_amount"],
        remaining=amounts["remaining_amount"],
        items=final_items,
        payment_method=row.get("payment_method", "Telegram") or "Telegram",
        notes=order_notes,
    )
    if not save_result.get("success"):
        raise ImporterError(f"save_order_transaction failed: {save_result.get('error', 'unknown error')}")

    order_id = int(save_result["order_id"])
    try:
        image_result = save_order_images(
            settings.bot_token,
            order_id=order_id,
            client_type=client_type,
            client_name=client_name,
            order_notes=order_notes,
            final_items=final_items,
            image_rows=image_rows,
            dry_run=False,
        )
    except Exception as exc:
        sheet.update_row_fields(
            "telegram_inbox",
            int(row["_row_index"]),
            {
                "status": "failed",
                "imported_order_id": order_id,
                "error_message": f"Order saved locally as #{order_id}, but image import failed: {exc}",
            },
        )
        mark_image_rows(sheet, image_rows, "failed")
        return {
            "status": "failed",
            "external_order_id": external_order_id,
            "imported_order_id": order_id,
            "error": str(exc),
        }

    try:
        force_sync_imported_order(order_id)
    except Exception as exc:
        sheet.update_row_fields(
            "telegram_inbox",
            int(row["_row_index"]),
            {
                "status": "failed",
                "imported_order_id": order_id,
                "error_message": f"Order saved locally as #{order_id}, but Google Sheets order sync failed: {exc}",
            },
        )
        path_map = {item["image_row_id"]: item["local_saved_path"] for item in image_result["saved_images"]}
        mark_image_rows(sheet, image_rows, "imported", path_map=path_map)
        return {
            "status": "failed",
            "external_order_id": external_order_id,
            "imported_order_id": order_id,
            "error": str(exc),
        }

    sheet.update_row_fields(
        "telegram_inbox",
        int(row["_row_index"]),
        {
            "status": "imported",
            "imported_order_id": order_id,
            "error_message": "",
        },
    )
    path_map = {item["image_row_id"]: item["local_saved_path"] for item in image_result["saved_images"]}
    mark_image_rows(sheet, image_rows, "imported", path_map=path_map)
    return {
        "status": "imported",
        "external_order_id": external_order_id,
        "imported_order_id": order_id,
        "order_folder": image_result["order_folder"],
        "saved_images": image_result["saved_images"],
        **preview,
    }


def handle_processing_error(sheet: ImporterGoogleSheet, row: Dict[str, str], error_message: str) -> Dict[str, Any]:
    external_order_id = row.get("external_order_id", "").strip()
    sheet.update_row_fields(
        "telegram_inbox",
        int(row["_row_index"]),
        {
            "status": "failed",
            "error_message": error_message,
        },
    )
    image_rows = sheet.get_images_for_external_order(external_order_id)
    mark_image_rows(sheet, image_rows, "failed")
    return {"status": "failed", "external_order_id": external_order_id, "error": error_message}


def run_import(dry_run: bool, limit: int | None) -> Dict[str, Any]:
    settings = load_settings()
    sheet = ImporterGoogleSheet(settings)
    pending_rows = select_pending_rows(sheet, limit)

    summary: Dict[str, Any] = {
        "dry_run": dry_run,
        "selected_pending_rows": len(pending_rows),
        "results": [],
    }
    if not pending_rows:
        return summary

    if not dry_run:
        backup_dir = create_safety_backup()
        summary["backup_dir"] = str(backup_dir)

    for row in pending_rows:
        try:
            result = process_inbox_row(sheet, settings, row, dry_run=dry_run)
        except Exception as exc:
            if dry_run:
                result = {
                    "status": "failed-preview",
                    "external_order_id": row.get("external_order_id", ""),
                    "error": str(exc),
                }
            else:
                result = handle_processing_error(sheet, row, str(exc))
        summary["results"].append(result)
    return summary


def verify_local_order_presence(order_id: int, external_order_id: str) -> Dict[str, Any]:
    syncer = __import__("google_sheet_realtime_sync").POSGoogleSheetSync(dry_run=False)
    time.sleep(2)
    orders_sheet_rows = []
    try:
        syncer.ensure_ready()
        orders_sheet_rows = syncer.sheets_service.spreadsheets().values().get(
            spreadsheetId=syncer.spreadsheet_id,
            range=f"{syncer.tabs['orders']}!A:H",
        ).execute().get("values", [])
    except Exception:
        orders_sheet_rows = []

    sheet_match = False
    for row in orders_sheet_rows[1:]:
        joined = " | ".join(row)
        if str(order_id) in joined and external_order_id in joined:
            sheet_match = True
            break

    kanban_match = False
    for order in database.get_kanban_orders():
        if int(order["id"]) == int(order_id):
            kanban_match = True
            break

    order_details = database.get_order_details(order_id)
    return {
        "order_id": order_id,
        "external_order_id": external_order_id,
        "orders_tab_match": sheet_match,
        "kanban_match": kanban_match,
        "local_image_path": order_details.get("local_image_path") if order_details else "",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args()
    if not args.dry_run and not args.once:
        print(json.dumps({"success": False, "error": "Choose --dry-run or --once."}, ensure_ascii=False, indent=2))
        return 1

    summary = run_import(dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
