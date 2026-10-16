# -*- coding: utf-8 -*-
"""النوتبوك الذكية — جسر تليجرام: استقبال النوتس من أي مكان + إرسال التذكيرات.

- استقبال: long-polling على getUpdates (بلا مكتبات خارجية — urllib فقط).
- أمان: يردّ فقط على المحادثات المسموح بها (.env: OWNER_TELEGRAM_ID / ALLOWED_CHAT_IDS).
- حماية تعارض: لو فيه webhook مسجّل على البوت، يرفض العمل ويطبع السبب (منع 409).
- كل رسالة تتحوّل: أمر (تم/أجّل/صنّف/المستحق/قائمتي) أو نوت جديد يُحلّل ويُحفظ.
- تذكيرات: تُرسل عند الاستحقاق؛ غير المتكرر يُغلق بعد الإرسال، والمتكرر يتقدّم للدورة التالية.
- ملخص صباحي يومي 08:00 مع اقتراح واحد.

الاستخدام:
    python -m notebook.telegram_bridge --test          # اختبار الإرسال فقط
    python -m notebook.telegram_bridge --send "نص"     # إرسال رسالة واحدة
    python -m notebook.telegram_bridge --watch         # الخدمة الدائمة (استقبال + تذكيرات)
    python -m notebook.telegram_bridge --once          # دورة واحدة ثم خروج (للاختبار)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from notebook import brain, store  # type: ignore
else:
    from . import brain, store

ROOT = store.ROOT
DATA_DIR = ROOT / "notebook" / "data"
STATE_FILE = DATA_DIR / "telegram_state.json"
LOCK_FILE = DATA_DIR / "telegram_bridge.lock"
API = "https://api.telegram.org/bot{token}/{method}"


# ------------------------------------------------------------------ إعدادات
def load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    path = ROOT / ".env"
    try:
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = raw.strip()
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def _allowed_chats(env: Dict[str, str]) -> set:
    ids = set()
    for key in ("OWNER_TELEGRAM_ID", "ALLOWED_CHAT_IDS"):
        for part in re.split(r"[,\s]+", env.get(key, "") or ""):
            part = part.strip()
            if re.fullmatch(r"-?\d+", part or ""):
                ids.add(int(part))
    return ids


def _load_state() -> Dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"offset": 0, "digest_date": "", "sent": []}


def _save_state(state: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def log(msg: str) -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        (ROOT / "logs").mkdir(parents=True, exist_ok=True)
        with (ROOT / "logs" / "notebook_bot.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ Telegram API
class Telegram:
    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout

    def call(self, method: str, payload: Optional[Dict[str, Any]] = None,
             timeout: Optional[int] = None) -> Dict[str, Any]:
        url = API.format(token=self.token, method=method)
        data = urllib.parse.urlencode(payload or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            return {"ok": False, "error": f"HTTP {exc.code}: {body}"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def send(self, chat_id: int, text: str, reply_to: Optional[int] = None) -> bool:
        payload = {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": "true"}
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        res = self.call("sendMessage", payload)
        if not res.get("ok"):
            log(f"send failed: {res.get('error')}")
        return bool(res.get("ok"))

    def get_updates(self, offset: int, timeout: int = 25) -> Optional[List[Dict[str, Any]]]:
        """يُرجع قائمة التحديثات، أو None عند فشل الشبكة (يفرّق عن الفراغ الصحي)."""
        res = self.call("getUpdates", {"offset": offset, "timeout": timeout, "allowed_updates": '["message"]'},
                        timeout=timeout + 15)
        if not res.get("ok"):
            log(f"getUpdates failed: {res.get('error')}")
            return None
        return res.get("result") or []

    def webhook_url(self) -> str:
        res = self.call("getWebhookInfo")
        return ((res.get("result") or {}).get("url") or "") if res.get("ok") else ""


# ------------------------------------------------------------------ الأوامر
HELP = (
    "💡 النوتبوك الذكية — اكتب أي حاجة وأنا أسجّلها وأصنّفها.\n"
    "أوامر سريعة (الرسالة كلها لازم تكون الأمر بس):\n"
    "• «المستحق» — اللي ميعاده جه أو فات\n"
    "• «قائمتي» — المفتوح كله\n"
    "• «الملخص» — ملخص شامل مع اقتراح\n"
    "• «تم 5» — اقفل النوت رقم 5\n"
    "• «أجّل 5» أو «أجّل 5 يوم» — تأجيل\n"
    "• «صنّف 5 حسابات» — نقل لتصنيف\n"
    "• «احذف 5» — حذف نهائي للنوت\n"
    "• «مساعدة» — القائمة دي\n"
    "\nوأي رسالة تانية = نوت جديد يتحلّل ويتصنّف لوحده."
)


def _fmt_note(n: Dict[str, Any], with_body: bool = False) -> str:
    icon = brain.KIND_LABELS.get(n.get("kind") or "", "📝")
    due = f" | 📅 {n['due_at']}" if n.get("due_at") else ""
    cat = f" | {n.get('category_emoji') or '📁'} {n.get('category') or 'غير مصنف'}"
    line = f"#{n.get('id')} {icon} {n.get('title') or '(بدون عنوان)'}{cat}{due}"
    if with_body and n.get("body") and n["body"] != n.get("title"):
        line += f"\n   {n['body'][:160]}"
    return line


def _is_exact(low: str, *words: str) -> bool:
    """مطابقة أمر قصير بالكامل (بعد التطبيع) — تمنع نفاذ الأوامر جوه نوت طويل."""
    return any(low == brain.normalize(w) for w in words)


def digest_text() -> str:
    due = store.due_now()
    late = store.overdue()
    open_notes = store.list_notes(status="open")
    tasks = [n for n in open_notes if n.get("kind") == "task"]
    ideas = [n for n in open_notes if n.get("kind") in ("idea", "program_idea")]
    no_when = [n for n in open_notes if not n.get("due_at")]
    lines = [f"☀️ ملخص النوتبوك — {datetime.now():%Y-%m-%d %H:%M}", ""]
    lines.append(f"📌 مفتوح: {len(open_notes)} | ✅ مهام: {len(tasks)} | 💡 أفكار: {len(ideas)}")
    if late:
        lines.append(f"🔴 متأخر ({len(late)}):")
        lines += [f"   • {_fmt_note(n)}" for n in late[:5]]
    if due:
        lines.append(f"⏰ مستحق الآن ({len(due)}):")
        lines += [f"   • {_fmt_note(n)}" for n in due[:5]]
    if tasks:
        lines.append(f"✅ أقرب المهام ({len(tasks)}):")
        lines += [f"   • {_fmt_note(n)}" for n in tasks[:6]]
    if ideas:
        lines.append(f"🚀 أفكار برامج ({len(ideas)}):")
        lines += [f"   • {_fmt_note(n)}" for n in ideas[:4]]
    if no_when:
        lines.append(f"❔ {len(no_when)} نوتس من غير ميعاد — تحب أحدّدها؟")
    lines.append("")
    lines.append("💡 اقتراحي: ابدأ بأكتر حاجة متأخرة، وابعتلي «تم <الرقم>» أول ما تخلّص.")
    return "\n".join(lines)


def route_message(text: str) -> str:
    """يحوّل رسالة المالك إلى رد — أمر أو نوت جديد.

    الأوامر لازم تكون الرسالة كلها (مطابقة كاملة أو رقم بعنوان واضح) —
    عشان نوت عادي فيه كلمة «تم» أو «قائمة» ما يتفسرش كأمر بالغلط.
    """
    t = (text or "").strip()
    if not t:
        return "ابعتلي نص النوت 🙂"
    low = brain.normalize(t)

    if _is_exact(low, "/start", "/help", "help", "بداية", "مساعدة", "ابدأ"):
        return HELP

    if _is_exact(low, "/due", "المستحق", "اللي فات", "المواعيد"):
        due, late = store.due_now(), store.overdue()
        if not due and not late:
            return "✅ مفيش حاجة مستحقة دلوقتي."
        out = []
        if late:
            out.append(f"🔴 متأخر ({len(late)}):")
            out += [f"   • {_fmt_note(n)}" for n in late[:8]]
        if due:
            out.append(f"⏰ مستحق الآن ({len(due)}):")
            out += [f"   • {_fmt_note(n)}" for n in due[:8]]
        return "\n".join(out)

    if _is_exact(low, "/list", "قائمتي", "قائمة", "المفتوح", "كل المهام", "المهام"):
        notes = store.list_notes(status="open")
        if not notes:
            return "القايمة فاضية — اكتب أول نوت 💡"
        return f"📋 المفتوح ({len(notes)}):\n" + "\n".join(_fmt_note(n) for n in notes[:12])

    if _is_exact(low, "/digest", "الملخص", "ملخص", "الملخص الكامل"):
        return digest_text()

    m = re.search(r"^\s*(?:تم|خلصت|انتهيت|اقفل|قفل)\s*#?(\d+)\s*$", low)
    if m:
        nid = int(m.group(1))
        note = store.get_note(nid)
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        store.set_status(nid, "done")
        return f"✅ تمام — قفلت #{nid}: {note.get('title')}"

    m = re.search(r"^\s*اجل\s*#?(\d+)\s*(ساعه?|ساعات|دقيقه?|دقايق|يوم|ايام)?\s*$", low)
    if m:
        nid = int(m.group(1))
        note = store.get_note(nid)
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        unit = m.group(2) or ""
        minutes = 1440 if ("يوم" in unit or "ايام" in unit) else (15 if ("دقيق" in unit) else 60)
        base = note.get("remind_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            when = datetime.strptime(base, "%Y-%m-%d %H:%M") + timedelta(minutes=minutes)
        except ValueError:
            when = datetime.now() + timedelta(minutes=minutes)
        store.update_note(nid, remind_at=when.strftime("%Y-%m-%d %H:%M"))
        store.log_event(nid, "snooze", f"+{minutes}m via telegram")
        return f"⏰ أجّلت #{nid} لحد {when:%Y-%m-%d %H:%M}"

    m = re.search(r"^\s*(?:صنف|تصنيف|انقل)\s*#?(\d+)\s+(.+?)\s*$", low)
    if m:
        nid = int(m.group(1))
        cat = m.group(2).strip()
        if not store.get_note(nid):
            return f"مفيش نوت رقم #{nid} 🤔"
        store.set_category(nid, cat)
        note = store.get_note(nid)
        return f"🗂️ نقلت #{nid} لتصنيف «{note.get('category')}»"

    m = re.search(r"^\s*احذف\s*#?(\d+)\s*$", low)
    if m:
        nid = int(m.group(1))
        note = store.get_note(nid)
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        store.delete_note(nid)
        return f"🗑️ اتمسح #{nid}: {note.get('title')}"

    # غير كده: نوت/مهمة جديدة
    analysis = brain.analyze(t, source="telegram")
    if not analysis.get("ok"):
        return "مش فاهم النص ده 🤔"
    note_id = store.add_note(analysis)
    return brain.confirm_message(analysis, note_id)


# ------------------------------------------------------------------ الدورات
def handle_update(tg: Telegram, update: Dict[str, Any], allowed: set, state: Dict[str, Any]) -> None:
    msg = update.get("message") or update.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = msg.get("text") or msg.get("caption") or ""
    if chat_id is None:
        return
    if allowed and chat_id not in allowed:
        log(f"ignored message from unauthorized chat {chat_id}")
        return
    if not text.strip():
        tg.send(chat_id, "ابعتلي نص — الصور والملفات مش مدعومة دلوقتي 🙂")
        return
    try:
        reply = route_message(text)
    except Exception as exc:
        reply = f"❌ حصل خطأ داخلي ({type(exc).__name__}) — ما افترضتش أي نتيجة."
        log(f"route error: {type(exc).__name__}: {exc}")
    tg.send(chat_id, reply, reply_to=msg.get("message_id"))
    log(f"handled chat={chat_id} text={text[:60]!r}")


def _advance_reminder(note: Dict[str, Any]) -> Optional[str]:
    every = (note.get("remind_every") or "none").lower()
    if every in ("daily", "weekly", "monthly"):
        base = note.get("remind_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            when = datetime.strptime(base, "%Y-%m-%d %H:%M")
        except ValueError:
            when = datetime.now()
        when += {"daily": timedelta(days=1), "weekly": timedelta(weeks=1),
                 "monthly": timedelta(days=30)}[every]
        return when.strftime("%Y-%m-%d %H:%M")
    return None


def reminders_cycle(tg: Telegram, allowed: set) -> int:
    sent = 0
    for note in store.due_now():
        chat_id = next(iter(allowed)) if allowed else 0
        if not chat_id:
            log("no allowed chat id — reminders cannot be sent")
            break
        icon = brain.KIND_LABELS.get(note.get("kind") or "", "⏰")
        body = [f"⏰ تذكير {icon}: {note.get('title')}",
                f"• التصنيف: {note.get('category') or 'غير مصنف'}"]
        if note.get("due_at"):
            body.append(f"• الميعاد: {note['due_at']}")
        body.append(f"• للتنفيذ: «تم {note['id']}» — للتأجيل: «أجّل {note['id']} ساعة»")
        if tg.send(chat_id, "\n".join(body)):
            nxt = _advance_reminder(note)
            store.update_note(note["id"], remind_at=nxt)
            store.log_event(note["id"], "reminded", f"sent to {chat_id}" + (f" next={nxt}" if nxt else " (once)"))
            sent += 1
    return sent


def digest_cycle(tg: Telegram, allowed: set, state: Dict[str, Any], now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    today = now.strftime("%Y-%m-%d")
    if state.get("digest_date") == today:
        return False
    if not (8 <= now.hour < 10):
        return False
    chat_id = next(iter(allowed)) if allowed else 0
    if not chat_id:
        return False
    if tg.send(chat_id, digest_text()):
        state["digest_date"] = today
        _save_state(state)
        log("morning digest sent")
        return True
    return False


def poll_loop(tg: Telegram, allowed: set, state: Dict[str, Any], stop: threading.Event,
              once: bool = False) -> None:
    while not stop.is_set():
        updates = tg.get_updates(int(state.get("offset") or 0))
        if updates is None:
            # شبكة واقعة — مهلة قبل المحاولة الجاية (بلا لوب محموم)
            if once:
                return
            stop.wait(20)
            continue
        for update in updates:
            state["offset"] = int(update.get("update_id", 0)) + 1
            handle_update(tg, update, allowed, state)
        if updates:
            _save_state(state)
        if once:
            return


def reminder_loop(tg: Telegram, allowed: set, stop: threading.Event, interval: int = 30,
                  once: bool = False) -> None:
    while not stop.is_set():
        try:
            count = reminders_cycle(tg, allowed)
            if count:
                log(f"reminders sent: {count}")
        except Exception as exc:
            log(f"reminder cycle error: {type(exc).__name__}: {exc}")
        if once:
            return
        stop.wait(interval)


# ------------------------------------------------------------------ main
def _lock_ok() -> bool:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            if time.time() - LOCK_FILE.stat().st_mtime < 900:
                return False
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            return False
    try:
        with LOCK_FILE.open("x", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        return True
    except FileExistsError:
        return False


def start_background() -> Optional[threading.Event]:
    """تشغيل الجسر كخيوط خلفية داخل عملية الويب (تكامل 2026-10-16 — عقدة الورشة).

    يرجع threading.Event للإيقاف، أو None صادقًا لو البدء تعذّر:
    بلا توكن / بلا محادثات مسموحة / webhook مسجّل على البوت / نسخة تانية شغّالة.
    نفس حمايات الوضع المستقل: قفل single-instance + رفض التعارض مع الويب هوك.
    """
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    allowed = _allowed_chats(env)
    if not token or not allowed:
        log("الجسر المدمج: بلا توكن/محادثات مسموحة في .env — تخطّي صادق")
        return None
    tg = Telegram(token)
    me = tg.call("getMe")
    if not me.get("ok"):
        log(f"الجسر المدمج: getMe فشل ({me.get('error')}) — تخطّي صادق")
        return None
    if tg.webhook_url():
        log("الجسر المدمج: webhook مسجّل على البوت — polling هيعمل تعارض 409؛ تخطّي (الاستقبال عبر الويب هوك السحابي)")
        return None
    if not _lock_ok():
        log("الجسر المدمج: نسخة تانية شغّالة — تخطّي (single instance)")
        return None
    import atexit
    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))
    state = _load_state()
    stop = threading.Event()
    threading.Thread(target=poll_loop, args=(tg, allowed, state, stop), name="nb-poll", daemon=True).start()
    threading.Thread(target=reminder_loop, args=(tg, allowed, stop), name="nb-remind", daemon=True).start()

    def _digest() -> None:
        while not stop.is_set():
            try:
                digest_cycle(tg, allowed, state)
            except Exception as exc:
                log(f"digest cycle error: {type(exc).__name__}: {exc}")
            stop.wait(20)
    threading.Thread(target=_digest, name="nb-digest", daemon=True).start()
    log("الجسر المدمج اشتغل مع الواجهة (poll + reminders + digest)")
    return stop


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="النوتبوك الذكية — جسر تليجرام")
    ap.add_argument("--watch", action="store_true", help="الخدمة الدائمة")
    ap.add_argument("--once", action="store_true", help="دورة واحدة (اختبار)")
    ap.add_argument("--test", action="store_true", help="إرسال رسالة اختبار")
    ap.add_argument("--send", type=str, help="إرسال نص محدد")
    ap.add_argument("--digest", action="store_true", help="إرسال الملخص الآن")
    args = ap.parse_args(argv)

    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log("TELEGRAM_BOT_TOKEN غير موجود في .env — توقف صادق")
        return 2
    allowed = _allowed_chats(env)
    if not allowed:
        log("OWNER_TELEGRAM_ID / ALLOWED_CHAT_IDS غير موجودين — توقف صادق")
        return 2
    tg = Telegram(token)
    chat_id = next(iter(allowed))

    me = tg.call("getMe")
    if not me.get("ok"):
        log(f"getMe فشل: {me.get('error')} — توقف صادق")
        return 2
    log(f"bot=@{((me.get('result') or {}).get('username'))} allowed={sorted(allowed)}")

    if args.test or args.send or args.digest:
        text = args.send or ("✅ النوتبوك الذكية متصلة — أي نوت تكتبه هنا هيتسجّل ويتصنّف فورًا."
                             if args.test else digest_text())
        ok = tg.send(chat_id, text)
        log(f"manual send ok={ok}")
        return 0 if ok else 2

    webhook = tg.webhook_url()
    if webhook:
        log(f"webhook مسجّل على البوت ({webhook[:60]}) — الاستقبال بالـpolling هيعمل تعارض 409.")
        log("الحل: إما فك الـwebhook من جهة السحابة، أو تشغيل الوضع --send للتذكيرات فقط.")
        if not args.once:
            return 3

    if args.once:
        reminders_cycle(tg, allowed)
        digest_cycle(tg, allowed, _load_state())
        poll_loop(tg, allowed, _load_state(), threading.Event(), once=True)
        log("once cycle done")
        return 0

    if not args.watch:
        ap.print_help()
        return 0

    if not _lock_ok():
        log("نسخة تانية شغّالة بالفعل — خروج (single instance)")
        return 0

    state = _load_state()
    stop = threading.Event()
    threads = [
        threading.Thread(target=poll_loop, args=(tg, allowed, state, stop), name="poll", daemon=True),
        threading.Thread(target=reminder_loop, args=(tg, allowed, stop), name="reminders", daemon=True),
    ]
    for th in threads:
        th.start()
    log("bridge started (poll + reminders)")
    try:
        while True:
            digest_cycle(tg, allowed, state)
            time.sleep(20)
    except KeyboardInterrupt:
        stop.set()
        log("bridge stopped by user")
    finally:
        LOCK_FILE.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())