from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Sequence

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ConfigError, load_settings
from openrouter_client import (
    ask_general_assistant,
    ask_openrouter,
    build_sheet_context,
    classify_message_intent,
    extract_order_json,
)
from sheets_queue import STATUS_GROUPS
from firebase_client import TelegramFirebaseQueue as TelegramSheetsQueue

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger("telegram_bot")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

(
    STATE_CLIENT_NAME,
    STATE_CLIENT_PHONE,
    STATE_CLIENT_TYPE,
    STATE_ITEMS,
    STATE_PAID,
    STATE_NOTES,
    STATE_IMAGES,
    STATE_CONFIRM,
) = range(8)

SMART_ORDER_KEY = "smart_order_draft"
SMART_AWAITING_KEY = "smart_awaiting"
SMART_LAST_ORDER_KEY = "smart_last_order"
SMART_PAYMENT_KEY = "smart_payment_draft"
SMART_ADMIN_ACTION_KEY = "smart_admin_action_draft"
DEFAULT_CLIENT_NAME = "عميل تيليجرام"
AI_MODEL_NAME = "gpt-4o-mini"
AI_REQUEST_TIMEOUT_SECONDS = 90
SMART_PRICE_CONFIRM_TEXT = "تأكيد تعديل الأسعار"
SMART_CONFIRM_TEXT = "تأكيد"
SMART_CANCEL_TEXT = "الغاء"
ARABIC_HELP_TEXT = (
    "أهلا بيك في Smart Arabic POS Assistant.\n"
    "تقدر تكتب أوامر زي:\n"
    "- طلبات\n"
    "- طلبات جاهزة\n"
    "- حسابات\n"
    "- عميل زينب\n"
    "- سعر تابلو\n"
    "- مخزون تابلو\n"
    "- طلب رقم 256\n"
    "- بحث طلب زينب\n"
    "- طلب جديد\n\n"
    "وتقدر تبعت الطلب بالعربي الطبيعي زي:\n"
    "- اية كرم جملة تابلو 30ف40\n"
    "- 01012345678 قطاعي تابلو 30ف40 2 مدفوع 50\n"
    "- محمد جملة منتج جديد @ 25\n\n"
    f"للحفظ اكتب {SMART_CONFIRM_TEXT}، وللإلغاء اكتب {SMART_CANCEL_TEXT}."
)
AI_DISABLED_MESSAGE = "خدمة الذكاء الاصطناعي غير متاحة حاليًا."

COMMAND_ALIASES = {
    "ابدأ": "start",
    "مساعدة": "help",
    "اوامر": "help",
    "المنتجات": "products",
    "منتجات": "products",
    "عميل": "client",
    "العملاء": "client",
    "طلبات اليوم": "orders_today",
    "النهارده": "orders_today",
    "طلب جديد": "neworder_alias",
    "اضافة طلب": "neworder_alias",
    "الغاء": "cancel_alias",
    "شرح": "guide",
}

WHOLESALE_WORDS = {"جمله", "جملة", "wholesale"}
RETAIL_WORDS = {"قطاعي", "قطعي", "retail"}
PAID_PATTERN = re.compile(r"(?:مدفوع|دفع|paid)\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
DISCOUNT_PATTERN = re.compile(r"(?:خصم|discount)\s*([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
NOTES_PATTERN = re.compile(r"(?:ملاحظات|ملحوظة|ملحوظه)\s*(.+)$", re.IGNORECASE)
PHONE_AT_START_PATTERN = re.compile(r"^\s*(\+?\d[\d\s\-()]{7,})")


def get_settings_and_queue() -> tuple[Any, TelegramSheetsQueue]:
    settings = load_settings()
    queue = TelegramSheetsQueue(settings)
    return settings, queue


def get_user_id(update: Update) -> int:
    if not update.effective_user:
        return 0
    return update.effective_user.id


def get_display_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return "يا بطل"
    if user.first_name:
        return f"يا {user.first_name}"
    if user.username:
        return f"يا @{user.username}"
    return "يا بطل"


def is_allowed_user(settings: Any, update: Update) -> bool:
    user_id = get_user_id(update)
    return bool(user_id) and settings.is_authorized(user_id)


async def reject_unauthorized(update: Update, settings: Any) -> None:
    message = settings.authorization_notice(get_user_id(update))
    if update.message:
        await update.message.reply_text(message)


def normalize_input(text: str) -> str:
    return TelegramSheetsQueue.normalize_text(text)


def is_cancel_text(text: str) -> bool:
    return normalize_input(text) in {"cancel", "الغاء", "إلغاء"}


def is_confirm_text(text: str) -> bool:
    return normalize_input(text) in {"confirm", "تاكيد", "تأكيد"}


def choose_price(row: Dict[str, str], client_type: str) -> float | None:
    key = "wholesale_price" if client_type == "Wholesale" else "retail_price"
    return TelegramSheetsQueue.parse_money(row.get(key, ""))


def client_type_label(client_type: str) -> str:
    return "جملة" if client_type == "Wholesale" else "قطاعي"


def looks_like_order_request(text: str) -> bool:
    normalized = normalize_input(text)
    if not normalized:
        return False
    if any(word in normalized for word in WHOLESALE_WORDS | RETAIL_WORDS):
        return True
    if "@" in text:
        return True
    if PHONE_AT_START_PATTERN.search(text):
        return True
    if any(keyword in normalized for keyword in {"مدفوع", "دفع", "خصم", "طلب"}):
        return True
    return False


def build_help_text() -> str:
    return ARABIC_HELP_TEXT


def build_summary_text(draft: Dict[str, Any]) -> str:
    lines = [
        f"العميل: {draft.get('client_name') or DEFAULT_CLIENT_NAME}",
        f"النوع: {client_type_label(draft.get('client_type', 'Retail'))}",
        f"الهاتف: {draft.get('client_phone') or '-'}",
        "المنتجات:",
    ]
    for item in draft.get("items", []):
        review_suffix = " [مراجعة]" if item.get("needs_review") else ""
        note_suffix = f" | ملاحظات: {item.get('notes')}" if item.get("notes") else ""
        lines.append(
            f"- {item.get('product_name', '')} × {TelegramSheetsQueue.format_number(item.get('qty', 1))} × "
            f"{TelegramSheetsQueue.format_number(item.get('price', 0))} = {TelegramSheetsQueue.format_number(item.get('total', 0))}"
            f"{review_suffix}{note_suffix}"
        )
    lines.extend(
        [
            f"الإجمالي: {TelegramSheetsQueue.format_number(draft.get('total_amount', 0))}",
            f"الخصم: {TelegramSheetsQueue.format_number(draft.get('discount', 0))}",
            f"المدفوع: {TelegramSheetsQueue.format_number(draft.get('paid_amount', 0))}",
            f"المتبقي: {TelegramSheetsQueue.format_number(draft.get('remaining_amount', 0))}",
            f"الملاحظات: {draft.get('notes') or '-'}",
        ]
    )
    missing_fields = draft.get("missing_fields", [])
    if missing_fields:
        lines.append(f"حقول محتاجة مراجعة: {', '.join(missing_fields)}")
    if draft.get("needs_review"):
        lines.append("فيه عناصر محتاجة مراجعة قبل التنفيذ المحلي لاحقًا.")
    lines.extend(
        [
            "",
            "هل تؤكد تسجيل الطلب؟ اكتب: تأكيد",
            f'وللإلغاء اكتب: "{SMART_CANCEL_TEXT}".',
        ]
    )
    return "\n".join(lines)


def build_order_notes(notes: str, original_text: str) -> str:
    notes_parts = []
    if notes.strip():
        notes_parts.append(notes.strip())
    notes_parts.append(f"[raw_telegram_text:{original_text.strip()}]")
    return "\n".join(notes_parts)


def trigger_local_import_now(settings: Any) -> bool:
    try:
        settings.telegram_import_flag_path.write_text("import-now\n", encoding="utf-8")
        return True
    except Exception:
        LOGGER.exception("Failed to create telegram import trigger flag.")
        return False


def extract_money_values(text: str) -> list[float]:
    matches = re.findall(r"[0-9٠-٩]+(?:[.,٫٬][0-9٠-٩]+)?", text or "")
    values: list[float] = []
    for raw_value in matches:
        parsed = TelegramSheetsQueue.parse_money(raw_value)
        if parsed is not None:
            values.append(parsed)
    return values


def find_best_client(queue: TelegramSheetsQueue, query: str) -> Dict[str, str] | None:
    rows = queue.search_clients(query, limit=5)
    if not rows:
        return None
    return rows[0]


def build_payment_summary_text(draft: Dict[str, Any]) -> str:
    return "\n".join(
        [
            "مسودة دفعة:",
            f"العميل: {draft.get('client_name', '') or DEFAULT_CLIENT_NAME}",
            f"الرصيد الحالي: {TelegramSheetsQueue.format_number(draft.get('balance_before', 0))}",
            f"مبلغ الدفعة: {TelegramSheetsQueue.format_number(draft.get('amount', 0))}",
            f"الرصيد بعد الدفع: {TelegramSheetsQueue.format_number(draft.get('balance_after', 0))}",
            f"طريقة الدفع: {draft.get('payment_method', 'Telegram')}",
            f"ملاحظات: {draft.get('notes') or '-'}",
            "",
            f"هل تؤكد تسجيل الدفعة؟ اكتب: {SMART_CONFIRM_TEXT}",
            f'وللإلغاء اكتب: "{SMART_CANCEL_TEXT}".',
        ]
    )


def build_price_update_summary_text(draft: Dict[str, Any]) -> str:
    lines = [
        "مسودة تعديل أسعار:",
        f"النطاق: {draft.get('target_scope', '-')}",
        f"نوع التعديل: {draft.get('price_mode_label', '-')}",
        f"عدد المنتجات المتأثرة: {len(draft.get('products', []))}",
    ]
    for row in draft.get("products", [])[:12]:
        lines.append(
            f"- {row.get('name', '')} | قطاعي: {row.get('retail_price', '') or '0'} -> {row.get('new_retail_price', '') or row.get('retail_price', '') or '0'}"
            f" | جملة: {row.get('wholesale_price', '') or '0'} -> {row.get('new_wholesale_price', '') or row.get('wholesale_price', '') or '0'}"
        )
    lines.extend(
        [
            "",
            f"للتنفيذ الآمن اكتب: {SMART_PRICE_CONFIRM_TEXT}",
            f'وللإلغاء اكتب: "{SMART_CANCEL_TEXT}".',
        ]
    )
    return "\n".join(lines)


def build_partial_search_reply(queue: TelegramSheetsQueue, query: str) -> str:
    results = queue.partial_search_everywhere(query, limit_per_section=4)
    lines = [f"نتايج البحث عن: {query}"]

    clients = results["clients"]
    if clients:
        lines.append("العملاء:")
        lines.extend(f"- {row.get('name', '')} | {row.get('phone', '') or '-'} | رصيد: {row.get('balance', '') or '0'}" for row in clients)

    products = results["products"]
    if products:
        lines.append("المنتجات:")
        lines.extend(
            f"- {row.get('name', '')} | قطاعي: {row.get('retail_price', '') or '0'} | جملة: {row.get('wholesale_price', '') or '0'}"
            for row in products
        )

    orders = results["orders"]
    if orders:
        lines.append("طلبات دخلت البرنامج:")
        lines.extend(
            f"- طلب #{row.get('order_id', '')} | {row.get('client_name', '')} | {row.get('status', '') or '-'} | {row.get('total_amount', '') or '0'}"
            for row in orders
        )

    order_items = results["order_items"]
    if order_items:
        lines.append("أصناف داخل الطلبات:")
        lines.extend(
            f"- {row.get('product_name', '')} | طلب #{row.get('order_id', '')} | كمية: {row.get('qty', '') or '0'}"
            for row in order_items
        )

    telegram_inbox = results["telegram_inbox"]
    if telegram_inbox:
        lines.append("طلبات تيليجرام:")
        lines.extend(
            f"- {row.get('client_name', '') or DEFAULT_CLIENT_NAME} | status: {row.get('status', '') or '-'} | {row.get('external_order_id', '')}"
            for row in telegram_inbox
        )

    if len(lines) == 1:
        return "مش لاقي نتائج مطابقة للبحث ده."
    return "\n".join(lines)


def build_sync_status_text(queue: TelegramSheetsQueue) -> str:
    summary = queue.get_telegram_sync_status_summary()
    lines = [
        "حالة المزامنة:",
        f"- الحالة: {summary['status_text']}",
        f"- pending: {summary['pending_count']}",
        f"- imported: {summary['imported_count']}",
        f"- failed: {summary['failed_count']}",
        f"- آخر وقت ظاهر: {summary.get('last_event_at') or '-'}",
    ]
    if summary.get("last_error"):
        lines.append(f"- آخر خطأ: {summary['last_error']}")
    return "\n".join(lines)


def extract_phone_prefix(text: str) -> tuple[str, str]:
    match = PHONE_AT_START_PATTERN.match(text)
    if not match:
        return "", text.strip()
    phone_text = TelegramSheetsQueue.normalize_phone(match.group(1))
    remaining = text[match.end():].strip(" -،,")
    return phone_text, remaining


def extract_client_type(text: str) -> tuple[str | None, str]:
    tokens = text.split()
    resolved = None
    remaining_tokens = []
    for token in tokens:
        normalized = normalize_input(token)
        if normalized in WHOLESALE_WORDS and resolved is None:
            resolved = "Wholesale"
            continue
        if normalized in RETAIL_WORDS and resolved is None:
            resolved = "Retail"
            continue
        remaining_tokens.append(token)
    return resolved, " ".join(remaining_tokens).strip()


def extract_notes_paid_discount(text: str) -> Dict[str, Any]:
    notes = ""
    working = text.strip()

    notes_match = NOTES_PATTERN.search(working)
    if notes_match:
        notes = notes_match.group(1).strip()
        working = working[:notes_match.start()].strip(" ،,")

    paid_amount = 0.0
    paid_match = PAID_PATTERN.search(working)
    if paid_match:
        paid_amount = TelegramSheetsQueue.parse_money(paid_match.group(1)) or 0.0
        working = PAID_PATTERN.sub("", working).strip(" ،,")

    discount = 0.0
    discount_match = DISCOUNT_PATTERN.search(working)
    if discount_match:
        discount = TelegramSheetsQueue.parse_money(discount_match.group(1)) or 0.0
        working = DISCOUNT_PATTERN.sub("", working).strip(" ،,")

    return {
        "working_text": " ".join(working.split()),
        "notes": notes,
        "paid_amount": round(paid_amount, 2),
        "discount": round(discount, 2),
    }


def extract_explicit_price(segment: str) -> tuple[str, float | None]:
    if "@" not in segment:
        return segment.strip(), None
    left, right = segment.rsplit("@", 1)
    price_value = TelegramSheetsQueue.parse_money(right.strip())
    return left.strip(), price_value


def extract_qty_from_segment(segment: str) -> tuple[str, float]:
    text = segment.strip()
    patterns = [
        re.compile(r"^(?P<name>.+?)\s+(?:عدد\s*)?(?P<qty>[0-9]+(?:[.,][0-9]+)?)$", re.IGNORECASE),
        re.compile(r"^(?P<name>.+?)\s*(?:x|×|\*)\s*(?P<qty>[0-9]+(?:[.,][0-9]+)?)$", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.match(text)
        if match:
            qty = TelegramSheetsQueue.parse_money(match.group("qty")) or 1.0
            return match.group("name").strip(), qty
    return text, 1.0


def select_product_candidate(candidates: Sequence[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not candidates:
        return None
    top = candidates[0]
    if top["score"] >= 0.93:
        return top
    if len(candidates) == 1 and top["score"] >= 0.82:
        return top
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    if top["score"] >= 0.86 and (top["score"] - second_score) >= 0.08:
        return top
    return None


def find_best_product_from_tokens(
    queue: TelegramSheetsQueue,
    tokens: Sequence[str],
    start_index: int,
) -> Dict[str, Any] | None:
    best: Dict[str, Any] | None = None
    max_length = min(len(tokens), start_index + 6)
    for end_index in range(start_index + 1, max_length + 1):
        phrase = " ".join(tokens[start_index:end_index])
        candidates = queue.find_product_candidates(phrase, limit=3)
        if not candidates:
            continue
        top = candidates[0]
        if top["score"] < 0.72:
            continue
        query_tokens = phrase.split()
        compact_query = normalize_input(phrase).replace(" ", "")
        if len(query_tokens) == 1 and len(compact_query) <= 4 and top["score"] < 0.96:
            continue
        candidate = {
            "query": phrase,
            "token_end": end_index,
            "candidates": candidates,
            "selected": select_product_candidate(candidates),
        }
        if best is None:
            best = candidate
            continue
        current_score = top["score"]
        best_score = best["candidates"][0]["score"]
        if current_score > best_score or (abs(current_score - best_score) < 0.02 and end_index > best["token_end"]):
            best = candidate
    return best


def infer_client_name_and_items_text(
    queue: TelegramSheetsQueue,
    working_text: str,
    phone: str,
    client_type: str | None,
    explicit_price_present: bool,
) -> tuple[str, str]:
    if not working_text:
        return "", ""
    tokens = working_text.split()
    if phone:
        return "", working_text.strip()

    first_product_match = None
    best_adjusted_score = 0.0
    for index in range(len(tokens)):
        match = find_best_product_from_tokens(queue, tokens, index)
        if not match:
            continue
        top_score = match["candidates"][0]["score"]
        matched_token_count = max(match["token_end"] - index, 1)
        if explicit_price_present and matched_token_count == 1 and top_score < 0.97:
            continue
        extra_prefix_penalty = index * 0.05
        extra_suffix_penalty = max(len(tokens) - match["token_end"], 0) * 0.01
        short_match_penalty = 0.05 if matched_token_count == 1 else 0.0
        adjusted_score = top_score - extra_prefix_penalty - extra_suffix_penalty - short_match_penalty
        if top_score >= 0.82 and adjusted_score > best_adjusted_score:
            best_adjusted_score = adjusted_score
            first_product_match = index

    if first_product_match is not None and first_product_match > 0:
        return " ".join(tokens[:first_product_match]).strip(), " ".join(tokens[first_product_match:]).strip()
    if first_product_match == 0:
        return "", working_text.strip()

    if explicit_price_present and client_type:
        if len(tokens) == 3:
            return tokens[0].strip(), " ".join(tokens[1:]).strip()
        if len(tokens) >= 4:
            return " ".join(tokens[:2]).strip(), " ".join(tokens[2:]).strip()
        if len(tokens) >= 3:
            return tokens[0].strip(), " ".join(tokens[1:]).strip()
    return "", working_text.strip()


def resolve_item_segment(
    queue: TelegramSheetsQueue,
    segment_text: str,
    client_type: str,
    item_index: int,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    overrides = overrides or {}
    original_segment = segment_text.strip()
    segment_key = normalize_input(original_segment)
    price_base_text, explicit_price = extract_explicit_price(original_segment)
    if segment_key in overrides and overrides[segment_key].get("explicit_price") is not None:
        explicit_price = overrides[segment_key]["explicit_price"]

    item_base_text, qty = extract_qty_from_segment(price_base_text)
    qty = max(qty, 1.0)
    item_name_query = item_base_text.strip()
    if not item_name_query:
        return {
            "success": False,
            "action": "invalid_item",
            "message": "فيه سطر منتج فاضي. ابعته تاني بشكل أوضح.",
        }

    forced_product_name = overrides.get(segment_key, {}).get("forced_product_name")
    if forced_product_name:
        candidates = queue.find_product_candidates(forced_product_name, limit=3)
    else:
        candidates = queue.find_product_candidates(item_name_query, limit=3)

    selected = select_product_candidate(candidates)
    if forced_product_name and candidates:
        selected = candidates[0]

    if selected:
        row = selected["row"]
        unit_price = choose_price(row, client_type)
        if unit_price is None or unit_price <= 0:
            return {
                "success": False,
                "action": "need_price",
                "segment_key": segment_key,
                "segment_text": original_segment,
                "item_name": row.get("name", item_name_query),
                "message": f"سعر المنتج {row.get('name', item_name_query)} غير واضح. ابعت السعر رقماً بس، مثال: 25",
            }
        total = round(qty * unit_price, 2)
        return {
            "success": True,
            "item": {
                "product_id": str(row.get("product_id", "")),
                "product_name": row.get("name", item_name_query),
                "qty": qty,
                "price": round(unit_price, 2),
                "total": total,
                "item_index": item_index,
                "matched_existing_product": True,
                "needs_review": False,
                "price_source": "wholesale_price" if client_type == "Wholesale" else "retail_price",
                "explicit_price": explicit_price,
            },
        }

    if candidates and len(candidates) > 1 and candidates[0]["score"] >= 0.7:
        return {
            "success": False,
            "action": "need_choice",
            "segment_key": segment_key,
            "segment_text": original_segment,
            "item_name": item_name_query,
            "candidates": candidates[:3],
            "message": "مش متأكد من اسم المنتج، اختار رقم من دول.",
        }

    if explicit_price is None or explicit_price <= 0:
        return {
            "success": False,
            "action": "need_price",
            "segment_key": segment_key,
            "segment_text": original_segment,
            "item_name": item_name_query,
            "message": f"المنتج ده جديد، اكتب سعره بالشكل: {item_name_query} @ 25",
        }

    total = round(qty * explicit_price, 2)
    return {
        "success": True,
        "item": {
            "product_id": "",
            "product_name": item_name_query,
            "qty": qty,
            "price": round(explicit_price, 2),
            "total": total,
            "item_index": item_index,
            "matched_existing_product": False,
            "needs_review": False,
            "price_source": "user_supplied_new_product",
            "explicit_price": explicit_price,
        },
    }


def parse_items_from_text(
    queue: TelegramSheetsQueue,
    items_text: str,
    client_type: str,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    overrides = overrides or {}
    segments = [segment.strip() for segment in re.split(r"[،,]+", items_text) if segment.strip()]
    if len(segments) > 1:
        items = []
        for index, segment in enumerate(segments):
            resolved = resolve_item_segment(queue, segment, client_type, index, overrides=overrides)
            if not resolved["success"]:
                return resolved
            items.append(resolved["item"])
        return {
            "success": True,
            "items": items,
        }

    tokens = items_text.split()
    if not tokens:
        return {
            "success": False,
            "action": "invalid_item",
            "message": "ابعت منتج واحد على الأقل عشان أفهم الطلب.",
        }

    items = []
    index = 0
    item_index = 0
    while index < len(tokens):
        best_match = find_best_product_from_tokens(queue, tokens, index)
        if best_match and best_match["candidates"][0]["score"] >= 0.82:
            query = best_match["query"]
            qty = 1.0
            next_index = best_match["token_end"]
            if next_index < len(tokens):
                next_token = tokens[next_index]
                next_qty = TelegramSheetsQueue.parse_money(next_token)
                if next_qty is not None and next_qty > 0:
                    qty = next_qty
                    next_index += 1
            segment = query if qty == 1 else f"{query} {TelegramSheetsQueue.format_number(qty)}"
            resolved = resolve_item_segment(queue, segment, client_type, item_index, overrides=overrides)
            if not resolved["success"]:
                return resolved
            if qty != 1:
                resolved["item"]["qty"] = qty
                resolved["item"]["total"] = round(qty * (resolved["item"]["price"] or 0), 2)
            items.append(resolved["item"])
            item_index += 1
            index = next_index
            continue

        fallback_segment = " ".join(tokens[index:]).strip()
        resolved = resolve_item_segment(queue, fallback_segment, client_type, item_index, overrides=overrides)
        if not resolved["success"]:
            return resolved
        items.append(resolved["item"])
        break

    return {
        "success": True,
        "items": items,
    }


def parse_natural_order_text(
    queue: TelegramSheetsQueue,
    text: str,
    overrides: Dict[str, Any] | None = None,
    forced_client_type: str | None = None,
) -> Dict[str, Any]:
    overrides = overrides or {}
    original_text = text.strip()
    extracted = extract_notes_paid_discount(original_text)
    phone, working_text = extract_phone_prefix(extracted["working_text"])
    found_client_type, after_type_text = extract_client_type(working_text)
    explicit_price_present = "@" in original_text
    text_for_inference, _ = extract_explicit_price(after_type_text)
    client_type = forced_client_type or found_client_type

    if not client_type and not phone:
        return {
            "success": False,
            "action": "need_client_type",
            "original_text": original_text,
            "message": "محتاج أعرف نوع العميل الأول: جملة ولا قطاعي؟",
        }

    if not client_type and phone:
        client_type = "Retail"
        type_warning = "مافيش نوع عميل واضح، فاعتبرت الطلب قطاعي مؤقتًا."
    else:
        type_warning = ""

    client_name, inferred_items_text = infer_client_name_and_items_text(
        queue=queue,
        working_text=text_for_inference,
        phone=phone,
        client_type=client_type,
        explicit_price_present=explicit_price_present,
    )
    if client_name:
        prefix_pattern = re.compile(rf"^\s*{re.escape(client_name)}\b", re.IGNORECASE)
        items_text = prefix_pattern.sub("", after_type_text, count=1).strip(" ،,")
    else:
        items_text = after_type_text.strip() or inferred_items_text

    if not client_name and not phone:
        client_name = DEFAULT_CLIENT_NAME

    if not items_text:
        return {
            "success": False,
            "action": "invalid_item",
            "message": "مش لاقي منتج واضح في الرسالة. ابعتها بالشكل: اسم العميل جملة اسم المنتج الكمية.",
        }

    items_result = parse_items_from_text(queue, items_text, client_type, overrides=overrides)
    if not items_result["success"]:
        items_result["original_text"] = original_text
        items_result["client_type"] = client_type
        items_result["client_name"] = client_name
        items_result["client_phone"] = phone
        items_result["notes"] = extracted["notes"]
        items_result["paid_amount"] = extracted["paid_amount"]
        items_result["discount"] = extracted["discount"]
        return items_result

    items = items_result["items"]
    total_amount = round(sum(TelegramSheetsQueue.parse_money(item.get("total", 0)) or 0 for item in items), 2)
    discount = round(extracted["discount"], 2)
    paid_amount = round(extracted["paid_amount"], 2)
    remaining_amount = round(total_amount - discount - paid_amount, 2)
    notes = build_order_notes(extracted["notes"], original_text)

    return {
        "success": True,
        "draft": {
            "root_message_id": 0,
            "chat_id": 0,
            "client_name": client_name or DEFAULT_CLIENT_NAME,
            "client_phone": phone,
            "client_type": client_type,
            "items": items,
            "total_amount": total_amount,
            "discount": discount,
            "paid_amount": paid_amount,
            "remaining_amount": remaining_amount,
            "notes": notes,
            "images": [],
            "raw_text": original_text,
            "type_warning": type_warning,
            "needs_review": any(bool(item.get("needs_review")) for item in items),
        },
    }


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _queue = get_settings_and_queue()
    user_id = get_user_id(update)
    notice = settings.authorization_notice(user_id)
    await update.message.reply_text(f"{notice}\n\n{build_help_text()}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    await update.message.reply_text(build_help_text())


async def orders_today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    rows = queue.list_orders_for_today()
    if not rows:
        await update.message.reply_text("مفيش طلبات مسجلة النهارده في الشيت.")
        return
    await update.message.reply_text(queue.format_orders_for_reply(rows))


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    await send_pending_inbox(update, queue, ["pending"], "مفيش طلبات منتظرة الاستيراد حاليًا.")


async def import_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    await send_import_status(update, queue)


async def sync_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    await update.message.reply_text(build_sync_status_text(queue))


async def import_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    created = trigger_local_import_now(settings)
    if created:
        await update.message.reply_text("تمام، عملت إشارة مزامنة فورية للمستورد المحلي.")
        return
    await update.message.reply_text("معرفتش أعمل إشارة المزامنة الفورية دلوقتي.")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("اكتب: /search ثم نص البحث.")
        return
    await update.message.reply_text(build_partial_search_reply(queue, query))


async def balances_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    summary = queue.get_accounts_summary()
    rows = summary["top_debt_clients"]
    if not rows:
        await update.message.reply_text("مفيش أرصدة مدينة ظاهرة حاليًا.")
        return
    await update.message.reply_text(
        "أعلى الأرصدة الحالية:\n"
        + "\n".join(f"- {row.get('name', '')} | {row.get('balance', '') or '0'}" for row in rows[:15])
    )


async def receivables_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    summary = queue.get_accounts_summary()
    pending_rows = queue.list_telegram_inbox(statuses=["pending"], limit=20)
    pending_remaining = round(
        sum(TelegramSheetsQueue.parse_money(row.get("remaining_amount", 0)) or 0 for row in pending_rows),
        2,
    )
    lines = [
        f"إجمالي الفلوس اللي لينا بره حسب أرصدة العملاء: {TelegramSheetsQueue.format_number(summary['total_client_balance'])}",
        f"طلبات تيليجرام المنتظرة المتبقي فيها: {TelegramSheetsQueue.format_number(pending_remaining)}",
    ]
    if summary["top_debt_clients"]:
        lines.append("أعلى العملاء مديونية:")
        lines.extend(f"- {row.get('name', '')} | {row.get('balance', '') or '0'}" for row in summary["top_debt_clients"][:10])
    await update.message.reply_text("\n".join(lines))


async def prices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("اكتب: /prices ثم اسم المنتج أو جزء منه.")
        return
    await send_product_price(update, queue, query)


async def client_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("اكتب: عميل + اسم العميل أو رقمه.")
        return

    rows = queue.search_clients(query)
    await update.message.reply_text(queue.format_clients_for_reply(rows))


async def products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return

    query = " ".join(context.args).strip()
    rows = queue.search_products(query)
    await update.message.reply_text(queue.format_products_for_reply(rows))


def ask_sheet_ai(settings: Any, queue: TelegramSheetsQueue, question: str) -> Dict[str, Any]:
    if settings.ai_provider != "openrouter":
        return {"success": False, "error": "unsupported_ai_provider", "details": settings.ai_provider}
    ai_context = build_sheet_context(question, queue)
    result = ask_openrouter(settings, question, ai_context)
    result["context_preview"] = ai_context
    return result


def normalize_client_type_value(raw_value: Any) -> tuple[str, bool]:
    normalized = normalize_input(str(raw_value or ""))
    if normalized in WHOLESALE_WORDS or normalized == "wholesale":
        return "Wholesale", False
    if normalized in RETAIL_WORDS or normalized == "retail":
        return "Retail", False
    return "Retail", True


def resolve_extracted_order_to_draft(
    queue: TelegramSheetsQueue,
    extracted_order: Dict[str, Any],
    original_text: str,
) -> Dict[str, Any]:
    raw_items = extracted_order.get("items", [])
    if not isinstance(raw_items, list) or not raw_items:
        return {
            "success": False,
            "message": "مش لاقي منتجات واضحة في الرسالة. ابعتها بشكل أوضح، مثال: العميل أحمد قطاعي مج عادي عدد 3 والمدفوع 50",
        }

    client_type, client_type_missing = normalize_client_type_value(extracted_order.get("client_type"))
    missing_fields = [str(field).strip() for field in extracted_order.get("missing_fields", []) if str(field).strip()]
    if client_type_missing and "client_type" not in missing_fields:
        missing_fields.append("client_type")

    client_name = str(extracted_order.get("client_name", "")).strip() or DEFAULT_CLIENT_NAME
    client_phone = TelegramSheetsQueue.normalize_phone(str(extracted_order.get("client_phone", "")).strip())
    paid_amount = round(TelegramSheetsQueue.parse_money(extracted_order.get("paid_amount", 0)) or 0.0, 2)
    discount = round(TelegramSheetsQueue.parse_money(extracted_order.get("discount", 0)) or 0.0, 2)
    raw_notes = str(extracted_order.get("notes", "")).strip()
    additional_notes: list[str] = []

    items: list[Dict[str, Any]] = []
    pricing_mode = "wholesale_price" if client_type == "Wholesale" else "retail_price"

    for item_index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            continue
        source_name = str(raw_item.get("product_name", "")).strip()
        if not source_name:
            continue

        qty = TelegramSheetsQueue.parse_money(raw_item.get("qty", 1)) or 1.0
        qty = max(qty, 1.0)
        typed_price = TelegramSheetsQueue.parse_money(raw_item.get("unit_price", ""))
        item_notes = str(raw_item.get("notes", "")).strip()
        needs_review = bool(raw_item.get("needs_review"))
        normalized_source_name = normalize_input(source_name)

        if normalized_source_name in {"صورة", "صوره", "صور", "image", "photo"}:
            note_text = item_notes or source_name
            additional_notes.append(f"مرفق متوقع من العميل: {note_text}")
            continue

        candidates = queue.find_product_candidates(source_name, limit=3)
        selected = select_product_candidate(candidates)
        matched_existing_product = selected is not None
        resolved_name = source_name
        product_id = ""

        if selected:
            product_row = selected["row"]
            resolved_name = product_row.get("name", source_name) or source_name
            product_id = str(product_row.get("product_id", ""))

        if typed_price is not None and typed_price > 0:
            unit_price = round(typed_price, 2)
            price_source = "user_typed"
        elif selected:
            unit_price = choose_price(selected["row"], client_type)
            if unit_price is None or unit_price <= 0:
                unit_price = 0.0
                price_source = "missing_sheet_price"
                needs_review = True
            else:
                unit_price = round(unit_price, 2)
                price_source = pricing_mode
        else:
            unit_price = 0.0
            price_source = "missing_price"
            needs_review = True

        if not matched_existing_product:
            needs_review = True

        total = round(qty * unit_price, 2)
        items.append(
            {
                "product_id": product_id,
                "product_name": resolved_name,
                "qty": qty,
                "price": unit_price,
                "total": total,
                "item_index": item_index,
                "matched_existing_product": matched_existing_product,
                "needs_review": needs_review,
                "price_source": price_source,
                "explicit_price": typed_price,
                "notes": item_notes,
                "source_product_name": source_name,
            }
        )

    if not items:
        return {
            "success": False,
            "message": "مش قادر أحدد المنتجات المطلوبة من الرسالة. ابعتها بشكل أوضح من فضلك.",
        }

    merged_notes = "\n".join(part for part in [raw_notes, *additional_notes] if part.strip())
    notes = build_order_notes(merged_notes, original_text)
    total_amount = round(sum(TelegramSheetsQueue.parse_money(item.get("total", 0)) or 0 for item in items), 2)
    remaining_amount = round(total_amount - discount - paid_amount, 2)
    needs_review = any(bool(item.get("needs_review")) for item in items)

    return {
        "success": True,
        "draft": {
            "root_message_id": 0,
            "chat_id": 0,
            "client_name": client_name,
            "client_phone": client_phone,
            "client_type": client_type,
            "items": items,
            "total_amount": total_amount,
            "discount": discount,
            "paid_amount": paid_amount,
            "remaining_amount": remaining_amount,
            "notes": notes,
            "images": [],
            "raw_text": original_text,
            "missing_fields": missing_fields,
            "needs_review": needs_review,
            "type_warning": "نوع العميل غير مذكور بوضوح، فاعتبرته قطاعي مؤقتًا." if client_type_missing else "",
        },
    }


async def ask_ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return

    if not settings.ai_enabled:
        await update.message.reply_text(AI_DISABLED_MESSAGE)
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("اكتب السؤال بعد /ask أو /ai.")
        return

    result = await asyncio.to_thread(ask_sheet_ai, settings, queue, query)
    if not result.get("success"):
        LOGGER.warning("OpenRouter ask failed: %s", result)
        await update.message.reply_text(AI_DISABLED_MESSAGE)
        return
    await update.message.reply_text(result["content"])


def reset_smart_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(SMART_ORDER_KEY, None)
    context.user_data.pop(SMART_AWAITING_KEY, None)
    context.user_data.pop(SMART_PAYMENT_KEY, None)
    context.user_data.pop(SMART_ADMIN_ACTION_KEY, None)


async def neworder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings, _queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return ConversationHandler.END

    context.user_data["pending_order"] = {
        "root_message_id": update.message.message_id,
        "chat_id": update.effective_chat.id,
        "images": [],
    }
    await update.message.reply_text(
        "تمام، ابعت اسم العميل الأول. ولو تحب أسرع، ابعت الطلب كله مرة واحدة بالعربي الطبيعي.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_CLIENT_NAME


async def collect_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)
    context.user_data["pending_order"]["client_name"] = update.message.text.strip()
    await update.message.reply_text("ابعت رقم الموبايل.")
    return STATE_CLIENT_PHONE


async def collect_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)
    context.user_data["pending_order"]["client_phone"] = update.message.text.strip()
    reply_markup = ReplyKeyboardMarkup([["قطاعي", "جملة"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("العميل قطاعي ولا جملة؟", reply_markup=reply_markup)
    return STATE_CLIENT_TYPE


async def collect_client_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)
    normalized = normalize_input(update.message.text)
    if normalized in WHOLESALE_WORDS:
        client_type = "Wholesale"
    elif normalized in RETAIL_WORDS:
        client_type = "Retail"
    else:
        await update.message.reply_text("اكتب جملة أو قطاعي بالضبط.")
        return STATE_CLIENT_TYPE
    context.user_data["pending_order"]["client_type"] = client_type
    await update.message.reply_text(
        "ابعت المنتجات، كل منتج في سطر لوحده بالشكل:\n"
        "تابلو 30ف40 x 2\n"
        "منتج جديد x 1 @ 25"
    )
    return STATE_ITEMS


async def collect_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return ConversationHandler.END
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)

    pending_order = context.user_data["pending_order"]
    try:
        parsed = queue.parse_items_text(update.message.text, pending_order["client_type"])
    except Exception as exc:
        await update.message.reply_text(str(exc))
        return STATE_ITEMS

    pending_order["items"] = parsed["items"]
    pending_order["total_amount"] = parsed["total_amount"]
    pending_order["needs_review"] = parsed["needs_review"]
    await update.message.reply_text(f"تمام، إجمالي المنتجات {parsed['total_amount']}. ابعت المدفوع.")
    return STATE_PAID


async def collect_paid_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)
    _settings, queue = get_settings_and_queue()
    paid_amount = queue.parse_money(update.message.text.strip())
    if paid_amount is None or paid_amount < 0:
        await update.message.reply_text("ابعت رقم صحيح للمدفوع، مثال 0 أو 150.")
        return STATE_PAID
    context.user_data["pending_order"]["paid_amount"] = round(paid_amount, 2)
    await update.message.reply_text("ابعت الملاحظات، أو اكتب - لو مفيش.")
    return STATE_NOTES


async def collect_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel_text(update.message.text):
        return await cancel_command(update, context)
    notes = update.message.text.strip()
    context.user_data["pending_order"]["notes"] = "" if notes == "-" else notes
    await update.message.reply_text(
        "لو عندك صور ابعتها دلوقتي. ولما تخلص اكتب /doneimages أو /skipimages.",
    )
    return STATE_IMAGES


async def collect_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pending_order = context.user_data["pending_order"]
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        await update.message.reply_text("الصورة ماوصلتش بشكل صحيح. ابعتها تاني أو اكتب /doneimages.")
        return STATE_IMAGES

    caption = update.message.caption or ""
    pending_order["images"].append(
        {
            "message_id": update.message.message_id,
            "item_index": "",
            "telegram_file_id": photo.file_id,
            "original_name": f"photo_{update.message.message_id}.jpg",
            "mime_type": "image/jpeg",
            "caption": caption,
        }
    )
    await update.message.reply_text(f"تمام، حفظت الصورة. عدد الصور الحالي: {len(pending_order['images'])}")
    return STATE_IMAGES


async def collect_image_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pending_order = context.user_data["pending_order"]
    document = update.message.document
    if not document:
        await update.message.reply_text("الملف ماوصلش كصورة. ابعت صورة أو اكتب /doneimages.")
        return STATE_IMAGES

    pending_order["images"].append(
        {
            "message_id": update.message.message_id,
            "item_index": "",
            "telegram_file_id": document.file_id,
            "original_name": document.file_name or f"image_{update.message.message_id}",
            "mime_type": document.mime_type or "image/*",
            "caption": update.message.caption or "",
        }
    )
    await update.message.reply_text(f"تمام، حفظت الصورة. عدد الصور الحالي: {len(pending_order['images'])}")
    return STATE_IMAGES


async def finish_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pending_order = context.user_data["pending_order"]
    pending_order["discount"] = pending_order.get("discount", 0.0)
    pending_order["remaining_amount"] = round(
        pending_order["total_amount"] - pending_order["paid_amount"] - pending_order["discount"],
        2,
    )
    summary = {
        "client_name": pending_order["client_name"],
        "client_phone": pending_order["client_phone"],
        "client_type": pending_order["client_type"],
        "total_amount": pending_order["total_amount"],
        "paid_amount": pending_order["paid_amount"],
        "remaining_amount": pending_order["remaining_amount"],
        "images_count": len(pending_order["images"]),
    }
    await update.message.reply_text(
        f'اكتب "{SMART_CONFIRM_TEXT}" للحفظ أو "{SMART_CANCEL_TEXT}" للإلغاء.\n'
        f"{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )
    return STATE_CONFIRM


async def skip_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await finish_images(update, context)


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings, queue = get_settings_and_queue()
    pending_order = context.user_data["pending_order"]
    decision = update.message.text.strip()

    if is_cancel_text(decision):
        await update.message.reply_text("تم إلغاء الطلب الحالي.", reply_markup=ReplyKeyboardRemove())
        context.user_data.pop("pending_order", None)
        return ConversationHandler.END

    if not is_confirm_text(decision):
        await update.message.reply_text(f'اكتب "{SMART_CONFIRM_TEXT}" للحفظ أو "{SMART_CANCEL_TEXT}" للإلغاء.')
        return STATE_CONFIRM

    result = queue.queue_order(
        chat_id=pending_order["chat_id"],
        root_message_id=pending_order["root_message_id"],
        client_name=pending_order["client_name"],
        client_phone=pending_order["client_phone"],
        client_type=pending_order["client_type"],
        items=pending_order["items"],
        paid_amount=pending_order["paid_amount"],
        notes=pending_order["notes"],
        images=pending_order["images"],
        discount=pending_order.get("discount", 0.0),
    )
    context.user_data.pop("pending_order", None)

    if result["duplicate"]:
        await update.message.reply_text("الطلب ده كان محفوظ قبل كده أونلاين.")
        return ConversationHandler.END

    await update.message.reply_text(
        "تم حفظ الطلب أونلاين، وهينزل في البرنامج لما جهاز المحل يفتح.\n"
        f"external_order_id: {result['external_order_id']}\n"
        f"عدد الصور: {result['images_count']}"
    )
    trigger_local_import_now(settings)
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("pending_order", None)
    reset_smart_state(context)
    await update.message.reply_text("تم إلغاء العملية الحالية.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def build_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("neworder", neworder_start)],
        states={
            STATE_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_client_name)],
            STATE_CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_client_phone)],
            STATE_CLIENT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_client_type)],
            STATE_ITEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_items)],
            STATE_PAID: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_paid_amount)],
            STATE_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_notes)],
            STATE_IMAGES: [
                MessageHandler(filters.PHOTO, collect_photo),
                MessageHandler(filters.Document.IMAGE, collect_image_document),
                CommandHandler("doneimages", finish_images),
                CommandHandler("skipimages", skip_images),
            ],
            STATE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_order)],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        allow_reentry=True,
    )


async def send_status_response(update: Update, queue: TelegramSheetsQueue) -> None:
    pending_count = len(queue.list_telegram_inbox(statuses=["pending"], limit=1000))
    await update.message.reply_text(
        "الحالة الحالية تمام.\n"
        f"- الشيت متصل\n- pending online orders: {pending_count}"
    )


async def send_accounts_summary(update: Update, queue: TelegramSheetsQueue) -> None:
    summary = queue.get_accounts_summary()
    debt_lines = [
        f"- {row.get('name', '')}: {row.get('balance', '') or '0'}"
        for row in summary["top_debt_clients"]
    ]
    if not debt_lines:
        debt_lines = ["- مفيش مديونيات واضحة حاليًا."]
    await update.message.reply_text(
        "\n".join(
            [
                "ملخص الحسابات:",
                f"- جاري التجهيز: {summary['under_preparation']['count']} طلب | قيمة {TelegramSheetsQueue.format_number(summary['under_preparation']['total'])}",
                f"- جاري التسليم: {summary['delivery']['count']} طلب | قيمة {TelegramSheetsQueue.format_number(summary['delivery']['total'])}",
                f"- تم التنفيذ: {summary['delivered']['count']} طلب | قيمة {TelegramSheetsQueue.format_number(summary['delivered']['total'])}",
                f"- طلبات اليوم: {summary['today_orders_count']} | قيمة {TelegramSheetsQueue.format_number(summary['today_orders_total'])}",
                f"- إجمالي المتبقي على العملاء: {TelegramSheetsQueue.format_number(summary['total_client_balance'])}",
                f"- عدد العملاء: {summary['clients_count']}",
                f"- عدد المنتجات: {summary['products_count']}",
                f"- منتجات مخزونها صفر أو أقل: {summary['low_stock_count']}",
                "أعلى 10 مديونيات:",
                *debt_lines,
            ]
        )
    )


async def send_quick_totals(update: Update, queue: TelegramSheetsQueue) -> None:
    summary = queue.get_accounts_summary()
    await update.message.reply_text(
        "ملخص سريع:\n"
        f"- طلبات اليوم: {summary['today_orders_count']}\n"
        f"- قيمة طلبات اليوم: {TelegramSheetsQueue.format_number(summary['today_orders_total'])}\n"
        f"- pending online: {summary['pending_inbox_count']}\n"
        f"- العملاء: {summary['clients_count']}\n"
        f"- المنتجات: {summary['products_count']}"
    )


async def send_debt_summary(update: Update, queue: TelegramSheetsQueue) -> None:
    summary = queue.get_accounts_summary()
    rows = summary["top_debt_clients"]
    if not rows:
        await update.message.reply_text("مفيش مديونيات على العملاء حاليًا.")
        return
    await update.message.reply_text(
        "أعلى العملاء مديونية:\n"
        + "\n".join(f"- {row.get('name', '')} | {row.get('balance', '') or '0'}" for row in rows)
    )


async def send_low_stock(update: Update, queue: TelegramSheetsQueue) -> None:
    rows = queue.list_low_stock_products(limit=20, threshold=0)
    if not rows:
        await update.message.reply_text("مفيش منتجات ناقصة مخزون حاليًا.")
        return
    await update.message.reply_text(
        "المنتجات الناقصة:\n"
        + "\n".join(f"- {row.get('name', '')} | المخزون: {row.get('stock_qty', '') or '0'}" for row in rows)
    )


async def send_order_status_group(update: Update, queue: TelegramSheetsQueue, group_name: str, empty_message: str) -> None:
    rows = queue.list_orders_by_status_group(group_name)
    if not rows:
        await update.message.reply_text(empty_message)
        return
    await update.message.reply_text(queue.format_orders_for_reply(rows))


async def send_pending_inbox(update: Update, queue: TelegramSheetsQueue, statuses: Sequence[str], empty_message: str) -> None:
    rows = queue.list_telegram_inbox(statuses=statuses, limit=15)
    if not rows:
        await update.message.reply_text(empty_message)
        return
    await update.message.reply_text(
        "منتظرة الاستيراد من تيليجرام:\n"
        + "\n".join(
            f"- {row.get('client_name', '') or DEFAULT_CLIENT_NAME} | الإجمالي: {row.get('total_amount', '') or '0'} | المتبقي: {row.get('remaining_amount', '') or '0'} | status: {row.get('status', '') or '-'} | {row.get('external_order_id', '')}"
            for row in rows
        )
    )


async def send_import_status(update: Update, queue: TelegramSheetsQueue) -> None:
    rows = queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=15)
    if not rows:
        await update.message.reply_text("مفيش حالات import ظاهرة حاليًا في telegram_inbox.")
        return
    await update.message.reply_text(
        "حالة طلبات تيليجرام:\n"
        + "\n".join(
            f"- {row.get('client_name', '') or DEFAULT_CLIENT_NAME} | status: {row.get('status', '') or '-'} | الإجمالي: {row.get('total_amount', '') or '0'} | imported_order_id: {row.get('imported_order_id', '') or '-'} | error: {row.get('error_message', '') or '-'} | {row.get('external_order_id', '')}"
            for row in rows
        )
    )


async def send_order_details(update: Update, queue: TelegramSheetsQueue, order_id: str) -> None:
    details = queue.get_order_details(order_id)
    if details is None:
        await update.message.reply_text(f"مش لاقي طلب رقم {order_id} في الشيت.")
        return
    order = details["order"]
    items = details["items"]
    lines = [
        f"طلب رقم {order.get('order_id', '')}",
        f"العميل: {order.get('client_name', '')}",
        f"الحالة: {order.get('status', '') or '-'}",
        f"الإجمالي: {order.get('total_amount', '') or '0'}",
        f"التاريخ: {order.get('date', '') or '-'}",
        f"الملاحظات: {order.get('notes', '') or '-'}",
        "العناصر:",
    ]
    if items:
        for item in items:
            lines.append(
                f"- {item.get('product_name', '')} × {item.get('qty', '') or '1'} × {item.get('price', '') or '0'} = {item.get('total', '') or '0'}"
            )
    else:
        lines.append("- مفيش عناصر ظاهرة في order_items.")
    await update.message.reply_text("\n".join(lines))


async def send_order_search(update: Update, queue: TelegramSheetsQueue, query: str) -> None:
    rows = queue.search_orders(query)
    if not rows:
        await update.message.reply_text("مش لاقي طلبات مطابقة للبحث ده.")
        return
    await update.message.reply_text(queue.format_orders_for_reply(rows))


async def send_client_info(update: Update, queue: TelegramSheetsQueue, query: str, debt_only: bool = False) -> None:
    summary = queue.get_client_summary(query)
    if summary is None:
        await update.message.reply_text("مش لاقي العميل ده في الشيت.")
        return
    client = summary["client"]
    if debt_only:
        await update.message.reply_text(
            f"مديونية {client.get('name', '')}: {client.get('balance', '') or '0'}"
        )
        return
    await update.message.reply_text(
        "\n".join(
            [
                f"اسم العميل: {client.get('name', '')}",
                f"الموبايل: {client.get('phone', '') or '-'}",
                f"النوع: {client.get('type', '') or '-'}",
                f"الرصيد: {client.get('balance', '') or '0'}",
                f"ملاحظات: {client.get('notes', '') or '-'}",
            ]
        )
    )


async def send_product_price(update: Update, queue: TelegramSheetsQueue, query: str) -> None:
    rows = queue.search_products(query, limit=5)
    if not rows:
        await update.message.reply_text("مش لاقي المنتج ده في الشيت.")
        return
    await update.message.reply_text(
        "\n".join(
            f"- {row.get('name', '')} | قطاعي: {row.get('retail_price', '') or '0'} | جملة: {row.get('wholesale_price', '') or '0'}"
            for row in rows
        )
    )


async def send_product_stock(update: Update, queue: TelegramSheetsQueue, query: str) -> None:
    rows = queue.search_products(query, limit=5)
    if not rows:
        await update.message.reply_text("مش لاقي المنتج ده في الشيت.")
        return
    await update.message.reply_text(
        "\n".join(
            f"- {row.get('name', '')} | المخزون: {row.get('stock_qty', '') or '0'}"
            for row in rows
        )
    )


async def send_product_matches(update: Update, queue: TelegramSheetsQueue, query: str) -> None:
    rows = queue.search_products(query, limit=10)
    await update.message.reply_text(queue.format_products_for_reply(rows))


async def send_last_sync(update: Update, queue: TelegramSheetsQueue) -> None:
    row = queue.get_last_sync_log()
    if row is None:
        await update.message.reply_text("مفيش sync_log ظاهر حاليًا.")
        return
    await update.message.reply_text(
        "\n".join(
            [
                "آخر تحديث:",
                f"- الوقت: {row.get('timestamp', '') or '-'}",
                f"- المستوى: {row.get('level', '') or '-'}",
                f"- النوع: {row.get('entity_type', '') or '-'}",
                f"- العملية: {row.get('action', '') or '-'}",
                f"- الرسالة: {row.get('message', '') or '-'}",
            ]
        )
    )


async def begin_smart_order_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt_only: bool = False) -> None:
    reset_smart_state(context)
    if prompt_only:
        await update.message.reply_text(
            "ابعت الطلب بالعربي الطبيعي في رسالة واحدة، مثال:\n"
            "- اية كرم جملة تابلو 30ف40\n"
            "- 01012345678 قطاعي تابلو 30ف40 2 مدفوع 50"
        )
        return
    await update.message.reply_text("ابعت تفاصيل الطلب بالطريقة اللي تريحك، وأنا هفهمه.")


def set_smart_order_draft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    draft: Dict[str, Any],
) -> None:
    draft["root_message_id"] = draft.get("root_message_id") or update.message.message_id
    draft["chat_id"] = draft.get("chat_id") or update.effective_chat.id
    _settings, queue = get_settings_and_queue()
    draft["external_order_id"] = draft.get("external_order_id") or queue.build_external_order_id(
        draft["chat_id"],
        draft["root_message_id"],
    )
    context.user_data[SMART_ORDER_KEY] = draft


async def finalize_smart_order_preview(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parse_result: Dict[str, Any],
) -> None:
    draft = parse_result["draft"]
    existing = context.user_data.get(SMART_ORDER_KEY)
    if existing and existing.get("images"):
        draft["images"] = existing["images"]
    set_smart_order_draft(update, context, draft)
    context.user_data.pop(SMART_AWAITING_KEY, None)
    prefix = f"تمام {get_display_name(update)}، فهمت الطلب كده..."
    if draft.get("type_warning"):
        prefix += f"\n{draft['type_warning']}"
    await update.message.reply_text(prefix + "\n" + build_summary_text(draft))


async def finalize_payment_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: Dict[str, Any]) -> None:
    context.user_data[SMART_PAYMENT_KEY] = draft
    context.user_data.pop(SMART_ADMIN_ACTION_KEY, None)
    await update.message.reply_text(build_payment_summary_text(draft))


async def finalize_admin_action_preview(update: Update, context: ContextTypes.DEFAULT_TYPE, draft: Dict[str, Any]) -> None:
    context.user_data[SMART_ADMIN_ACTION_KEY] = draft
    context.user_data.pop(SMART_PAYMENT_KEY, None)
    await update.message.reply_text(build_price_update_summary_text(draft))


async def handle_smart_order_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    draft = context.user_data.get(SMART_ORDER_KEY)
    if not draft:
        return False
    text = update.message.text.strip()
    if is_cancel_text(text):
        reset_smart_state(context)
        await update.message.reply_text("تم إلغاء الطلب الحالي.")
        return True
    if not is_confirm_text(text):
        return False

    _settings, queue = get_settings_and_queue()
    result = queue.queue_order(
        chat_id=draft["chat_id"],
        root_message_id=draft["root_message_id"],
        client_name=draft["client_name"],
        client_phone=draft["client_phone"],
        client_type=draft["client_type"],
        items=draft["items"],
        paid_amount=draft["paid_amount"],
        notes=draft["notes"],
        images=draft.get("images", []),
        discount=draft.get("discount", 0.0),
    )
    context.user_data[SMART_LAST_ORDER_KEY] = {
        "external_order_id": result["external_order_id"],
        "chat_id": draft["chat_id"],
    }
    reset_smart_state(context)
    if result["duplicate"]:
        await update.message.reply_text("الطلب ده كان محفوظ قبل كده أونلاين.")
        return True
    await update.message.reply_text(
        "تم حفظ الطلب أونلاين، وهينزل في البرنامج لما جهاز المحل يفتح.\n"
        f"external_order_id: {result['external_order_id']}\n"
        f"عدد الصور: {result['images_count']}"
    )
    trigger_local_import_now(_settings)
    return True


async def handle_payment_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    draft = context.user_data.get(SMART_PAYMENT_KEY)
    if not draft:
        return False
    text = update.message.text.strip()
    if is_cancel_text(text):
        context.user_data.pop(SMART_PAYMENT_KEY, None)
        await update.message.reply_text("تم إلغاء مسودة الدفعة الحالية.")
        return True
    if not is_confirm_text(text):
        return False

    _settings, queue = get_settings_and_queue()
    result = queue.queue_payment(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        client_id=draft.get("client_id", ""),
        client_name=draft.get("client_name", ""),
        client_phone=draft.get("client_phone", ""),
        amount=float(draft.get("amount", 0) or 0),
        payment_method=draft.get("payment_method", "Telegram"),
        notes=draft.get("notes", ""),
    )
    context.user_data.pop(SMART_PAYMENT_KEY, None)
    if result.get("duplicate"):
        await update.message.reply_text("مسودة الدفعة دي محفوظة قبل كده في queue.")
        return True
    await update.message.reply_text(
        "تم حفظ الدفعة في telegram_payments_queue للمراجعة والاستيراد الآمن.\n"
        f"external_payment_id: {result['external_payment_id']}"
    )
    return True


async def handle_admin_action_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    draft = context.user_data.get(SMART_ADMIN_ACTION_KEY)
    if not draft:
        return False
    text = update.message.text.strip()
    if is_cancel_text(text):
        context.user_data.pop(SMART_ADMIN_ACTION_KEY, None)
        await update.message.reply_text("تم إلغاء مسودة تعديل الأسعار.")
        return True
    if normalize_input(text) != normalize_input(SMART_PRICE_CONFIRM_TEXT):
        return False

    _settings, queue = get_settings_and_queue()
    result = queue.queue_admin_action(
        chat_id=update.effective_chat.id,
        message_id=update.message.message_id,
        action_type=draft.get("action_type", "update_product_prices_bulk"),
        target_scope=draft.get("target_scope", "products"),
        payload=draft.get("payload", {}),
        notes=draft.get("notes", ""),
    )
    context.user_data.pop(SMART_ADMIN_ACTION_KEY, None)
    if result.get("duplicate"):
        await update.message.reply_text("طلب تعديل الأسعار ده محفوظ قبل كده في queue.")
        return True
    await update.message.reply_text(
        "تم حفظ تعديل الأسعار في telegram_admin_actions_queue للمراجعة والتنفيذ المحلي الآمن.\n"
        f"external_action_id: {result['external_action_id']}"
    )
    return True


async def handle_smart_order_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    awaiting = context.user_data.get(SMART_AWAITING_KEY)
    if not awaiting:
        return False
    _settings, queue = get_settings_and_queue()
    text = update.message.text.strip()
    if is_cancel_text(text):
        reset_smart_state(context)
        await update.message.reply_text("تم إلغاء الطلب الحالي.")
        return True

    if awaiting["action"] == "need_client_type":
        normalized = normalize_input(text)
        if normalized in WHOLESALE_WORDS:
            forced_client_type = "Wholesale"
        elif normalized in RETAIL_WORDS:
            forced_client_type = "Retail"
        else:
            await update.message.reply_text("اكتب جملة أو قطاعي عشان أكمل الطلب.")
            return True
        parse_result = parse_natural_order_text(queue, awaiting["original_text"], forced_client_type=forced_client_type)
        if parse_result.get("success"):
            await finalize_smart_order_preview(update, context, parse_result)
            return True
        context.user_data[SMART_AWAITING_KEY] = parse_result
        await update.message.reply_text(parse_result["message"])
        return True

    if awaiting["action"] == "need_price":
        price_value = TelegramSheetsQueue.parse_money(text)
        if price_value is None or price_value <= 0:
            await update.message.reply_text("ابعت السعر رقماً فقط، مثال: 25")
            return True
        overrides = dict(awaiting.get("overrides", {}))
        overrides[awaiting["segment_key"]] = {"explicit_price": price_value}
        parse_result = parse_natural_order_text(
            queue,
            awaiting["original_text"],
            overrides=overrides,
            forced_client_type=awaiting.get("client_type"),
        )
        if parse_result.get("success"):
            await finalize_smart_order_preview(update, context, parse_result)
            return True
        parse_result["overrides"] = overrides
        context.user_data[SMART_AWAITING_KEY] = parse_result
        await update.message.reply_text(parse_result["message"])
        return True

    if awaiting["action"] == "need_choice":
        choice_index = TelegramSheetsQueue.parse_money(text)
        if choice_index is None or int(choice_index) < 1 or int(choice_index) > len(awaiting.get("candidates", [])):
            await update.message.reply_text("اختار رقم من القائمة اللي فوق.")
            return True
        selected_row = awaiting["candidates"][int(choice_index) - 1]["row"]
        overrides = dict(awaiting.get("overrides", {}))
        overrides[awaiting["segment_key"]] = {"forced_product_name": selected_row.get("name", "")}
        parse_result = parse_natural_order_text(
            queue,
            awaiting["original_text"],
            overrides=overrides,
            forced_client_type=awaiting.get("client_type"),
        )
        if parse_result.get("success"):
            await finalize_smart_order_preview(update, context, parse_result)
            return True
        parse_result["overrides"] = overrides
        context.user_data[SMART_AWAITING_KEY] = parse_result
        await update.message.reply_text(parse_result["message"])
        return True
    return False


def build_payment_draft_from_text(queue: TelegramSheetsQueue, text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    amounts = extract_money_values(cleaned)
    amount = amounts[-1] if amounts else None

    client_query = re.sub(r"(?:دفع|دفعت|سدد|سددت|خالص|خلص|خلصت|حسابه|حسابها|حسابهم)", " ", cleaned, flags=re.IGNORECASE)
    if amount is not None:
        client_query = re.sub(r"[0-9٠-٩]+(?:[.,٫٬][0-9٠-٩]+)?", " ", client_query)
    client_query = re.sub(r"\s+", " ", client_query).strip(" -،,")
    client = find_best_client(queue, client_query or cleaned)
    if not client:
        return {"success": False, "message": "مش لاقي العميل ده في الشيت عشان أجهز مسودة الدفعة."}

    balance_before = round(TelegramSheetsQueue.parse_money(client.get("balance", 0)) or 0.0, 2)
    if amount is None:
        if balance_before <= 0:
            return {"success": False, "message": f"رصيد {client.get('name', '')} ظاهر صفر، فمحتاج مبلغ الدفعة مكتوب صراحة."}
        amount = balance_before
    amount = round(amount, 2)
    if amount <= 0:
        return {"success": False, "message": "مبلغ الدفعة لازم يكون أكبر من صفر."}

    return {
        "success": True,
        "draft": {
            "client_id": client.get("client_id", ""),
            "client_name": client.get("name", "") or DEFAULT_CLIENT_NAME,
            "client_phone": client.get("phone", ""),
            "balance_before": balance_before,
            "amount": amount,
            "balance_after": round(balance_before - amount, 2),
            "payment_method": "Telegram",
            "notes": f"[raw_telegram_text:{cleaned}]",
        },
    }


def build_price_update_draft_from_text(queue: TelegramSheetsQueue, text: str) -> Dict[str, Any]:
    amounts = extract_money_values(text)
    if not amounts:
        return {"success": False, "message": "محتاج قيمة التعديل في الأسعار عشان أجهز المسودة."}
    delta = amounts[-1]
    normalized = normalize_input(text)

    scope_query = re.sub(r"(?:عدل|غير|زود|ارفع|اسعار|الاسعار|سعر|كلها|كل|جنيه|زيادة|نقصان)", " ", text, flags=re.IGNORECASE)
    scope_query = re.sub(r"[0-9٠-٩]+(?:[.,٫٬][0-9٠-٩]+)?", " ", scope_query)
    scope_query = re.sub(r"\s+", " ", scope_query).strip()
    if "تابلو" in normalized:
        scope_query = "تابلو"
    rows = queue.search_products(scope_query, limit=25)
    if not rows and ("تابلو" in normalized or "تابلوهات" in normalized):
        rows = queue.search_products("تابلو", limit=25)
    if not rows:
        return {"success": False, "message": "مش لاقي منتجات مطابقة لتعديل الأسعار ده."}

    update_wholesale = "جمله" in normalized or "جملة" in text or "wholesale" in normalized
    update_retail = "قطاعي" in normalized or "retail" in normalized
    if not update_wholesale and not update_retail:
        update_wholesale = True
        update_retail = True

    products = []
    for row in rows:
        retail_price = TelegramSheetsQueue.parse_money(row.get("retail_price", 0)) or 0.0
        wholesale_price = TelegramSheetsQueue.parse_money(row.get("wholesale_price", 0)) or 0.0
        product_row = dict(row)
        if update_retail:
            product_row["new_retail_price"] = TelegramSheetsQueue.format_number(round(retail_price + delta, 2))
        if update_wholesale:
            product_row["new_wholesale_price"] = TelegramSheetsQueue.format_number(round(wholesale_price + delta, 2))
        products.append(product_row)

    payload = {
        "delta": delta,
        "scope_query": scope_query,
        "update_retail": update_retail,
        "update_wholesale": update_wholesale,
        "products": [
            {
                "product_id": row.get("product_id", ""),
                "name": row.get("name", ""),
                "old_retail_price": row.get("retail_price", ""),
                "old_wholesale_price": row.get("wholesale_price", ""),
                "new_retail_price": row.get("new_retail_price", row.get("retail_price", "")),
                "new_wholesale_price": row.get("new_wholesale_price", row.get("wholesale_price", "")),
            }
            for row in products
        ],
        "raw_text": text.strip(),
    }
    mode_label = "قطاعي + جملة"
    if update_retail and not update_wholesale:
        mode_label = "قطاعي فقط"
    elif update_wholesale and not update_retail:
        mode_label = "جملة فقط"

    return {
        "success": True,
        "draft": {
            "action_type": "update_product_prices_bulk" if len(products) > 1 else "update_product_price",
            "target_scope": scope_query or "products",
            "price_mode_label": mode_label,
            "products": products,
            "payload": payload,
            "notes": "Queued from Telegram for safe local review.",
        },
    }


async def handle_smart_message_router(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    settings, queue = get_settings_and_queue()
    if not settings.ai_enabled:
        await update.message.reply_text(AI_DISABLED_MESSAGE)
        return

    route_result = await asyncio.to_thread(classify_message_intent, settings, text)
    if not route_result.get("success"):
        LOGGER.warning("Smart router classification failed: %s", route_result)
        await update.message.reply_text("مش واضح لي نوع الرسالة دلوقتي. جرّب تعيدها بصياغة أقصر.")
        return

    intent = route_result["intent"]
    if intent == "create_order" or intent == "order_intent":
        extracted = await asyncio.to_thread(extract_order_json, settings, text)
        if not extracted.get("success"):
            LOGGER.warning("Order extraction failed: %s", extracted)
            await update.message.reply_text("ماقدرتش أفهم الطلب بشكل آمن. ابعته تاني بصياغة أوضح.")
            return
        draft_result = resolve_extracted_order_to_draft(queue, extracted.get("order", {}), text)
        if not draft_result.get("success"):
            await update.message.reply_text(draft_result["message"])
            return
        await finalize_smart_order_preview(update, context, draft_result)
        return

    if intent == "record_payment":
        draft_result = build_payment_draft_from_text(queue, text)
        if not draft_result.get("success"):
            await update.message.reply_text(draft_result["message"])
            return
        await finalize_payment_preview(update, context, draft_result["draft"])
        return

    if intent == "product_lookup":
        if "جملة" in text or "wholesale" in normalize_input(text):
            query = re.sub(r"هات|أسعار|اسعار|الأسعار|الاسعار|بالجملة|جملة", " ", text, flags=re.IGNORECASE).strip()
            rows = queue.search_products(query or text, limit=10)
            if not rows:
                await update.message.reply_text("مش لاقي منتجات مطابقة للسؤال ده.")
                return
            await update.message.reply_text("\n".join(f"- {row.get('name', '')} | جملة: {row.get('wholesale_price', '') or '0'}" for row in rows))
            return
        query = re.sub(r"هات|سعر|أسعار|اسعار|الأسعار|الاسعار|منتج|عندك|فيه", " ", text, flags=re.IGNORECASE).strip()
        await send_product_price(update, queue, query or text)
        return

    if intent in {"update_product_price", "update_product_prices_bulk"}:
        draft_result = build_price_update_draft_from_text(queue, text)
        if not draft_result.get("success"):
            await update.message.reply_text(draft_result["message"])
            return
        await finalize_admin_action_preview(update, context, draft_result["draft"])
        return

    if intent == "client_balance_query":
        query = re.sub(r"(?:رصيد|حساب|على|عميل)", " ", text, flags=re.IGNORECASE).strip()
        await send_client_info(update, queue, query or text, debt_only=True)
        return

    if intent == "receivables_summary":
        summary = queue.get_accounts_summary()
        pending_rows = queue.list_telegram_inbox(statuses=["pending"], limit=20)
        pending_remaining = round(sum(TelegramSheetsQueue.parse_money(row.get("remaining_amount", 0)) or 0 for row in pending_rows), 2)
        lines = [
            f"إجمالي الفلوس اللي لينا بره: {TelegramSheetsQueue.format_number(summary['total_client_balance'])}",
            f"طلبات تيليجرام المنتظرة المتبقي فيها: {TelegramSheetsQueue.format_number(pending_remaining)}",
        ]
        if "ما تسلمتش" in text or "ما اتسلمتش" in text or "غير delivered" in normalize_input(text):
            lines.append("تنبيه: المتبقي لكل طلب داخل orders مش ظاهر بالكامل في الشيت الحالي، فاعتمدت على أرصدة العملاء + pending تيليجرام.")
        if summary["top_debt_clients"]:
            lines.append("أعلى العملاء مديونية:")
            lines.extend(f"- {row.get('name', '')} | {row.get('balance', '') or '0'}" for row in summary["top_debt_clients"][:10])
        await update.message.reply_text("\n".join(lines))
        return

    if intent == "orders_status_query":
        result = await asyncio.to_thread(ask_sheet_ai, settings, queue, text)
        if not result.get("success"):
            LOGGER.warning("Orders status question failed: %s", result)
            await update.message.reply_text(AI_DISABLED_MESSAGE)
            return
        await update.message.reply_text(result["content"])
        return

    if intent == "partial_search":
        query = re.sub(r"(?:دور على|ابحث عن|هات أي حاجة فيها|عندك منتج باسم|عندك منتج|فيه منتج باسم|فيه منتج)", " ", text, flags=re.IGNORECASE).strip()
        await update.message.reply_text(build_partial_search_reply(queue, query or text))
        return

    if intent == "data_question":
        result = await asyncio.to_thread(ask_sheet_ai, settings, queue, text)
        if not result.get("success"):
            LOGGER.warning("Data question failed: %s", result)
            await update.message.reply_text(AI_DISABLED_MESSAGE)
            return
        await update.message.reply_text(result["content"])
        return

    if intent == "normal_ai_question":
        result = await asyncio.to_thread(ask_general_assistant, settings, text)
        if not result.get("success"):
            LOGGER.warning("General AI question failed: %s", result)
            await update.message.reply_text(AI_DISABLED_MESSAGE)
            return
        await update.message.reply_text(result["content"])
        return

    await update.message.reply_text("محتاج توضيح بسيط: تقصد تسجيل طلب، ولا سؤال عن بيانات، ولا سؤال عام؟")


async def handle_plain_text_alias(update: Update, context: ContextTypes.DEFAULT_TYPE, normalized: str) -> bool:
    alias = COMMAND_ALIASES.get(normalized)
    if alias == "start":
        await start_command(update, context)
        return True
    if alias == "help":
        await help_command(update, context)
        return True
    if alias == "products":
        context.args = []
        await products_command(update, context)
        return True
    if alias == "client":
        await update.message.reply_text("اكتب: عميل + اسم العميل أو رقمه.")
        return True
    if alias == "orders_today":
        await orders_today_command(update, context)
        return True
    if normalized == "pending" or normalized == "منتظرة" or normalized == "طلبات منتظرة":
        await pending_command(update, context)
        return True
    if normalized == "import status" or normalized == "حالة الاستيراد" or normalized == "حالات الاستيراد":
        await import_status_command(update, context)
        return True
    if alias == "neworder_alias":
        await begin_smart_order_flow(update, context, prompt_only=True)
        return True
    if alias == "cancel_alias":
        await cancel_command(update, context)
        return True
    if alias == "guide":
        await update.message.reply_text(build_help_text())
        return True
    return False


async def handle_operational_text(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, normalized: str) -> bool:
    _settings, queue = get_settings_and_queue()

    if normalized in {"طلبات", "طلبات التجهيز"}:
        await send_order_status_group(update, queue, "under_preparation", "مفيش طلبات جاري التجهيز حاليًا.")
        return True
    if normalized == "طلبات جاهزه" or normalized == "طلبات جاهزة":
        await send_order_status_group(update, queue, "ready", "مفيش طلبات جاهزة حاليًا.")
        return True
    if normalized == "طلبات التسليم":
        await send_order_status_group(update, queue, "delivery", "مفيش طلبات جاري تسليمها حاليًا.")
        return True
    if normalized == "طلبات منفذه" or normalized == "طلبات منفذة":
        await send_order_status_group(update, queue, "delivered", "مفيش طلبات منفذة حاليًا.")
        return True
    if normalized == "طلبات معلقه" or normalized == "طلبات معلقة" or normalized == "انتظار":
        await send_pending_inbox(update, queue, ["pending"], "مفيش طلبات معلقة حاليًا.")
        return True
    if normalized in {"الطلبات الحالية", "طلبات حالية", "الطلبات تحت التجهيز", "طلبات تحت التجهيز", "فيه طلبات جديدة", "طلبات جديدة"}:
        result = ask_sheet_ai(_settings, queue, text)
        if not result.get("success"):
            await update.message.reply_text(AI_DISABLED_MESSAGE)
            return True
        await update.message.reply_text(result["content"])
        return True
    if normalized == "فشل":
        await send_pending_inbox(update, queue, ["failed"], "مفيش طلبات failed حاليًا.")
        return True
    if normalized in {"طلبات اليوم", "طلبات النهارده", "النهارده"}:
        await orders_today_command(update, context)
        return True
    if normalized in {"حسابات", "الحسابات"}:
        await send_accounts_summary(update, queue)
        return True
    if normalized == "اجمالي":
        await send_quick_totals(update, queue)
        return True
    if normalized == "مبيعات اليوم":
        summary = queue.get_accounts_summary()
        await update.message.reply_text(
            f"طلبات اليوم: {summary['today_orders_count']}\n"
            f"قيمة طلبات اليوم: {TelegramSheetsQueue.format_number(summary['today_orders_total'])}"
        )
        return True
    if normalized == "مديونيات":
        await send_debt_summary(update, queue)
        return True
    if normalized in {"ناقص مخزون", "منتجات ناقصه", "منتجات ناقصة"}:
        await send_low_stock(update, queue)
        return True
    if normalized == "الحاله" or normalized == "الحالة":
        await send_status_response(update, queue)
        return True
    if normalized == "اخر طلبات":
        await update.message.reply_text(queue.format_orders_for_reply(queue.list_recent_orders(limit=10)))
        return True
    if normalized == "اخر عملاء":
        await update.message.reply_text(queue.format_clients_for_reply(queue.list_recent_clients(limit=10)))
        return True
    if normalized == "تحديث":
        await send_last_sync(update, queue)
        return True

    order_match = re.match(r"^طلب رقم\s+(\d+)$", text.strip(), re.IGNORECASE)
    if order_match:
        await send_order_details(update, queue, order_match.group(1))
        return True

    search_order_match = re.match(r"^بحث طلب\s+(.+)$", text.strip(), re.IGNORECASE)
    if search_order_match:
        await send_order_search(update, queue, search_order_match.group(1).strip())
        return True

    client_match = re.match(r"^عميل\s+(.+)$", text.strip(), re.IGNORECASE)
    if client_match:
        await send_client_info(update, queue, client_match.group(1).strip())
        return True

    debt_match = re.match(r"^مديونيه\s+(.+)$|^مديونية\s+(.+)$", text.strip(), re.IGNORECASE)
    if debt_match:
        query = debt_match.group(1) or debt_match.group(2) or ""
        await send_client_info(update, queue, query.strip(), debt_only=True)
        return True

    product_match = re.match(r"^منتج\s+(.+)$", text.strip(), re.IGNORECASE)
    if product_match:
        await send_product_matches(update, queue, product_match.group(1).strip())
        return True

    price_match = re.match(r"^سعر\s+(.+)$", text.strip(), re.IGNORECASE)
    if price_match:
        await send_product_price(update, queue, price_match.group(1).strip())
        return True

    stock_match = re.match(r"^مخزون\s+(.+)$", text.strip(), re.IGNORECASE)
    if stock_match:
        await send_product_stock(update, queue, stock_match.group(1).strip())
        return True

    return False


async def handle_smart_natural_order(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> bool:
    _settings, queue = get_settings_and_queue()
    parse_result = parse_natural_order_text(queue, text)
    if parse_result.get("success"):
        await finalize_smart_order_preview(update, context, parse_result)
        return True

    action = parse_result.get("action")
    if action in {"need_client_type", "need_price", "need_choice"}:
        parse_result["overrides"] = parse_result.get("overrides", {})
        context.user_data[SMART_AWAITING_KEY] = parse_result
        context.user_data.setdefault(
            SMART_ORDER_KEY,
            {
                "root_message_id": update.message.message_id,
                "chat_id": update.effective_chat.id,
                "images": [],
            },
        )
        reply = parse_result["message"]
        if action == "need_choice":
            candidates = parse_result.get("candidates", [])
            if candidates:
                lines = [reply]
                for index, candidate in enumerate(candidates, start=1):
                    row = candidate["row"]
                    lines.append(f"{index}. {row.get('name', '')}")
                reply = "\n".join(lines)
        await update.message.reply_text(reply)
        return True

    return False


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if await handle_admin_action_confirmation(update, context):
        return
    if await handle_payment_confirmation(update, context):
        return
    if await handle_smart_order_confirmation(update, context):
        return
    if await handle_smart_order_followup(update, context):
        return
    await handle_smart_message_router(update, context, text)


async def handle_smart_order_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, queue = get_settings_and_queue()
    if not is_allowed_user(settings, update):
        await reject_unauthorized(update, settings)
        return

    draft = context.user_data.get(SMART_ORDER_KEY)

    photo = update.message.photo[-1] if update.message.photo else None
    document = update.message.document if update.message.document else None
    image_payload = None
    if photo:
        image_payload = {
            "message_id": update.message.message_id,
            "item_index": "",
            "telegram_file_id": photo.file_id,
            "original_name": f"photo_{update.message.message_id}.jpg",
            "mime_type": "image/jpeg",
            "caption": update.message.caption or "",
        }
    elif document:
        image_payload = {
            "message_id": update.message.message_id,
            "item_index": "",
            "telegram_file_id": document.file_id,
            "original_name": document.file_name or f"image_{update.message.message_id}",
            "mime_type": document.mime_type or "image/*",
            "caption": update.message.caption or "",
        }

    if not image_payload:
        await update.message.reply_text("الصورة ماوصلتش بشكل واضح. ابعتها تاني.")
        return

    if draft:
        draft.setdefault("images", []).append(image_payload)
        context.user_data[SMART_ORDER_KEY] = draft
        external_order_id = draft.get("external_order_id")
        if external_order_id:
            image_result = queue.append_telegram_image(external_order_id, image_payload)
            if image_result.get("duplicate"):
                await update.message.reply_text(
                    f"الصورة مرتبطة بالفعل بالطلب الحالي. عدد الصور في المسودة: {len(draft['images'])}"
                )
                return
        await update.message.reply_text(
            f"تمام، ربطت الصورة بالطلب الحالي. عدد الصور في المسودة: {len(draft['images'])}"
        )
        return

    last_order = context.user_data.get(SMART_LAST_ORDER_KEY)
    if last_order and str(last_order.get("chat_id")) == str(update.effective_chat.id):
        image_result = queue.append_telegram_image(last_order["external_order_id"], image_payload)
        if image_result.get("duplicate"):
            await update.message.reply_text("الصورة دي مضافة بالفعل على آخر طلب مؤكد.")
            return
        await update.message.reply_text(
            f"تمام، ربطت الصورة بآخر طلب مؤكد.\nexternal_order_id: {last_order['external_order_id']}"
        )
        return

    await update.message.reply_text("ابعت تفاصيل الطلب الأول، وبعدها ابعت الصور.")


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("orders_today", orders_today_command))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(CommandHandler("import_status", import_status_command))
    application.add_handler(CommandHandler("sync_status", sync_status_command))
    application.add_handler(CommandHandler("import_now", import_now_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("balances", balances_command))
    application.add_handler(CommandHandler("receivables", receivables_command))
    application.add_handler(CommandHandler("prices", prices_command))
    application.add_handler(CommandHandler("client", client_command))
    application.add_handler(CommandHandler("products", products_command))
    application.add_handler(CommandHandler("ask", ask_ai_command))
    application.add_handler(CommandHandler("ai", ask_ai_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(build_conversation_handler())
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_smart_order_image))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text))


def build_application() -> Application:
    settings, _queue = get_settings_and_queue()
    application = ApplicationBuilder().token(settings.bot_token).concurrent_updates(False).build()
    register_handlers(application)
    return application


async def telegram_healthcheck() -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    queue_info = queue.healthcheck()
    application = ApplicationBuilder().token(settings.bot_token).build()
    await application.initialize()
    try:
        bot_info = await application.bot.get_me()
    finally:
        await application.shutdown()
    return {
        "bot_id": bot_info.id,
        "bot_username": bot_info.username,
        "queue": queue_info,
        "ai_enabled": settings.ai_enabled,
        "ai_provider": settings.ai_provider,
        "openrouter_model": settings.openrouter_model,
    }


async def _post_init_stop_timer(application: Application) -> None:
    stop_after = application.bot_data.get("stop_after_seconds", 0)
    if not stop_after:
        return

    async def stop_later() -> None:
        await asyncio.sleep(stop_after)
        application.stop_running()

    asyncio.get_running_loop().create_task(stop_later())


def run_polling_for_seconds(seconds: int) -> None:
    settings, _queue = get_settings_and_queue()
    builder = ApplicationBuilder().token(settings.bot_token).concurrent_updates(False)
    if seconds > 0:
        builder = builder.post_init(_post_init_stop_timer)
    application = builder.build()
    application.bot_data["stop_after_seconds"] = seconds
    register_handlers(application)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        application.run_polling(drop_pending_updates=False, close_loop=True)
    finally:
        asyncio.set_event_loop(None)


def smoke_test_handlers() -> Dict[str, str]:
    settings, _queue = get_settings_and_queue()
    fake_user_id = settings.owner_id or 123456789
    return {
        "start_preview": settings.authorization_notice(fake_user_id),
        "help_preview": build_help_text().splitlines()[0],
    }


def smoke_test_ai(question: str) -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    if not settings.ai_enabled:
        return {
            "question": question,
            "success": False,
            "reply_preview": AI_DISABLED_MESSAGE,
        }
    result = ask_sheet_ai(settings, queue, question)
    if not result.get("success"):
        result["reply_preview"] = AI_DISABLED_MESSAGE
    else:
        result["reply_preview"] = result.get("content", "")
    return {"question": question, **result}


def test_openrouter() -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    question = "ايه أهم المنتجات الموجودة في الشيت دلوقتي؟"
    return ask_sheet_ai(settings, queue, question)


def test_ai_context() -> Dict[str, Any]:
    _settings, queue = get_settings_and_queue()
    return {
        "products_question": build_sheet_context("ايه اسعار تابلو", queue),
        "orders_today_question": build_sheet_context("ايه طلبات اليوم", queue),
    }


def smoke_test_smart_read() -> Dict[str, Any]:
    _settings, queue = get_settings_and_queue()
    return {
        "products_sample_count": len(queue.search_products("تابلو", limit=5)),
        "clients_sample_count": len(queue.search_clients("", limit=5)),
        "orders_today_count": len(queue.list_orders_for_today()),
        "recent_orders_count": len(queue.list_recent_orders(limit=5)),
    }


def smoke_test_smart_parser() -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    samples = [
        "العميل أحمد كريم جملة طلب 2 منديل كتب كتاب طباعة بسعر 80 والمدفوع 50",
        "سجل طلب لمحمد 01012345678 قطاعي مج عادي عدد 3 وصورة هبعتها بعدين",
        "مين العملاء اللي عليهم فلوس؟",
    ]
    results = {}
    for sample in samples:
        route = classify_message_intent(settings, sample)
        row: Dict[str, Any] = {"route": route}
        if route.get("success") and route.get("intent") == "order_intent":
            extracted = extract_order_json(settings, sample)
            row["extracted"] = extracted
            if extracted.get("success"):
                row["draft"] = resolve_extracted_order_to_draft(queue, extracted.get("order", {}), sample)
        elif route.get("success") and route.get("intent") == "data_question":
            row["answer_preview"] = ask_sheet_ai(settings, queue, sample)
        results[sample] = row
    return results


def smoke_test_smart_confirm() -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    sample = "سجل طلب لمحمد 01012345678 قطاعي مج عادي عدد 1 والمدفوع 0"
    extracted = extract_order_json(settings, sample)
    if not extracted.get("success"):
        return extracted
    drafted = resolve_extracted_order_to_draft(queue, extracted.get("order", {}), sample)
    if not drafted.get("success"):
        return drafted
    draft = drafted["draft"]
    seed = int(time.time())
    result = queue.queue_order(
        chat_id=settings.owner_id or 999000111,
        root_message_id=seed,
        client_name=draft["client_name"],
        client_phone=draft["client_phone"],
        client_type=draft["client_type"],
        items=draft["items"],
        paid_amount=draft["paid_amount"],
        notes=draft["notes"],
        images=[],
        discount=draft["discount"],
    )
    return {
        "sample": sample,
        "queue_result": result,
    }


def smoke_test_pending() -> Dict[str, Any]:
    _settings, queue = get_settings_and_queue()
    return {
        "command": "/pending",
        "rows": queue.list_telegram_inbox(statuses=["pending"], limit=15),
    }


def smoke_test_import_status() -> Dict[str, Any]:
    _settings, queue = get_settings_and_queue()
    return {
        "command": "/import_status",
        "rows": queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=15),
    }


def smoke_test_sync_status() -> Dict[str, Any]:
    _settings, queue = get_settings_and_queue()
    return {
        "command": "/sync_status",
        "summary": queue.get_telegram_sync_status_summary(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Arabic POS Telegram bot for Elnagar POS.")
    parser.add_argument("--healthcheck", action="store_true", help="Validate Telegram token and Google Sheet access.")
    parser.add_argument("--poll-seconds", type=int, default=0, help="Run polling and auto-stop after N seconds.")
    parser.add_argument("--smoke-test-handlers", action="store_true", help="Preview /start and /help responses locally.")
    parser.add_argument("--smoke-test-queue", action="store_true", help="Create a demo queue row in telegram_inbox and one image row.")
    parser.add_argument("--smoke-test-ai", help="Send one AI prompt through the configured provider using Google Sheet context.")
    parser.add_argument("--smoke-test-smart-read", action="store_true", help="Read products, clients, and orders from Google Sheets.")
    parser.add_argument("--smoke-test-smart-parser", action="store_true", help="Run parser samples for natural Arabic orders.")
    parser.add_argument("--smoke-test-smart-confirm", action="store_true", help="Write one confirm-style test order to telegram_inbox only.")
    parser.add_argument("--smoke-test-pending", action="store_true", help="Preview rows used by /pending.")
    parser.add_argument("--smoke-test-import-status", action="store_true", help="Preview rows used by /import_status.")
    parser.add_argument("--smoke-test-sync-status", action="store_true", help="Preview summary used by /sync_status.")
    parser.add_argument("--test-openrouter", action="store_true", help="Run one OpenRouter question using limited Google Sheet context.")
    parser.add_argument("--test-ai-context", action="store_true", help="Print the limited Google Sheet contexts used for AI.")
    return parser.parse_args()


def run_queue_smoke_test() -> Dict[str, Any]:
    settings, queue = get_settings_and_queue()
    seed = int(time.time())
    parsed = queue.parse_items_text("Test Product x 1 @ 10", "Retail")
    result = queue.queue_order(
        chat_id=999000111,
        root_message_id=seed,
        client_name="Telegram Queue Smoke Test",
        client_phone="01000000000",
        client_type="Retail",
        items=parsed["items"],
        paid_amount=0.0,
        notes="Automated smoke test row. Queue only.",
        images=[
            {
                "message_id": seed + 1,
                "item_index": 0,
                "telegram_file_id": "smoke-test-file-id",
                "original_name": "smoke_test.jpg",
                "mime_type": "image/jpeg",
                "caption": "Smoke test image",
            }
        ],
    )
    return result


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = parse_args()
    try:
        if args.healthcheck:
            print(json.dumps(asyncio.run(telegram_healthcheck()), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_handlers:
            print(json.dumps(smoke_test_handlers(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_queue:
            print(json.dumps(run_queue_smoke_test(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_ai:
            print(json.dumps(smoke_test_ai(args.smoke_test_ai), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_smart_read:
            print(json.dumps(smoke_test_smart_read(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_smart_parser:
            print(json.dumps(smoke_test_smart_parser(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_smart_confirm:
            print(json.dumps(smoke_test_smart_confirm(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_pending:
            print(json.dumps(smoke_test_pending(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_import_status:
            print(json.dumps(smoke_test_import_status(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke_test_sync_status:
            print(json.dumps(smoke_test_sync_status(), ensure_ascii=False, indent=2))
            return 0
        if args.test_openrouter:
            print(json.dumps(test_openrouter(), ensure_ascii=False, indent=2))
            return 0
        if args.test_ai_context:
            print(json.dumps(test_ai_context(), ensure_ascii=False, indent=2))
            return 0
        run_polling_for_seconds(args.poll_seconds)
        return 0
    except ConfigError as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        LOGGER.exception("Telegram bot failed")
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
