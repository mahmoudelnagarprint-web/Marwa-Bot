#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Marwa Cloud Brain — Telegram Webhook Server (Level 1, option B)
========================================================================
The CLOUD side of the hybrid agent: receives @Marwty_bot messages via Webhook
while the shop PC is OFF. Gives full business intelligence using the Supabase
mirror as memory and Dahl (LLM) as the "وكيل النجار برنت" persona.

Flow for each message (owner-only, verified by OWNER_TELEGRAM_ID):
  1. If it is a SYSTEM command (لقطة شاشة / اغلق الجهاز / أعد التشغيل):
     -> insert into `commands` as (action='system_command', payload={'cmd': ...}).
  2. Otherwise: read mirror tables (clients/products) from Supabase, build a
     rich system prompt, ask Dahl. If Dahl decides a WRITE is needed
     (order/client/product/payment) -> insert that into `commands` status=pending.
  3. Send Dahl's reply straight back to the owner via Telegram.

Deploy: Replit (Flask + requests only). Public HTTPS URL required for Telegram.

Register webhook (run once after deploy, from local or any shell):
  python cloud_webhook_server.py --register https://<your-app>.replit.app
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request

# --- paths / env ------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

SUPA_URL = ""
SUPA_KEY = ""
TELEGRAM_TOKEN = ""
OWNER_ID = ""
ALLOWED = set()
DAHL_URL = ""
DAHL_KEY = ""
DAHL_MODEL = "default-model"
PERSONA = ""

app = Flask(__name__)


def load_env() -> None:
    global SUPA_URL, SUPA_KEY, TELEGRAM_TOKEN, OWNER_ID, ALLOWED
    global DAHL_URL, DAHL_KEY, DAHL_MODEL, PERSONA
    env: dict = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    env = {**os.environ, **env}

    SUPA_URL = env.get("SUPABASE_URL", "").rstrip("/")
    SUPA_KEY = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_PUBLISHABLE_KEY", "")
    TELEGRAM_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
    OWNER_ID = str(env.get("OWNER_TELEGRAM_ID", "")).strip()
    ALLOWED = {
        str(x).strip()
        for x in (env.get("ALLOWED_CHAT_IDS", "") or env.get("OWNER_TELEGRAM_ID", "")).split(",")
        if str(x).strip()
    }
    DAHL_URL = env.get("DAHL_API_URL", "").rstrip("/")
    DAHL_KEY = env.get("DAHL_API_KEY", "")
    DAHL_MODEL = env.get("DAHL_MODEL", "default-model")
    PERSONA = env.get(
        "MARWA_PERSONA",
        "أنت «مروة» الوكيل الذكي لمطبعة النجار برنت (متجر الطباعة والقص بالليزر). "
        "تتحدث مصرية واضحة وأدبية، مختصرة، وتساعد في الرد على استفسارات العملاء عن "
        "الأسعار والمنتجات والعملاء، وترشّد تُغرّد. ارد بالمنطوق المباشر الآمن." if False else
        "أنت «مروة» الوكيل الذكي لمطبعة النجار برنت — متجر الطباعة المتخصصة والقص بالليزر. تتحدث بالعربية "
        "المصرية، بلباقة ومختصرة. عند طلبك معلومة من السياق (أسعار/منتجات/عملاء/أرصدة) أجب من المعطى فقط، "
        "ولا تختلق. إن طلب المستخدم عملية كتابة (طلب جديد/عميل/منتج/دفعة) قدّم نية كتابية بصيغة JSON.",
    )


def _headers() -> dict:
    return {
        "apikey": SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type": "application/json",
    }


# ------------------------------------------------------------------- memory
def fetch_table(table: str, limit: int = 500) -> list:
    """Read a mirror table from Supabase (read-only)."""
    if not SUPA_URL or not SUPA_KEY:
        return []
    resp = requests.get(
        f"{SUPA_URL}/rest/v1/{table}?select=*&order=id.asc&limit={limit}",
        headers=_headers(),
        timeout=30,
    )
    if not resp.ok:
        return []
    return resp.json() or []


def build_business_context() -> str:
    """Compress mirror tables into a compact context string for Dahl (no secrets)."""
    clients = fetch_table("clients", 500)
    products = fetch_table("products", 500)

    lines = ["السياق الحالي للمحل (مرآة سحابية):"]

    # Clients: only name + balance (no phones displayed to LLM unless needed)
    clients_sorted = sorted(clients, key=lambda c: c.get("balance") or 0, reverse=True)[:150]
    if clients_sorted:
        lines.append("العملاء (الاسم - الرصيد):")
        for c in clients_sorted:
            lines.append(
                f"  · {c.get('name','')} — رصيد {c.get('balance') or 0}"
            )
    else:
        lines.append("العملاء: (لا يوجد)")

    # Products: name - category - retail - wholesale - stock
    if products:
        lines.append("المنتجات (الاسم - الفئة - التجزئة - الجملة - المخزون):")
        for p in sorted(products, key=lambda p: str(p.get("name", "")))[:300]:
            lines.append(
                f"  · {p.get('name','')} | {p.get('category','')} | "
                f"{p.get('price_retail') or 0} | {p.get('price_wholesale') or 0} | "
                f"مخزون {p.get('stock_qty') or 0}"
            )
    else:
        lines.append("المنتجات: (لا يوجد)")

    lines.append(f"(إجمالي العملاء {len(clients)}، المنتجات {len(products)})")
    return "\n".join(lines)


# -------------------------------------------------------------------- dahl
def ask_dahl(user_text: str, context: str) -> tuple[str, dict]:
    """Send to Dahl with a structured contract: expect JSON envelope.

    Returns (reply_text, action_dict). action_dict = {"action": "...", "payload": {...}}
    """
    system = (
        f"{PERSONA}\n\nبيانات المحل (مرآة):\n{context}\n\n"
        "قواعد الاتصال:\n"
        "1. أجب المستخدم بإجابة عربية مصرية طبيعية كاملة في حقل reply.\n"
        "2. إن كان طلب المستخدم عملية كتابة (إضافة طلب/عميل/منتج جديد/تسجيل دفعة) فاملأ حقل "
        "action بأحد القيم: create_order | create_client | add_product | record_payment، "
        "وحقل payload بالبيانات اللازمة ككائن JSON.\n"
        "3. إن لم يكن هناك كتابة مطلوبة فاجعل action = 'none' و payload = {}.\n"
        "4. أعد JSON صالحًا فقط بهذا الشكل:\n"
        '{"reply": "الرد", "action": "none", "payload": {}}'
    )
    try:
        resp = requests.post(
            f"{DAHL_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DAHL_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": DAHL_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text},
                ],
                "temperature": 0.3,
            },
            timeout=60,
        )
        resp.raise_for_status()
        content = (resp.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
    except Exception as exc:
        return f"⚠️ تعذر الاتصال بمزود الذكاء: {exc}", {"action": "none", "payload": {}}

    # Try to parse JSON envelope (cope with markdown-fenced JSON)
    m = re.search(r"\{.*\}", content, re.S)
    if m:
        try:
            env = json.loads(m.group(0))
            reply = env.get("reply") or content
            action = env.get("action") or "none"
            payload = env.get("payload") or {}
            return str(reply), {"action": str(action), "payload": payload}
        except Exception:
            pass
    return content, {"action": "none", "payload": {}}


# ---------------------------------------------------------------- telegram
def tg_send_message(chat_id, text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": str(chat_id), "text": text, "disable_web_page_preview": True},
            timeout=30,
        )
        return r.ok
    except Exception:
        return False


def tg_send_reply(chat_id, text: str) -> None:
    # Telegram limit 4096 — chunk if needed
    for i in range(0, len(text), 4000):
        ok = tg_send_message(chat_id, text[i:i + 4000])
        if not ok:
            break


# ---------------------------------------------------------------- commands
def lookup_client_id(name_query: str) -> int | None:
    """Best-effort: resolve a client's probable id from mirror (by exact name or contains)."""
    q = (name_query or "").strip().lower()
    if not q:
        return None
    for c in fetch_table("clients", 500):
        if str(c.get("name", "")).strip().lower() == q:
            return c.get("id")
    for c in fetch_table("clients", 500):
        if q in str(c.get("name", "")).strip().lower():
            return c.get("id")
    return None


def enqueue_command(action: str, payload: dict, idempotency_key: str | None = None) -> None:
    """Insert a command into Supabase `commands` with status='pending'."""
    if not SUPA_URL or not SUPA_KEY:
        return
    row = {
        "action": action,
        "payload": payload,
        "status": "pending",
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    requests.post(
        f"{SUPA_URL}/rest/v1/commands",
        headers=_headers(),
        json=row,
        timeout=30,
    )


# ------------------------------------------------- system-command matching
SYSTEM_CMDS = {
    "screenshot": ["لقطة", "لقطه", "سكرين", "شاشة", "شاشه", "screenshot", "capture"],
    "reboot": ["أعد التشغيل", "اعادة تشغيل", "اعيد التشغيل", "reset", "restart", "reboot"],
    "shutdown": ["اغلق الجهاز", "اقفل الجهاز", "اطفئ", "اطفي", "إطفاء", "اغلاق", "shutdown", "power off"],
}


def detect_system_command(text: str) -> str | None:
    t = (text or "").strip().lower()
    if not t:
        return None
    # priority: shutdown exact phrases first to avoid "لقطة شاشة" → shutdown
    if any(k in t for k in SYSTEM_CMDS["shutdown"]):
        return "shutdown"
    if any(k in t for k in SYSTEM_CMDS["reboot"]):
        return "reboot"
    if any(k in t for k in SYSTEM_CMDS["screenshot"]):
        return "screenshot"
    return None


# ------------------------------------------------------------------ routes
@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "service": "marwa-cloud", "ts": datetime.now(timezone.utc).isoformat()}


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(silent=True) or {}
    message = update.get("message") or {}
    from_id = str((message.get("from") or {}).get("id", "")).strip()
    chat_id = str((message.get("chat") or {}).get("id", "")).strip()
    text = (message.get("text") or "").strip()

    # Owner-only: reject anyone not in OWNER_ALLOWED
    if ALLOWED and from_id not in ALLOWED:
        return jsonify({"ok": True, "ignored": True})  # 200 so Telegram stops retrying
    if not chat_id:
        return jsonify({"ok": True, "ignored": True})

    if not text:
        return jsonify({"ok": True, "ignored": True})

    print(f"[{datetime.now(timezone.utc).isoformat()}] msg from {from_id}: {text[:80]}", flush=True)

    # 1) System command?
    sys_cmd = detect_system_command(text)
    if sys_cmd:
        enqueue_command("system_command", {"cmd": sys_cmd})
        reply = "تمام يا معلم 👌 هتفاعل معاها محليًا خلال ثوانٍ (توصّل لك بسرعة)."
        if sys_cmd == "shutdown":
            reply = "تمام، هيقفل الجهاز بعد ثوانٍ على الأمر المحلي. 😴"
        elif sys_cmd == "reboot":
            reply = "تمام، هيعيد التشغيل محليًا. 🔄"
        elif sys_cmd == "screenshot":
            reply = "تمام، ناخد لقطة شاشة وبعتها لك حالًا. 📸"
        tg_send_reply(chat_id, reply)
        return jsonify({"ok": True, "system": sys_cmd})

    # 2) Business query → Dahl + memory
    context = build_business_context()
    parsed_reply, decision = ask_dahl(text, context)

    # If Dahl asked for a WRITE → enqueue it pending (resolves client id when possible)
    payload = decision.get("payload") or {}
    action = (decision.get("action") or "").strip().lower()
    if action in ("create_order", "create_client", "add_product", "record_payment") and payload:
        if action in ("create_order", "record_payment") and not payload.get("client_id"):
            cid = lookup_client_id(payload.get("client_name") or payload.get("client") or "")
            if cid:
                payload["client_id"] = cid
        enqueue_command(action, payload)
        parsed_reply += "\n\n✅ (تم تجهيز العملية ليتم تطبيقها على جهاز المحل فور عودته)."

    # 3) Reply to owner
    tg_send_reply(chat_id, parsed_reply)
    return jsonify({"ok": True})


# ------------------------------------------------------------------- runner
def register_webhook(public_url: str, secret_token: str | None = None) -> dict:
    public_url = public_url.rstrip("/")
    params = {"url": f"{public_url}/webhook", "allowed_updates": '["message"]'}
    if secret_token:
        params["secret_token"] = secret_token
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
        data=params,
        timeout=30,
    )
    return r.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="Marwa Cloud Brain webhook server")
    ap.add_argument("--register", type=str, help="public base URL to set as webhook, e.g. https://x.replit.app")
    ap.add_argument("--unregister", action="store_true", help="delete webhook")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    args = ap.parse_args()

    load_env()

    if args.register:
        res = register_webhook(args.register)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res.get("ok") else 1
    if args.unregister:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook", timeout=30
        )
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
        return 0 if r.json().get("ok") else 1

    load_env()
    print(f"[marwa-cloud] listening :{args.port}  (use --register <public_url> to attach webhook)")
    app.run(host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    sys_exit = main()
    sys.exit(sys_exit)
