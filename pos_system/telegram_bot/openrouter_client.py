from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List

from config import TelegramBotSettings
from sheets_queue import TelegramSheetsQueue


OPENROUTER_TIMEOUT_SECONDS = 90
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 700
MAX_PRODUCTS = 50
MAX_ORDERS = 20
MAX_CLIENTS = 10
MAX_ORDER_ITEMS = 20
MAX_PENDING = 10

SYSTEM_PROMPT = (
    "أنت مساعد حسابات ومبيعات خاص بمحل Elnagar Print. "
    "أجب بالعربية المصرية المختصرة والواضحة. "
    "اعتمد فقط على البيانات المرسلة من Google Sheet. "
    "لو السؤال عن الطلبات الحالية أو الطلبات تحت التجهيز أو الطلبات الجديدة، "
    "ففرّق بوضوح بين: دخلت البرنامج، ومنتظرة الاستيراد من تيليجرام. "
    "لو وُجدت بيانات من orders وtelegram_inbox فاذكر القسمين بوضوح. "
    "لو المعلومة غير موجودة أو البيانات غير كافية، قل ذلك بوضوح. "
    "لا تخترع أرقام أو ديون أو طلبات أو منتجات."
)
ROUTER_SYSTEM_PROMPT = (
    "أنت مصنف نوايا لرسائل مالك بوت Elnagar POS. "
    "أعد JSON فقط بدون أي شرح. "
    "intent يجب أن تكون واحدة من: create_order, record_payment, product_lookup, update_product_price, update_product_prices_bulk, client_balance_query, receivables_summary, orders_status_query, partial_search, data_question, normal_ai_question, unknown. "
    "اختر create_order إذا كانت الرسالة تصف طلب عميل أو تسجيل طلب أو تفاصيل منتجات/مدفوع/نوع عميل. "
    "اختر record_payment إذا كانت الرسالة عن دفعة عميل أو تسوية حسابه أو أنه خلص/خالص. "
    "اختر product_lookup إذا كانت الرسالة عن سعر منتج أو توفره أو البحث عن منتج بعينه. "
    "اختر update_product_price أو update_product_prices_bulk إذا كانت الرسالة تطلب تعديل أسعار. "
    "اختر client_balance_query إذا كانت الرسالة عن رصيد عميل معين. "
    "اختر receivables_summary إذا كانت الرسالة عن إجمالي الفلوس اللي لينا أو العملاء اللي عليهم فلوس. "
    "اختر orders_status_query إذا كانت الرسالة عن حالة الطلبات الحالية أو الجديدة أو تحت التجهيز أو الجاهزة. "
    "اختر partial_search إذا كانت الرسالة تطلب بحثًا جزئيًا مثل: دور على، هات أي حاجة فيها. "
    "اختر data_question إذا كانت الرسالة تسأل عن بيانات موجودة في Google Sheet مثل العملاء أو الديون أو المنتجات أو الأسعار أو الطلبات. "
    "اختر normal_ai_question إذا كانت الرسالة سؤال عام أو طلب مساعدة عام لا يحتاج بيانات فعلية من الشيت. "
    "اختر unknown إذا كانت الرسالة ناقصة جدًا أو غامضة."
)
ORDER_EXTRACTION_SYSTEM_PROMPT = (
    "أنت تستخرج طلبات عملاء من رسالة عربية حرة لصالح Elnagar POS. "
    "أعد JSON فقط وبنفس هذا الشكل دون أي نص إضافي: "
    '{"intent":"create_order","client_name":"","client_phone":"","client_type":"Retail أو Wholesale","items":[{"product_name":"","qty":1,"unit_price":null,"notes":"","needs_review":false}],"paid_amount":0,"discount":0,"notes":"","missing_fields":[]}. '
    "استخرج فقط ما هو مذكور صراحة أو مستنتج بشكل قوي جدًا. "
    "إذا لم يُذكر نوع العميل بوضوح فاجعله Retail وضع client_type في missing_fields. "
    "إذا لم يذكر اسم العميل اتركه فارغًا وضع client_name في missing_fields. "
    "إذا لم يذكر رقم العميل اتركه فارغًا ولا تعتبره خطأ. "
    "إذا ذكر سعرًا صريحًا لمنتج ضعه في unit_price، وإلا اجعله null. "
    "إذا كان المنتج أو الكمية غير واضحة ضع needs_review=true على هذا المنتج. "
    "لو لا توجد منتجات واضحة فأعد items فارغة وضع items في missing_fields."
)
GENERAL_ASSISTANT_PROMPT = (
    "أنت مساعد Elnagar POS. "
    "رد بالعربية المصرية المختصرة والواضحة. "
    "لا تختلق بيانات عن النظام أو العملاء أو الطلبات أو المنتجات. "
    "لو السؤال يحتاج بيانات فعلية من Google Sheet أو النظام ولم تُعطَ لك، قل ذلك بوضوح."
)

PRODUCT_KEYWORDS = {"منتج", "سعر", "اسعار", "الاسعار", "مخزون", "المنتجات", "products"}
CLIENT_KEYWORDS = {"عميل", "مديونيه", "مديونية", "رصيد"}
ORDER_KEYWORDS = {"طلب", "طلبات", "بحث طلب"}
PAYMENT_KEYWORDS = {"دفع", "دفعت", "دافع", "سدد", "سددت", "خالص", "خلص", "خلصت", "حسابه", "حسابها"}
PRICE_UPDATE_KEYWORDS = {"عدل سعر", "عدل أسعار", "غير سعر", "غير أسعار", "زود سعر", "زود أسعار", "ارفع سعر", "ارفع أسعار"}
SEARCH_KEYWORDS = {"دور على", "ابحث عن", "هات أي حاجة فيها", "عندك منتج", "فيه منتج", "اسم كذا"}
RECEIVABLES_KEYWORDS = {"الفلوس اللي لينا", "لينا بره", "مين العملاء اللي عليهم فلوس", "العملاء اللي عليهم فلوس", "رصيد"}
CURRENT_ORDER_MARKERS = {
    "الطلبات الحالية",
    "طلبات حالية",
    "ما هي الطلبات الحالية",
    "ما الطلبات الحالية",
    "الطلبات تحت التجهيز",
    "طلبات تحت التجهيز",
    "ما الطلبات تحت التجهيز",
    "فيه طلبات جديدة",
    "هل فيه طلبات جديدة",
    "طلبات جديدة",
    "طلبات معلقة",
}


def _normalize_question_for_rules(question: str) -> str:
    return TelegramSheetsQueue.normalize_text(question)


def _classify_with_rules(message_text: str) -> str:
    normalized = _normalize_question_for_rules(message_text)
    if not normalized:
        return "unknown"

    normalized_price_update_keywords = {TelegramSheetsQueue.normalize_text(keyword) for keyword in PRICE_UPDATE_KEYWORDS}
    normalized_search_keywords = {TelegramSheetsQueue.normalize_text(keyword) for keyword in SEARCH_KEYWORDS}
    normalized_receivables_keywords = {TelegramSheetsQueue.normalize_text(keyword) for keyword in RECEIVABLES_KEYWORDS}

    if any(keyword in normalized for keyword in normalized_price_update_keywords) or (
        any(token in normalized for token in {"عدل", "غير", "زود", "ارفع"})
        and any(token in normalized for token in {"سعر", "اسعار"})
    ):
        if "كل" in normalized or "كلها" in normalized or "جميع" in normalized:
            return "update_product_prices_bulk"
        return "update_product_price"

    if any(keyword in normalized for keyword in PAYMENT_KEYWORDS):
        return "record_payment"

    if any(keyword in normalized for keyword in normalized_search_keywords):
        return "partial_search"

    if any(keyword in normalized for keyword in normalized_receivables_keywords):
        if "عميل" in normalized or "حساب " in normalized:
            return "client_balance_query"
        return "receivables_summary"

    normalized_current_markers = {TelegramSheetsQueue.normalize_text(marker) for marker in CURRENT_ORDER_MARKERS}
    if any(marker in normalized for marker in normalized_current_markers):
        return "orders_status_query"

    if any(keyword in normalized for keyword in PRODUCT_KEYWORDS):
        return "product_lookup"

    if any(keyword in normalized for keyword in ORDER_KEYWORDS):
        return "orders_status_query"

    if any(token in normalized for token in {"جملة", "قطاعي", "مدفوع", "خصم", "طلب"}) and any(ch.isdigit() for ch in message_text):
        return "create_order"

    return ""


def _extract_query_text(question: str, prefix_pattern: str) -> str:
    match = re.search(prefix_pattern, question, re.IGNORECASE)
    if not match:
        return ""
    return (match.group(1) or "").strip()


def _compact_rows(rows: List[Dict[str, str]], fields: List[str]) -> List[Dict[str, str]]:
    compact = []
    for row in rows:
        compact.append({field: row.get(field, "") for field in fields})
    return compact


def _is_generic_products_question(normalized_question: str, extracted_query: str) -> bool:
    if extracted_query.strip():
        return False
    generic_markers = {
        "المنتجات",
        "منتجات",
        "products",
        "available",
        "متاح",
        "المتاح",
        "الموجود",
        "الموجوده",
        "الموجودة",
        "حاليا",
        "دلوقتي",
        "ايه",
        "ما هي",
    }
    return any(marker in normalized_question for marker in generic_markers)


def build_sheet_context(question: str, queue: TelegramSheetsQueue) -> Dict[str, Any]:
    normalized = queue.normalize_text(question)
    context: Dict[str, Any] = {
        "question": question.strip(),
        "matched_sections": [],
    }

    order_id_match = re.search(r"(?:طلب رقم|order)\s*(\d+)", question, re.IGNORECASE)
    client_query = ""
    product_query = ""
    order_search_query = ""
    partial_search_query = ""

    if any(keyword in normalized for keyword in CLIENT_KEYWORDS):
        client_query = (
            _extract_query_text(question, r"(?:عميل|مديونيه|مديونية|رصيد)\s+(.+)$")
            or question.strip()
        )

    if any(keyword in normalized for keyword in PRODUCT_KEYWORDS):
        extracted_product_query = _extract_query_text(question, r"(?:منتج|سعر|اسعار|الاسعار|مخزون)\s+(.+)$")
        if _is_generic_products_question(normalized, extracted_product_query):
            product_query = ""
        else:
            product_query = extracted_product_query or question.strip()

    if any(keyword in normalized for keyword in ORDER_KEYWORDS):
        order_search_query = (
            _extract_query_text(question, r"(?:بحث طلب|طلب)\s+(.+)$")
            or question.strip()
        )

    if any(keyword in normalized for keyword in {queue.normalize_text(value) for value in SEARCH_KEYWORDS}):
        partial_search_query = (
            _extract_query_text(question, r"(?:دور على|ابحث عن|هات أي حاجة فيها|عندك منتج باسم|عندك منتج|فيه منتج باسم|فيه منتج)\s+(.+)$")
            or question.strip()
        )

    if order_id_match:
        order_id = order_id_match.group(1)
        details = queue.get_order_details(order_id)
        context["matched_sections"].append("order_by_id")
        context["order"] = details["order"] if details else {}
        context["order_items"] = details["items"][:MAX_ORDER_ITEMS] if details else []
        context["telegram_images"] = _compact_rows(
            queue.read_rows("telegram_images")[:MAX_PENDING],
            ["external_order_id", "message_id", "item_index", "telegram_file_id", "caption", "import_status"],
        )
        return context

    normalized_current_markers = {queue.normalize_text(marker) for marker in CURRENT_ORDER_MARKERS}
    if any(marker in normalized for marker in normalized_current_markers):
        program_orders = queue.list_orders_by_status_group("under_preparation", limit=MAX_ORDERS)
        pending_orders = queue.list_telegram_inbox(statuses=["pending"], limit=MAX_PENDING)
        recent_import_status = queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=MAX_PENDING)
        order_items = []
        for row in program_orders[:5]:
            order_id = row.get("order_id", "")
            order_items.extend(queue.get_order_items(order_id)[:5])
        context["matched_sections"].append("current_orders")
        context["program_orders"] = _compact_rows(
            program_orders,
            ["order_id", "client_name", "total_amount", "status", "date", "notes"],
        )
        context["program_order_items"] = _compact_rows(
            order_items[:MAX_ORDER_ITEMS],
            ["order_id", "product_name", "qty", "price", "total"],
        )
        context["telegram_pending_orders"] = _compact_rows(
            pending_orders,
            ["external_order_id", "client_name", "client_type", "total_amount", "remaining_amount", "status", "received_at"],
        )
        context["telegram_import_status"] = _compact_rows(
            recent_import_status,
            ["external_order_id", "client_name", "total_amount", "status", "imported_order_id", "error_message", "received_at"],
        )
        if "صورة" in normalized or "صور" in normalized or "image" in normalized:
            context["telegram_images"] = _compact_rows(
                queue.read_rows("telegram_images")[:MAX_PENDING],
                ["external_order_id", "message_id", "item_index", "telegram_file_id", "caption", "import_status"],
            )
        return context

    if "طلبات اليوم" in normalized or "النهارده" in normalized or "today" in normalized:
        today_orders = queue.list_orders_for_today()[:MAX_ORDERS]
        context["matched_sections"].append("orders_today")
        context["orders"] = _compact_rows(
            today_orders,
            ["order_id", "client_name", "total_amount", "status", "date", "notes"],
        )
        order_ids = [row.get("order_id", "") for row in today_orders[:5]]
        order_items = []
        for order_id in order_ids:
            order_items.extend(queue.get_order_items(order_id)[:5])
        context["order_items"] = _compact_rows(
            order_items[:MAX_ORDER_ITEMS],
            ["order_id", "product_name", "qty", "price", "total"],
        )
        context["telegram_pending_orders"] = _compact_rows(
            queue.list_telegram_inbox(statuses=["pending"], limit=MAX_PENDING),
            ["external_order_id", "client_name", "client_type", "total_amount", "remaining_amount", "status", "received_at"],
        )
        return context

    if client_query:
        clients = queue.search_clients(client_query, limit=MAX_CLIENTS)
        orders = queue.search_orders(client_query, limit=MAX_ORDERS)
        context["matched_sections"].append("client_lookup")
        context["clients"] = _compact_rows(
            clients,
            ["client_id", "name", "phone", "type", "balance", "notes"],
        )
        context["orders"] = _compact_rows(
            orders,
            ["order_id", "client_name", "total_amount", "status", "date", "notes"],
        )
        context["telegram_inbox"] = _compact_rows(
            queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=MAX_PENDING),
            ["external_order_id", "client_name", "client_type", "total_amount", "status", "imported_order_id", "error_message"],
        )
        return context

    if partial_search_query:
        search_results = queue.partial_search_everywhere(partial_search_query, limit_per_section=5)
        context["matched_sections"].append("partial_search")
        context["partial_search_query"] = partial_search_query
        context["clients"] = _compact_rows(
            search_results["clients"],
            ["client_id", "name", "phone", "type", "balance"],
        )
        context["products"] = _compact_rows(
            search_results["products"],
            ["product_id", "name", "category", "stock_qty", "retail_price", "wholesale_price"],
        )
        context["orders"] = _compact_rows(
            search_results["orders"],
            ["order_id", "client_name", "total_amount", "status", "date", "notes"],
        )
        context["order_items"] = _compact_rows(
            search_results["order_items"],
            ["order_id", "product_name", "qty", "price", "total"],
        )
        context["telegram_inbox"] = _compact_rows(
            search_results["telegram_inbox"],
            ["external_order_id", "client_name", "total_amount", "remaining_amount", "status", "received_at"],
        )
        return context

    if product_query or any(keyword in normalized for keyword in PRODUCT_KEYWORDS):
        products = queue.search_products(product_query, limit=MAX_PRODUCTS)
        context["matched_sections"].append("product_lookup")
        context["products"] = _compact_rows(
            products,
            ["product_id", "name", "category", "stock_qty", "retail_price", "wholesale_price"],
        )
        return context

    if order_search_query:
        orders = queue.search_orders(order_search_query, limit=MAX_ORDERS)
        context["matched_sections"].append("order_search")
        context["orders"] = _compact_rows(
            orders,
            ["order_id", "client_name", "total_amount", "status", "date", "notes"],
        )
        order_ids = [row.get("order_id", "") for row in orders[:5]]
        order_items = []
        for order_id in order_ids:
            order_items.extend(queue.get_order_items(order_id)[:5])
        context["order_items"] = _compact_rows(
            order_items[:MAX_ORDER_ITEMS],
            ["order_id", "product_name", "qty", "price", "total"],
        )
        context["telegram_inbox"] = _compact_rows(
            queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=MAX_PENDING),
            ["external_order_id", "client_name", "client_type", "total_amount", "status", "imported_order_id", "error_message"],
        )
        return context

    summary = queue.get_accounts_summary()
    context["matched_sections"].append("general_summary")
    context["summary"] = {
        "under_preparation": summary["under_preparation"],
        "delivery": summary["delivery"],
        "delivered": summary["delivered"],
        "today_orders_count": summary["today_orders_count"],
        "today_orders_total": summary["today_orders_total"],
        "pending_inbox_count": summary["pending_inbox_count"],
        "clients_count": summary["clients_count"],
        "products_count": summary["products_count"],
        "total_client_balance": summary["total_client_balance"],
        "low_stock_count": summary["low_stock_count"],
    }
    context["recent_orders"] = _compact_rows(
        queue.list_recent_orders(limit=MAX_ORDERS),
        ["order_id", "client_name", "total_amount", "status", "date", "notes"],
    )
    context["products"] = _compact_rows(
        queue.search_products("", limit=20),
        ["product_id", "name", "category", "stock_qty", "retail_price", "wholesale_price"],
    )
    context["top_debt_clients"] = _compact_rows(
        summary["top_debt_clients"][:MAX_CLIENTS],
        ["client_id", "name", "phone", "type", "balance"],
    )
    context["pending_queue"] = _compact_rows(
        queue.list_telegram_inbox(statuses=["pending"], limit=MAX_PENDING),
        ["external_order_id", "client_name", "client_type", "total_amount", "remaining_amount", "status", "received_at"],
    )
    context["telegram_import_status"] = _compact_rows(
        queue.list_telegram_inbox(statuses=["pending", "imported", "failed"], limit=MAX_PENDING),
        ["external_order_id", "client_name", "client_type", "total_amount", "status", "imported_order_id", "error_message", "received_at"],
    )
    context["telegram_sync_status"] = queue.get_telegram_sync_status_summary()
    return context


def parse_openrouter_response(response_payload: Dict[str, Any]) -> Dict[str, Any]:
    choices = response_payload.get("choices", [])
    if not choices:
        return {"success": False, "error": "missing_choices", "details": response_payload}

    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                text_parts.append(str(item.get("text", "")))
            else:
                text_parts.append(str(item))
        content = "\n".join(part for part in text_parts if part).strip()

    if not content:
        return {"success": False, "error": "empty_content", "details": response_payload}

    return {"success": True, "content": str(content).strip(), "raw": response_payload}


def _extract_json_object(text: str) -> Dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate)
    try:
        payload = json.loads(candidate)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in OpenRouter response.")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("OpenRouter JSON response is not an object.")
    return payload


def call_openrouter(
    settings: TelegramBotSettings,
    system_prompt: str,
    user_content: str,
    *,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Dict[str, Any]:
    if not settings.openrouter_api_key:
        return {"success": False, "error": "missing_openrouter_api_key"}

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        f"{settings.openrouter_base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OPENROUTER_TIMEOUT_SECONDS) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "error": f"http_{exc.code}", "details": error_body}
    except urllib.error.URLError as exc:
        return {"success": False, "error": "url_error", "details": str(exc)}
    except Exception as exc:
        return {"success": False, "error": "unexpected_error", "details": str(exc)}

    return parse_openrouter_response(response_payload)


def ask_openrouter(settings: TelegramBotSettings, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
    return call_openrouter(
        settings,
        SYSTEM_PROMPT,
        (
            f"سؤال المستخدم:\n{question.strip()}\n\n"
            f"بيانات من Google Sheet:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
        ),
    )


def classify_message_intent(settings: TelegramBotSettings, message_text: str) -> Dict[str, Any]:
    rule_intent = _classify_with_rules(message_text)
    if rule_intent:
        return {"success": True, "intent": rule_intent, "reason": "local_rule", "raw": {"intent": rule_intent, "reason": "local_rule"}}

    result = call_openrouter(
        settings,
        ROUTER_SYSTEM_PROMPT,
        f"رسالة المستخدم:\n{message_text.strip()}\n\nأعد JSON فقط بالشكل: {{\"intent\":\"...\",\"reason\":\"...\"}}",
        temperature=0.0,
        max_tokens=120,
    )
    if not result.get("success"):
        return result
    try:
        payload = _extract_json_object(result["content"])
    except Exception as exc:
        return {"success": False, "error": "invalid_router_json", "details": str(exc), "raw_content": result.get("content", "")}
    intent = str(payload.get("intent", "")).strip()
    if intent not in {
        "create_order",
        "record_payment",
        "product_lookup",
        "update_product_price",
        "update_product_prices_bulk",
        "client_balance_query",
        "receivables_summary",
        "orders_status_query",
        "partial_search",
        "data_question",
        "normal_ai_question",
        "unknown",
        "order_intent",
    }:
        return {"success": False, "error": "invalid_router_intent", "details": payload}
    if intent == "order_intent":
        intent = "create_order"
    return {"success": True, "intent": intent, "reason": str(payload.get("reason", "")).strip(), "raw": payload}


def extract_order_json(settings: TelegramBotSettings, message_text: str) -> Dict[str, Any]:
    result = call_openrouter(
        settings,
        ORDER_EXTRACTION_SYSTEM_PROMPT,
        f"رسالة الطلب:\n{message_text.strip()}",
        temperature=0.0,
        max_tokens=500,
    )
    if not result.get("success"):
        return result
    try:
        payload = _extract_json_object(result["content"])
    except Exception as exc:
        return {"success": False, "error": "invalid_order_json", "details": str(exc), "raw_content": result.get("content", "")}
    return {"success": True, "order": payload, "raw": payload}


def ask_general_assistant(settings: TelegramBotSettings, question: str) -> Dict[str, Any]:
    return call_openrouter(settings, GENERAL_ASSISTANT_PROMPT, f"رسالة المستخدم:\n{question.strip()}")
