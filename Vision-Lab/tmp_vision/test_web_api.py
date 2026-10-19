# -*- coding: utf-8 -*-
"""اختبار مسارات الويب الجديدة عبر Flask test_client (بلا سيرفر وبلا بورت).

بنتأكد من:
- /api/chat (GET و POST) بيمر من `bot.process_text` و**مابيبعتش تليجرام**
- /api/dashboard بيمشي وبيرجّع نفس مفاتيح `db.dashboard()`
- POST /api/capture/<id>/action لكل الأفعال على صف مؤقت
- الصفحات اتغيّرت لـ«أفكاري»
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
sys.path.insert(0, str(ROOT))

from nb import bot, db, web  # noqa: E402

OUT = {}
sent = []


def _guard(self, method, payload=None):
    sent.append({"method": method})
    raise AssertionError(f"الويب حاول يبعت تليجرام: {method}")


original = bot.TelegramClient.call
bot.TelegramClient.call = _guard

# منبوّض personas.remember عشان الاختبار ما يكتبش صفوف محادثة حقيقية
remembered = []
original_remember = bot.persona.remember
bot.persona.remember = lambda *a, **k: remembered.append(a)

client = web.app.test_client()
cid = None
try:
    # --- /api/dashboard
    t0 = time.time()
    r = client.get("/api/dashboard")
    OUT["dash_status"] = r.status_code
    OUT["dash_ms_cold"] = round((time.time() - t0) * 1000, 1)
    dash = r.get_json() or {}
    OUT["dash_keys"] = sorted(dash.keys())
    t0 = time.time()
    r2 = client.get("/api/dashboard")
    OUT["dash_ms_warm"] = round((time.time() - t0) * 1000, 1)
    OUT["dash_same_keys"] = sorted((r2.get_json() or {}).keys()) == OUT["dash_keys"]

    # --- /api/dashboard?ttl=0 (بلا كاش)
    t0 = time.time()
    r3 = client.get("/api/dashboard?ttl=0")
    OUT["dash_ttl0_ms"] = round((time.time() - t0) * 1000, 1)
    OUT["dash_ttl0_ok"] = r3.status_code == 200

    # --- /api/chat GET
    r = client.get("/api/chat?text=%D9%87%D8%A7%D9%8A")
    OUT["chat_get_status"] = r.status_code
    OUT["chat_get_json"] = {k: r.get_json().get(k) for k in
                            ("ok", "intent", "note_id", "routed_by", "source")}

    # --- /api/chat POST
    r = client.post("/api/chat", json={"text": "هاي"})
    OUT["chat_post_status"] = r.status_code
    OUT["chat_post_intent"] = r.get_json().get("intent")

    # --- /api/chat بلا نص → 400
    OUT["chat_empty_status"] = client.post("/api/chat", json={"text": "  "}).status_code

    # --- صفحة الجذر
    t0 = time.time()
    r = client.get("/")
    OUT["root_status"] = r.status_code
    OUT["root_ms"] = round((time.time() - t0) * 1000, 1)
    html = r.get_data(as_text=True)
    OUT["root_has_afkary"] = "أفكاري" in html
    OUT["root_has_old_name"] = "النوتبوك v2" in html
    OUT["root_renders_rows"] = html.count('class="note"') if 'class="note"' in html else None

    # --- أفعال النوتة على صف مؤقت
    cid = db.add_capture({"title": "VISION WEB ACTION TEST", "body": "اتمسح",
                          "kind": "task", "category": "غير مصنف", "priority": "normal",
                          "source": "web-test", "confidence": 0.5, "routed_by": "rules"})
    OUT["created_id"] = cid

    r = client.post(f"/api/capture/{cid}/action", json={"action": "done"})
    OUT["action_done"] = r.get_json()
    OUT["status_after"] = db.scalar("SELECT status FROM captures WHERE id=%s", (cid,))

    r = client.post(f"/api/capture/{cid}/action", json={"action": "snooze", "value": 600})
    OUT["action_snooze"] = r.get_json()

    r = client.post(f"/api/capture/{cid}/action", json={"action": "category", "value": "ليزر"})
    OUT["action_category"] = r.get_json()

    r = client.post(f"/api/capture/{cid}/action", json={"action": "reopen"})
    OUT["action_reopen"] = r.get_json()

    # فعل غلط → 400 صريح
    r = client.post(f"/api/capture/{cid}/action", json={"action": "nonsense"})
    OUT["action_bad_status"] = r.status_code

    # snooze بقيمة مش رقم → 400
    r = client.post(f"/api/capture/{cid}/action", json={"action": "snooze", "value": "abc"})
    OUT["action_bad_value_status"] = r.status_code

    # --- التصفية لسه شغالة
    r = client.get("/?kind=task")
    OUT["filter_kind_status"] = r.status_code
    r = client.get("/?status=all&q=ليزر")
    OUT["filter_search_status"] = r.status_code

finally:
    if cid is not None:
        db.x("DELETE FROM captures WHERE id=%s", (cid,))
    bot.TelegramClient.call = original
    bot.persona.remember = original_remember

OUT["scratch_left"] = int(db.scalar("SELECT count(*) FROM captures WHERE id=%s", (cid,))) if cid else None
OUT["scratch_events_left"] = int(db.scalar("SELECT count(*) FROM capture_events WHERE capture_id=%s", (cid,))) if cid else None
OUT["telegram_calls"] = sent
OUT["remember_calls"] = len(remembered)

print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
