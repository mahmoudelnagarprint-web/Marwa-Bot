# -*- coding: utf-8 -*-
"""بوت @Afkary22Bot — قناة المالك الشخصية 24/7 (R2).

- عميل Telegram بمكتبات القياسية فقط (urllib) — بلا python-telegram-bot.
- **Authorization middleware صارم**: كل update (message / edited / callback)
  يُفحص من خلال from.id == OWNER_TELEGRAM_ID — غير المالك يُتجاهل صمتًا
  ويُسجَّل سطر واحد. لا رد من أي نوع للغرباء.
- /start → قائمة Inline: 🏪 المحل | 🔧 الورشة | 🧠 الذاكرة | 📜 الخزنة.
- نص حر → ai_router (عربي local + سحابة) → يُحفظ → تأكيد عربي كامل.
- صوت → يُحفظ كملفات + نوت معلّق (التفريغ النصي: P2).
- حماية 409: webhook مسجّل → رفض صادق مع السبب قبل بدء الـpolling.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional

from nb import (ai_router, config, db, ha, intent, persona, proactive, prompt_vault,
                retail, squad, workshop)

API = "https://api.telegram.org/bot{token}/{method}"
FILE_API = "https://api.telegram.org/file/bot{token}/{path}"

DATA_DIR = config.DATA_DIR / "voice"


# ------------------------------------------------------------------ client
class TelegramClient:
    """غلاف خفيف على Telegram Bot API — صفر تبعيات."""

    def __init__(self, token: str, timeout: int = 30):
        self.token = token
        self.timeout = timeout

    def call(self, method: str, payload: Optional[Dict[str, Any]] = None,
             timeout: Optional[int] = None) -> Dict[str, Any]:
        data = urllib.parse.urlencode(payload or {}).encode("utf-8")
        req = urllib.request.Request(API.format(token=self.token, method=method), data=data)
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            return {"ok": False, "error": f"HTTP {exc.code}: {body}"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def get_me(self) -> Optional[str]:
        res = self.call("getMe")
        return (res.get("result") or {}).get("username") if res.get("ok") else None

    def get_webhook(self) -> str:
        res = self.call("getWebhookInfo")
        return (res.get("result") or {}).get("url") or "" if res.get("ok") else ""

    def get_updates(self, offset: int, timeout: int = 25) -> Optional[List[Dict[str, Any]]]:
        res = self.call("getUpdates",
                        {"offset": offset, "timeout": timeout,
                         "allowed_updates": '["message","edited_message","callback_query"]'},
                        timeout=timeout + 15)
        if not res.get("ok"):
            config.log(f"getUpdates فشل: {res.get('error')}")
            return None
        return res.get("result") or []

    @staticmethod
    def _kb(rows: List[List[tuple]]) -> Dict[str, Any]:
        return {"inline_keyboard": [[{"text": t, "callback_data": c} for t, c in row] for row in rows]}

    @staticmethod
    def _reply_kb(rows: List[List[str]]) -> Dict[str, Any]:
        """كيبورد سفلي ثابت — بيقعد تحت خانة الكتابة بدل ما يختفي."""
        return {"keyboard": [[{"text": t} for t in row] for row in rows],
                "resize_keyboard": True, "is_persistent": True}

    def send(self, chat_id: int, text: str, kb: Optional[List[List[tuple]]] = None,
             reply_to: Optional[int] = None, reply_kb: Optional[List[List[str]]] = None,
             kind: Optional[str] = None) -> bool:
        payload = {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": "true"}
        if kb:
            payload["reply_markup"] = json.dumps(self._kb(kb), ensure_ascii=False)
        elif reply_kb:
            payload["reply_markup"] = json.dumps(self._reply_kb(reply_kb), ensure_ascii=False)
        if reply_to:
            payload["reply_to_message_id"] = reply_to
        res = self.call("sendMessage", payload)
        if not res.get("ok"):
            config.log(f"send فشل إلى {chat_id}: {res.get('error')}")
        return bool(res.get("ok"))

    def edit(self, chat_id: int, message_id: int, text: str,
             kb: Optional[List[List[tuple]]] = None) -> bool:
        payload = {"chat_id": chat_id, "message_id": message_id, "text": text[:4000],
                   "disable_web_page_preview": "true"}
        if kb:
            payload["reply_markup"] = json.dumps(self._kb(kb), ensure_ascii=False)
        res = self.call("editMessageText", payload)
        return bool(res.get("ok"))

    def answer_cb(self, cb_id: str, text: Optional[str] = None) -> bool:
        payload = {"callback_query_id": cb_id}
        if text:
            payload["text"] = text[:200]
        return bool(self.call("answerCallbackQuery", payload).get("ok"))

    def typing(self, chat_id: int) -> None:
        self.call("sendChatAction", {"chat_id": chat_id, "action": "typing"})

    def file_path(self, file_id: str) -> Optional[str]:
        res = self.call("getFile", {"file_id": file_id})
        return (res.get("result") or {}).get("file_path") if res.get("ok") else None

    def download(self, file_path: str, dest) -> bool:
        url = FILE_API.format(token=self.token, path=file_path)
        try:
            with urllib.request.urlopen(url, timeout=90) as resp:
                dest.write_bytes(resp.read())
            return True
        except Exception as exc:
            config.log(f"تحميل ملف فشل: {type(exc).__name__}: {exc}")
            return False


# ------------------------------------------------------------------ قوائم
MAIN_KB = [
    [("🏪 نظام المحل", "sec:retail"), ("🔧 ورشة النجار برنت", "sec:workshop")],
    [("🧠 الذاكرة الثانية", "sec:brain"), ("📜 خزنة البرومبتات", "sec:vault")],
    [("📊 حالة المنظومة", "sec:status")],
]
BACK = [[("🔙 القائمة الرئيسية", "menu:main")]]

RETAIL_KB = [
    [("💵 آخر ملخص مالي", "retail:digest"), ("📦 طلبات مفتوحة", "retail:orders")],
    [("⚠️ مخزون ناقص", "retail:low"), ("🤝 تقارير الفريق", "retail:agents")],
] + BACK

WORKSHOP_KB = [
    [("⚙️ مهام قيد التنفيذ", "ws:list"), ("➕ إضافة شغلانة", "ws:new")],
    [("🪵 الخامات", "ws:materials"), ("🪫 خامات ناقصة", "ws:low")],
] + BACK

BRAIN_KB = [
    [("⏰ مستحق الآن", "brain:due"), ("📋 قائمتي", "brain:list")],
    [("🗣️ نادِ الفريق", "brain:squad"), ("🗂️ رادار المشاريع", "brain:radar")],
    [("🍅 بومودورو 25", "brain:pomo25"), ("🍅 بومودورو 50", "brain:pomo50")],
    [("➕ إضافة نوت", "brain:add")],
] + BACK

VAULT_KB = [
    [("📜 أحدث 5 برومبتات", "vault:recent"), ("🔍 بحث في الخزنة", "vault:search")],
    [("➕ إضافة برومبت", "vault:new")],
] + BACK

# الكيبورد السفلي الثابت — بيوصله من أي مكان بكبسة واحدة (A7)
MAIN_REPLY_KB = [["🧠 أفكاري", "📋 مهام اليوم"], ["🔧 الورشة", "🍅 بومودورو"]]


def reminder_kb(note_id: int) -> List[List[tuple]]:
    """خمس أزرار Inline لأي تذكير/مهمة (A7): تم | أجّل | الميعاد | صنّف | امسح.

    المصدر الحقيقي في `proactive.capture_kb` — الرسائل الفورية (هنا) والرسائل
    الاستباقية (الصندوق) لازم يبقوا **نفس الأزرار بالحرف**، وإلا المستخدم
    يشوف شكلين لأزرار تذكير واحدة.
    """
    return proactive.capture_kb(note_id)


CAPTURE_KB = [[("🧠 أفكاري", "brain:list"), ("📋 مهام اليوم", "brain:today")],
              [("⏰ المستحق", "brain:due")]] + BACK

WELCOME = (
    "أهلاً يا أفكار 👋\n"
    "أنا «فوفا» — مساعدتك في «أفكاري».\n\n"
    "• ابعتلي **أي حاجة في دماغك** وأنا أقرر: كلام = نردّ عليك، حاجة تتحفظ = أسجّلها\n"
    "• «📋 مهام اليوم» تشوف مهامك ومواعيدك\n"
    "• «🔧 الورشة» شغلانات وخامات النجار برنت\n"
    "• «🍅 بومودورو» جلسة تركيز\n\n"
    "ومفيش حاجة تتحفظ من غير ما أقولك ✅"
)

HELP = (
    "أنا فوفا — دي أسرع حاجات:\n"
    "• «مهام اليوم» / «المستحق» / «قائمتي»\n"
    "• «حالة» — وقفة على العقدة والقيادة\n"
    "• «تم 5» / «أجّل 5» / «صنّف 5 حسابات» / «احذف 5»\n"
    "• «بومودورو 25» — جلسة تركيز\n"
    "• أي نص حر: أنا بفرّق بنفسي — يا كلام نردّه، يا حاجة تتحفظ فأقولك ✅\n"
    "• وكل تذكير جايلك فيه أزرار: تم | أجّل | الميعاد | صنّف | امسح"
)


# ------------------------------------------------------------------ auth
def _extract_from(update: Dict[str, Any]) -> Dict[str, Any]:
    msg = update.get("message") or update.get("edited_message") or {}
    if msg:
        return msg.get("from") or {}
    cq = update.get("callback_query") or {}
    return cq.get("from") or {}


def authorize(update: Dict[str, Any]) -> bool:
    frm = _extract_from(update)
    uid = frm.get("id")
    return bool(uid and config.OWNER_TELEGRAM_ID and uid == config.OWNER_TELEGRAM_ID)


# ------------------------------------------------------------------ نصوص
def _fmt_capture(n: Dict[str, Any]) -> str:
    kind = n.get("kind") or "note"
    icon = ai_router.KIND_LABELS.get(kind, "📝")
    line = f"#{n['id']} {icon} {n.get('title') or '(بلا عنوان)'}"
    if n.get("category"):
        line += f" | {n['category']}"
    if n.get("due_at"):
        d = n["due_at"]
        ds = d.astimezone().strftime("%m-%d %H:%M") if hasattr(d, "astimezone") else str(d)[:11]
        line += f" | ← {ds}"
    return line


# ------------------------------------------------------------------ عارضات
def _brain_due() -> str:
    """المستحق الآن: متأخر + مستحق النهاردة."""
    overdue = db.overdue_captures()
    due_today = db.q("""SELECT * FROM captures
                        WHERE status='open' AND due_at IS NOT NULL
                          AND due_at::date = %s::date
                        ORDER BY due_at ASC LIMIT 20""", (db.now_local_date(),))
    if not overdue and not due_today:
        return "مفيش حاجة مستحقة دلوقتي — يومك فاضي ✅"
    lines = ["⏰ المستحق الآن:"]
    if overdue:
        lines.append(f"\n🔴 متأخر ({len(overdue)}):")
        lines += ["  " + _fmt_capture(n) for n in overdue[:10]]
    if due_today:
        lines.append(f"\n🟡 النهاردة ({len(due_today)}):")
        lines += ["  " + _fmt_capture(n) for n in due_today[:10]]
    lines.append("\n«تم #رقم» يقفل | «أجل #رقم ساعه» يؤجّل")
    return "\n".join(lines)


def _brain_today() -> str:
    """مهام اليوم: متأخر ← النهاردة ← المهم المفتوح. ده الزر الرئيسي في الكيبورد."""
    overdue = db.overdue_captures()
    due_today = db.q("""SELECT * FROM captures
                        WHERE status='open' AND due_at IS NOT NULL
                          AND due_at::date = %s::date
                        ORDER BY due_at ASC LIMIT 20""", (db.now_local_date(),))
    important = db.q("""SELECT * FROM captures
                        WHERE status='open' AND priority IN ('high','urgent')
                          AND (due_at IS NULL OR due_at::date > %s::date)
                        ORDER BY CASE priority WHEN 'urgent' THEN 0 ELSE 1 END, id DESC
                        LIMIT 10""", (db.now_local_date(),))
    if not (overdue or due_today or important):
        return "📋 مهام اليوم فاضية — مفيش حاجة مستحقة ولا مهمة معلّقة ✅"
    lines = ["📋 مهام اليوم"]
    if overdue:
        lines.append(f"\n🔴 متأخر ({len(overdue)}):")
        lines += ["  " + _fmt_capture(n) for n in overdue[:8]]
    if due_today:
        lines.append(f"\n🟡 النهاردة ({len(due_today)}):")
        lines += ["  " + _fmt_capture(n) for n in due_today[:8]]
    if important:
        lines.append(f"\n⭐ مهم ومفتوح ({len(important)}):")
        lines += ["  " + _fmt_capture(n) for n in important[:6]]
    lines.append("\nاضغط على أي تذكير وفيه أزرار: تم | أجّل | الميعاد | صنّف | امسح")
    return "\n".join(lines)


def _brain_list() -> str:
    """قائمتي: النوتات/المهام المفتوحة."""
    rows = db.list_captures(status="open", limit=40)
    if not rows:
        return "قائمتك فاضية — مفيش حاجة مفتوحة ✅"
    lines = [f"📋 قائمتي — مفتوح: {len(rows)}"]
    lines += ["  " + _fmt_capture(n) for n in rows[:25]]
    if len(rows) > 25:
        lines.append(f"  … و{len(rows) - 25} كمان")
    return "\n".join(lines)


def _brain_radar() -> str:
    """رادار المشاريع: اللي واقف/راكد."""
    projects = proactive.radar_projects()
    if not projects:
        return "🗂️ الرادار صافي — مفيش مشاريع راكدة 👌"
    lines = [f"🗂️ رادار المشاريع — راكد: {len(projects)}"]
    for p in projects[:15]:
        days = p.get("days_stuck")
        lines.append(f"  • {p.get('title') or p.get('id')}"
                     + (f" | واقف {days} يوم" if days is not None else ""))
    return "\n".join(lines)


def _retail_digest() -> str:
    """آخر ملخص مالي من لقطة المحل (قراءة فقط)."""
    snap = retail.last_snapshot()
    if not snap:
        return "🏪 مفيش لقطة محل بعد — ابعت /pull أو استنى الدورة الجاية."
    try:
        return retail.digest(snap)
    except Exception as exc:
        return f"❌ تعذر تجهيز الملخص ({type(exc).__name__}) — آخر لقطة: {str(snap['captured_at'])[:16]}"


def _retail_orders() -> str:
    """طلبات مفتوحة من لقطة المحل."""
    snap = retail.last_snapshot()
    if not snap:
        return "🏪 مفيش لقطة محل بعد."
    payload = snap.get("payload") or {}
    orders = payload.get("open_orders") if isinstance(payload, dict) else None
    if not orders:
        return "📦 مفيش طلبات مفتوحة في آخر لقطة ✅"
    lines = [f"📦 طلبات مفتوحة: {len(orders)}"]
    for o in list(orders)[:20]:
        if isinstance(o, dict):
            lines.append(f"  • {o.get('id') or ''} {o.get('customer') or ''} "
                         f"{o.get('status') or ''} {o.get('total') or ''}".rstrip())
        else:
            lines.append(f"  • {o}")
    return "\n".join(lines)


def _retail_low() -> str:
    """مخزون ناقص من لقطة المحل."""
    snap = retail.last_snapshot()
    if not snap:
        return "🏪 مفيش لقطة محل بعد."
    payload = snap.get("payload") or {}
    low = payload.get("low_stock") if isinstance(payload, dict) else None
    if not low:
        return "⚠️ مفيش مخزون ناقص في آخر لقطة ✅"
    lines = [f"⚠️ مخزون ناقص: {len(low)}"]
    for it in list(low)[:20]:
        if isinstance(it, dict):
            lines.append(f"  • {it.get('name') or it.get('id')} — "
                         f"{it.get('qty') if it.get('qty') is not None else '?'}")
        else:
            lines.append(f"  • {it}")
    return "\n".join(lines)


def _retail_agents() -> str:
    """تقارير الفريق الواردة + آخر مناداة."""
    rows = retail.latest_agent_reports(10)
    parts = []
    if not rows:
        parts.append("🤝 مفيش تقارير وكلاء لسه.")
    else:
        parts.append(f"🤝 تقارير الفريق — غير مقروء/مهم: {len(rows)}")
        for r in rows[:10]:
            parts.append(f"  • [{r['severity']}] {r['agent']}: {str(r['title'])[:70]}")
    try:
        parts.append("\n" + squad.briefing_line())
    except Exception:
        pass
    parts.append("\n«الفريق» = أنادي كل الوكلاء وأسألهم عن ملاحظاتهم دلوقتي")
    return "\n".join(parts)


def _ws_list() -> str:
    """مهام الورشة قيد التنفيذ."""
    jobs = workshop.list_jobs(limit=30)
    jobs = [j for j in jobs if j.get("status") not in ("delivered", "cancelled")]
    if not jobs:
        return "⚙️ مفيش شغلانات مفتوحة في الورشة ✅"
    lines = [f"⚙️ مهام قيد التنفيذ: {len(jobs)}"]
    lines += ["  " + workshop.format_job(j) for j in jobs[:20]]
    return "\n".join(lines)


def _ws_materials(low_only: bool = False) -> str:
    """خامات الورشة (أو الناقص منها بس)."""
    rows = workshop.low_stock() if low_only else workshop.list_materials(limit=60)
    title = "🪫 خامات ناقصة" if low_only else "🪵 الخامات"
    if not rows:
        return (f"{title}: مفيش ✅" if low_only else "🪵 مفيش خامات مسجّلة لسه.")
    lines = [f"{title}: {len(rows)}"]
    for m in rows[:30]:
        lines.append(f"  • {m.get('name')} — {m.get('qty')} {m.get('unit') or ''}"
                     f" (حد أدنى {m.get('min_qty')})".rstrip())
    return "\n".join(lines)


def _vault_recent() -> str:
    """أحدث برومبتات في الخزنة."""
    rows = prompt_vault.list_prompts(limit=5)
    if not rows:
        return "📜 الخزنة فاضية — ابعت «إضافة برومبت» وأبدأ أحفظ."
    lines = [f"📜 أحدث {len(rows)} برومبت:"]
    for p in rows:
        lines.append(f"  • #{p['id']} {str(p.get('title'))[:60]} | {p.get('category') or 'عام'}")
    return "\n".join(lines)


def _do_pomodoro(tg: TelegramClient, chat_id: int, minutes: int) -> str:
    """يبدأ بومودورو ويأكّد — مع رسالة إغلاق عند الانتهاء."""
    try:
        p = proactive.start_pomodoro(minutes=minutes)
    except Exception as exc:
        return f"❌ تعذر بدء البومودورو ({type(exc).__name__}: {exc})"
    ends = p.get("ends_at")
    ends_txt = ends.astimezone().strftime("%H:%M") if hasattr(ends, "astimezone") else str(ends)[11:16]
    return (f"🍅 بدأ بومودورو {minutes} دقيقة — ينتهي {ends_txt}.\n"
            "ركّز على مهمة واحدة، وأنا هأكدلك أول ما يخلّص 🔔")


def _do_squad(tg: TelegramClient, chat_id: int) -> str:
    """ينادي كل الفريق ويسأله عن ملاحظة/نوت/تذكير — ويجمّع الردود."""
    ok, why = squad.available()
    if not ok:
        return f"⚠️ مقدرش أنادي الفريق دلوقتي — {why}"
    # مؤشر «يكتب…» تجميلي: لو فشل ما يمنعش المناداة نفسها.
    try:
        tg.typing(chat_id)
    except Exception:
        pass
    try:
        return squad.rollcall_text(store=True)
    except Exception as exc:
        config.log(f"مناداة الفريق فشلت — {type(exc).__name__}: {exc}")
        return f"❌ حصل خطأ وأنا بنادي الفريق ({type(exc).__name__}: {exc})"


def status_text() -> str:
    st = ha.status()
    lines = [f"📊 حالة المنظومة — العقدة: {st['device_name']} ({st['node_id']})",
             f"دوري: {'⚡ قائد (يشغّل البوت والمهام)' if st['i_am_leader'] else '🛡️ غطاء جاهز'}"]
    leader = st.get("leader") or {}
    if leader.get("holder"):
        holder = "أنت" if leader["holder"] == st["node_id"] else leader["holder"]
        lines.append(f"القائد الحالي: {holder}")
    nodes = st.get("nodes") or []
    if nodes:
        lines.append("\nالعقد:")
        for nd in nodes:
            ls = nd["last_seen"]
            ls_txt = ls.strftime("%H:%M:%S") if hasattr(ls, "strftime") else str(ls)
            lines.append(f"  {'🟢' if nd.get('alive') else '🔴'} {nd['node_id']} — آخر نبضة {ls_txt}")
    try:
        from nb import providers
        drow, dmodel = providers.get_default()
        if drow:
            lines.append(f"\n☁️ مزود الـAI الافتراضي: {drow['name']} — {dmodel}")
        else:
            lines.append("\n☁️ مزود الـAI الافتراضي: لا يوجد")
    except Exception:
        pass
    snap = retail.last_snapshot()
    lines.append(f"🏪 آخر لقطة محل: {'لا يوجد' if not snap else str(snap['captured_at'])[:16]}")
    return "\n".join(lines)


# ------------------------------------------------------------------ حالة المحادثة
STATES: Dict[int, Dict[str, Any]] = {}


def _handle_state(tg: TelegramClient, chat_id: int, text: str):
    """مراحل متعددة الخطوات: شغلانة / خامة / برومبت / بحث."""
    S = STATES.get(chat_id)
    if not S:
        return None

    def _clear():
        STATES.pop(chat_id, None)

    step = S.get("step")
    if step == "ws_new_job":
        parts = [p.strip() for p in re.split(r"[|،]", text)]
        try:
            title = parts[1] if len(parts) > 1 and parts[1] else parts[0]
            jid = workshop.create_job(
                title=title,
                customer=parts[0] if len(parts) > 1 and parts[0] else None,
                price=float(parts[2]) if len(parts) > 2 and parts[2] else 0,
                due_date=parts[3] if len(parts) > 3 and parts[3] else None,
            )
            _clear()
            return "✅ اتحفظت الشغلانة:\n" + workshop.format_job(workshop.get_job(jid))
        except Exception as exc:
            return f"❌ {type(exc).__name__}: {exc}\nالصيغة: «العميل | الوصف | المبلغ | الميعاد»"
    if step == "ws_material_add":
        parts = [p.strip() for p in re.split(r"[|،]", text)]
        try:
            workshop.add_material(name=parts[0],
                                  qty=float(parts[2]) if len(parts) > 2 and parts[2] else 0,
                                  min_qty=float(parts[3]) if len(parts) > 3 and parts[3] else 0,
                                  unit_cost=float(parts[4]) if len(parts) > 4 and parts[4] else 0)
            _clear()
            return f"✅ اتحفظت الخامة «{parts[0]}»"
        except Exception as exc:
            return f"❌ {type(exc).__name__}: {exc}\nالصيغة: «الاسم | النوع | الكمية | الحد الأدنى | سعر الوحدة»"
    if step == "vault_title":
        STATES[chat_id] = {"step": "vault_body", "title": text}
        return None, "تمام — اكتب نص البرومبت نفسه دلوقتي 📝"
    if step == "vault_body":
        try:
            pid = prompt_vault.save_prompt(title=S.get("title", ""), body=text)
            _clear()
            return f"📜 البرومبت # {pid} اتخزن في الخزنة."
        except Exception as exc:
            return f"❌ {type(exc).__name__}: {exc}"
    if step == "vault_search":
        res = prompt_vault.search(text, k=4)
        _clear()
        if not res["results"]:
            return "مفيش نتايج للبحث ده 🤷"
        head = "🔍 دلالي:" if res["mode"] == "semantic" else "🔍 كلمات:"
        return head + "\n\n" + "\n\n".join(prompt_vault.format_result(p) for p in res["results"])
    return None


def _norm_set(*variants: str) -> tuple:
    """يطبّع صيغ الأوامر بنفس مُطبِّع ai_router.

    مهم: `ai_router.normalize` بيوحّد (ة→ه) و(ى→ي) و(أ→ا)، فمقارنة الرد
    المُطبَّع بصيغة مكتوبة يدوي زي «قائمتي» أو «حالة» كانت **بتفشل دايمًا**
    والأمر يقع على النص الحر. نطبّع الصيغ هنا عشان المطابقة تنجح.
    """
    return tuple(ai_router.normalize(v) for v in variants)


# الإيموجي اللي في أزرار الكيبورد السفلي بيتشال قبل المطابقة — التليجرام
# بيبعت نص الزر كامل بالإيموجي، فـ«📋 مهام اليوم» ما كانتش بتساوي «مهام اليوم».
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\uFE0F\u200d]+")


def _bare(text: str) -> str:
    """نص من غير إيموجي ومسافات زيادة — للمطابقة مع نصوص أزرار الكيبورد."""
    return re.sub(r"\s+", " ", _EMOJI_RE.sub(" ", ai_router.normalize(text or ""))).strip()


# ------------------------------------------------------------------ أوامر نصية
def _handle_command(tg: TelegramClient, chat_id: int, text: str) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return "ابعتلي النص 🙂"
    low = ai_router.normalize(t)
    bare = _bare(t)   # من غير إيموجي — عشان أزرار الكيبورد السفلي (A7)

    # --- أزرار الكيبورد السفلي الأربعة: التليجرام بيبعت نص الزر كامل بالإيموجي ---
    # من غير السطور دي، «📋 مهام اليوم» كان بيقع على النص الحر ويروح للموديل!
    if bare in _norm_set("افكاري", "/brain", "الذاكره", "ذاكرتي"):
        return _brain_list(), BACK
    if bare in _norm_set("مهام اليوم", "مهام النهارده", "/today", "اليوم"):
        return _brain_today(), BACK
    if bare in _norm_set("الورشه", "/workshop", "شغلاناتي", "الورشه والمخزون"):
        return _ws_list(), BACK
    m = re.match(r"^\s*(?:بومودورو|بمو?دورو)\s*(\d{1,3})?\s*$", bare)
    if m:
        return _do_pomodoro(tg, chat_id, int(m.group(1)) if m.group(1) else 25), None

    if low in _norm_set("/start", "بداية", "ابدأ"):
        return WELCOME, MAIN_KB
    if low in _norm_set("/help", "مساعدة"):
        return HELP, None
    if low in _norm_set("المستحق", "/due", "المواعيد"):
        return _brain_due(), None
    if low in _norm_set("قائمتي", "/list", "المفتوح"):
        return _brain_list(), None
    if low in _norm_set("الملخص", "/digest"):
        return proactive.briefing_text(), None
    if low in _norm_set("الفريق", "/squad", "نادي الفريق", "نادِ الفريق", "الوكلاء"):
        return _do_squad(tg, chat_id), None
    if low in _norm_set("حالة", "الوضع", "/status"):
        return status_text(), None

    m = re.match(r"^\s*(?:بومودورو|بمو?دورو)\s*(\d{1,3})?\s*$", low)
    if m:
        minutes = int(m.group(1)) if m.group(1) else 25
        return _do_pomodoro(tg, chat_id, minutes), None
    if low in _norm_set("الغاء بومودورو", "ألغى بومودورو", "الغاء البومودورو"):
        ok = proactive.cancel_latest_pomodoro()
        return ("اتلغى البومودورو الجاري ✔️" if ok else "مفيش بومودورو شغال دلوقتي"), None

    m = re.match(r"^\s*(?:تم|خلصت|اقفل|قفل)\s*#?(\d+)\s*$", low)
    if m:
        nid = int(m.group(1))
        note = db.q("SELECT id, title, kind FROM captures WHERE id=%s", (nid,), one=True)
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        db.set_capture_status(nid, "done")
        return f"✅ تمام — قفلت #{nid}: {note['title']}"

    m = re.match(r"^\s*(?:اجل|أجل)\s*#?(\d+)\s*(ساعه?|ساعات|دقيقه?|دقايق|يوم|ايام)?\s*$", low)
    if m:
        nid = int(m.group(1))
        note = db.q("SELECT id FROM captures WHERE id=%s", (nid,), )
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        unit = m.group(2) or ""
        minutes = 1440 if ("يوم" in unit or "ايام" in unit) else (15 if ("دقيق" in unit) else 60)
        db.snooze_capture(nid, minutes)
        return f"⏰ أجّلت #{nid} ساعة ({minutes} د)"

    m = re.match(r"^\s*(?:احذف)\s*#?(\d+)\s*$", low)
    if m:
        nid = int(m.group(1))
        note = db.q("SELECT id, title FROM captures WHERE id=%s", (nid,), one=True)
        if not note:
            return f"مفيش نوت رقم #{nid} 🤔"
        db.x("DELETE FROM captures WHERE id=%s", (nid,))
        return f"🗑️ اتمسح #{nid}: {note['title']}"

    m = re.match(r"^\s*(?:مشروع)\s*#?(\d+)\s*(?:تم|خلص)\s*$", low)
    if m:
        pid = int(m.group(1))
        ok = db.x("UPDATE projects SET status='done', updated_at=now() WHERE id=%s AND status='active'", (pid,))
        return ("🎉 تمام — المشروع اتعمل ✅" if ok else "مفيش مشروع نشط بالرقم ده")

    m = re.match(r"^\s*(?:صنف|تصنيف)\s*#?(\d+)\s*(.+?)\s*$", low)
    if m:
        nid, cat = int(m.group(1)), m.group(2).strip()
        db.x("UPDATE captures SET category=%s, updated_at=now() WHERE id=%s", (cat, nid))
        return f"🗂️ نقلت #{nid} لتصنيف «{cat}»"

    return None


# ------------------------------------------------------------------ القلب المشترك
def process_text(text: str, chat_id: Optional[int] = None,
                 source: str = "telegram") -> Dict[str, Any]:
    """بوابة النوايا ← كلام نردّه ولا حاجة تتحفظ. **المصدر الوحيد** للمنطق ده.

    البوت (تليجرام) والويب (/api/chat) والبريدج بينادوا الدالة دي، عشان
    الحفظ يحصل في مكان واحد بالظبط — لو كل واجهة كتبت منطقها، هيحصل
    تباعد: نفس الجملة تتحفظ من التليجرام وما تتحفظش من الويب.

    بترجّع: `{ok, intent, reply, kb, note_id, routed_by, reason, error}`.
    **مابتبعتش حاجة لأي حد** — الإرسال مسؤولية اللي بينادي.
    """
    cid_chat = int(chat_id or config.OWNER_TELEGRAM_ID or 0)
    out: Dict[str, Any] = {"ok": True, "intent": "chat", "reply": "", "kb": None,
                           "note_id": None, "routed_by": "rules", "reason": "",
                           "error": None}
    try:
        verdict = intent.gate(text, chat_id=cid_chat, source=source)
    except Exception as exc:
        config.log(f"intent gate error: {type(exc).__name__}: {exc}")
        verdict = {"intent": "chat", "reply": None, "analysis": None,
                   "routed_by": "rules", "reason": f"خطأ في البوابة: {type(exc).__name__}"}

    persona.remember(cid_chat, "user", text)
    out["routed_by"] = verdict.get("routed_by") or "rules"
    out["reason"] = verdict.get("reason") or ""
    config.log(f"intent[{source}]: {verdict['intent']} | {out['reason'][:160]} | "
               f"routed_by={out['routed_by']} | chat={cid_chat}")

    if verdict["intent"] == "chat":
        reply = verdict.get("reply")
        if not reply:
            reply, _meta = persona.reply(text, chat_id=cid_chat)
        persona.remember(cid_chat, "assistant", reply)
        out["reply"] = reply
        return out

    analysis = verdict.get("analysis") or {}
    try:
        note_id = db.add_capture(analysis)
    except Exception as exc:
        config.log(f"capture error: {type(exc).__name__}: {exc}")
        out.update(ok=False, error=f"{type(exc).__name__}: {exc}",
                   reply=(f"❌ مش قادر أحفظ دلوقتي ({type(exc).__name__}) — "
                          "ما افترضتش أي نتيجة."))
        return out

    analysis.setdefault("meta", {})
    if verdict.get("reference"):
        analysis["meta"]["reference_of"] = verdict["reference"][:200]
    confirm = ai_router.confirm_message(analysis, note_id)
    persona.remember(cid_chat, "assistant", confirm, {"note_id": note_id})
    out.update(intent="capture", reply=confirm, note_id=note_id,
               kb=reminder_kb(note_id) if analysis.get("due_at") else CAPTURE_KB)
    return out


# ------------------------------------------------------------------ استقبال update
def _handle_message(tg: TelegramClient, msg: Dict[str, Any]) -> None:
    chat_id = (msg.get("chat") or {}).get("id")
    if chat_id is None:
        return
    text = (msg.get("text") or msg.get("caption") or "").strip()
    if "voice" in msg:
        _handle_voice(tg, chat_id, msg)
        return
    if not text:
        tg.send(chat_id, "ابعتلي نص — الصور والملفات مش مدعومة دلوقتي 🙂")
        return

    # مرحلة محادثة؟ (فسرها أولًا حتى لو "تم 1" — المرحلة تحكمها الحالة)
    try:
        staged = _handle_state(tg, chat_id, text)
        if staged is not None:
            if isinstance(staged, tuple):
                reply, kb = staged
                tg.send(chat_id, reply, kb=kb)
            else:
                tg.send(chat_id, staged, kb=BACK if chat_id in STATES else None)
            return
    except Exception as exc:
        config.log(f"state error: {type(exc).__name__}: {exc}")

    cmd = None
    try:
        cmd = _handle_command(tg, chat_id, text)
    except Exception as exc:
        cmd = f"❌ خطأ في تنفيذ الأمر ({type(exc).__name__})"
    if cmd is not None:
        if isinstance(cmd, tuple):
            reply, kb = cmd
            tg.send(chat_id, reply, kb=kb)
        else:
            tg.send(chat_id, cmd, kb=BACK if chat_id not in STATES else None)
        return

    # غير كده: بوابة النوايا تقرر — كلام ولا حاجة تتحفظ؟ (A1/A2/A5/A6)
    #
    # قبل كده كان أي نص حر بيتبعت على route() ويتحفظ فورًا، فكلمة «هاي» اتحفظت
    # كنوت. دلوقتي: الافتراضي محادثة، والحفظ محتاج دليل صريح أو حكم الموديل.
    # المنطق نفسه في `process_text` عشان الويب والبريدج يستخدموه بلا نسخة تانية.
    tg.typing(chat_id)
    res = process_text(text, chat_id=chat_id, source="telegram")
    if res["intent"] == "chat":
        tg.send(chat_id, res["reply"], reply_kb=MAIN_REPLY_KB)
        return
    if not res["ok"]:
        tg.send(chat_id, res["reply"], reply_kb=MAIN_REPLY_KB)
        return
    tg.send(chat_id, res["reply"], kb=res["kb"], reply_kb=MAIN_REPLY_KB)


def _handle_voice(tg: TelegramClient, chat_id: int, msg: Dict[str, Any]) -> None:
    voice = msg.get("voice") or {}
    fid = voice.get("file_id")
    if not fid:
        tg.send(chat_id, "مبقدرش أوصل للملف ده 🤔")
        return
    fpath = tg.file_path(fid)
    if not fpath:
        tg.send(chat_id, "مفيش مسار للملف — جرب تاني")
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATA_DIR / f"voice-{int(datetime.now().timestamp())}.ogg"
    ok = tg.download(fpath, dest)
    if not ok:
        tg.send(chat_id, "فشل تحميل الملف الصوتي")
        return
    analysis = ai_router.analyze_local(f"🎙️ رسالة صوتية — {datetime.now():%Y-%m-%d %H:%M}", source="voice")
    analysis["meta"] = {"voice_file": str(dest), "pending_transcription": True, "duration_sec": voice.get("duration")}
    cid = db.add_capture(analysis)
    tg.send(chat_id, f"🎙️ صوتك اتسجل (#{cid}).\n"
                     "التفريغ النصي والتحليل الكامل هيتضافوا في مرحلة P2 (Whisper محلي على جهاز الورشة).")


# ------------------------------------------------------------------ callback
def _handle_capture_cb(tg: TelegramClient, chat_id: int, message_id: Optional[int],
                       data: str) -> None:
    """cap:done|snooze|due|cat|del:<id> — التعديل الفوري على النوت/التذكير."""
    parts = data.split(":")
    if len(parts) < 3:
        return
    action, raw_id = parts[1], parts[2]
    try:
        nid = int(raw_id)
    except ValueError:
        return
    note = db.q("SELECT id, title, kind, category, due_at FROM captures WHERE id=%s",
                (nid,), one=True)
    if not note:
        tg.send(chat_id, f"مفيش نوت #{nid} 🤔", reply_kb=MAIN_REPLY_KB)
        return

    if action == "done":
        db.set_capture_status(nid, "done")
        text, kb = f"✅ تمام يا أفكار — قفلت #{nid}: {note['title']}", None
    elif action == "snooze":
        db.snooze_capture(nid, 60)
        text, kb = f"⏰ أجّلت #{nid} ساعة — هرجّع أفكرك.", reminder_kb(nid)
    elif action == "due":
        when = note.get("due_at")
        when_txt = when.astimezone().strftime("%Y-%m-%d %H:%M") if when else "مفيش ميعاد"
        text, kb = (f"📅 #{nid}: {note['title']}\n• الميعاد الحالي: {when_txt}\n"
                    "عايز أغيّره؟ ابعت «فكرني <الميعاد الجديد>»."), reminder_kb(nid)
    elif action == "cat":
        STATES[chat_id] = {"step": "cap_category", "note_id": nid}
        text, kb = (f"🗂️ #{nid}: {note['title']}\n"
                    f"• التصنيف الحالي: {note.get('category') or 'غير مصنف'}\n"
                    "ابعت اسم التصنيف الجديد."), BACK
    elif action == "del":
        db.x("DELETE FROM captures WHERE id=%s", (nid,))
        text, kb = f"🗑️ اتمسح #{nid}: {note['title']}", None
    else:
        return

    if message_id and tg.edit(chat_id, message_id, text, kb=kb):
        return
    tg.send(chat_id, text, kb=kb, reply_kb=MAIN_REPLY_KB)


def _handle_callback(tg: TelegramClient, cq: Dict[str, Any]) -> None:
    data = cq.get("data") or ""
    msg = cq.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    cbid = cq.get("id")
    if chat_id is None:
        return
    tg.answer_cb(cbid)

    # أزرار الالتقاط (cap:…) — بتتولّد مع كل تذكير/مهمة، وبتعدّل نفس الجدول
    if data.startswith("cap:"):
        _handle_capture_cb(tg, chat_id, message_id, data)
        return

    text, kb = None, None
    if data == "menu:main":
        text, kb = WELCOME, MAIN_KB
    elif data == "sec:retail":
        text, kb = "🏪 نظام المحل — اختر:", RETAIL_KB
    elif data == "sec:workshop":
        text, kb = "🔧 ورشة النجار برنت — اختر:", WORKSHOP_KB
    elif data == "sec:brain":
        text, kb = "🧠 الذاكرة الثانية — اختر:", BRAIN_KB
    elif data == "sec:vault":
        text, kb = "📜 خزنة البرومبتات — اختر:", VAULT_KB
    elif data == "sec:status":
        text = status_text()
    elif data == "retail:digest":
        text = _retail_digest()
    elif data == "retail:orders":
        text = _retail_orders()
    elif data == "retail:low":
        text = _retail_low()
    elif data == "retail:agents":
        text = _retail_agents()
    elif data == "ws:list":
        text = _ws_list()
    elif data == "ws:materials":
        text = _ws_materials(low_only=False)
    elif data == "ws:low":
        text = _ws_materials(low_only=True)
    elif data == "ws:new":
        STATES[chat_id] = {"step": "ws_new_job"}
        text, kb = "اللي يثبت الورشة — الصيغة:\n«العميل | الوصف | المبلغ | الميعاد»", BACK
    elif data == "brain:due":
        text = _brain_due()
    elif data == "brain:today":
        text = _brain_today()
    elif data == "brain:list":
        text = _brain_list()
    elif data == "brain:radar":
        text = _brain_radar()
    elif data == "brain:squad":
        text = _do_squad(tg, chat_id)
    elif data == "brain:pomo25":
        text = _do_pomodoro(tg, chat_id, 25)
    elif data == "brain:pomo50":
        text = _do_pomodoro(tg, chat_id, 50)
    elif data == "brain:add":
        STATES[chat_id] = {"step": "brain_note"}
        text, kb = "اكتب النوت/المهمة — وأنا أصنّفه فورًا ✍️", BACK
    elif data == "vault:recent":
        text = _vault_recent()
    elif data == "vault:search":
        STATES[chat_id] = {"step": "vault_search"}
        text, kb = "ابعت كلمة/سؤال البحث — وأنا أدوّر دلاليًا في الخزنة 🔍", BACK
    elif data == "vault:new":
        STATES[chat_id] = {"step": "vault_title"}
        text, kb = "ابعت عنوان البرومبت الأول 📕", BACK

    if text is None:
        return
    if message_id and tg.edit(chat_id, message_id, text, kb=kb):
        return
    tg.send(chat_id, text, kb=kb)


# ------------------------------------------------------------------ main loop
def run(token: str, stop: threading.Event) -> None:
    tg = TelegramClient(token)

    me = tg.get_me()
    if not me:
        config.log(f"البوت لم يبدأ: getMe فشل (توكن خاطئ؟) — السبب الصادق في السجل")
        return
    config.log(f"بوت أفكري يعمل: @{me} | المالك الوحيد: {config.OWNER_TELEGRAM_ID}")

    webhook = tg.get_webhook()
    if webhook:
        config.log(f"webhook مسجّل على البوت ({webhook[:60]}) — polling هيعمل تعارض 409؛ توقف صادق")
        return

    offset = int(ha.get_bot_state("offset", "0"))
    config.log(f"بدء الـpolling من offset={offset}")
    last_cycle = 0.0
    while not stop.is_set():
        updates = tg.get_updates(offset)
        if updates is None:
            stop.wait(20)
            continue
        for upd in updates:
            offset = int(upd.get("update_id", 0)) + 1
            try:
                if not authorize(upd):
                    config.log(f"مهمل تحديث من غير المالك: user={_extract_from(upd).get('id')}")
                    continue
                if "message" in upd:
                    _handle_message(tg, upd["message"])
                elif "edited_message" in upd:
                    _handle_message(tg, upd["edited_message"])
                elif "callback_query" in upd:
                    _handle_callback(tg, upd["callback_query"])
            except Exception as exc:
                config.log(f"خطأ في معالجة التحديث: {type(exc).__name__}: {exc}")
        try:
            ha.set_bot_state("offset", str(offset))
        except Exception:
            pass
        # المحرك الاستباقي — بين الـlong-polls
        try:
            if time.monotonic() - last_cycle >= 30:
                proactive.run_cycle(tg.send)
                last_cycle = time.monotonic()
        except Exception as exc:
            config.log(f"proactive cycle error: {type(exc).__name__}: {exc}")
    config.log("بوت أفكري توقف (كلفت بالإيقاف)")
