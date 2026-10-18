# -*- coding: utf-8 -*-
"""المحرك الاستباقي — R5 (Project Radar & Timeboxing).

يعمل على **عقدة القيادة فقط**. كل الرسائل تمر من صندوق إرسال واحد (outbox)
بمفاتيح منع تكرار — فلا يوجد إرسال مزدوج حتى لو تبدّلت العقدتين.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from nb import config, db, prayer, retail


def enqueue(chat_id: int, body: str, kind: str = "plain",
            dedupe_key: Optional[str] = None) -> bool:
    """إضافة رسالة للصندوق — dedupe_key يمنع التكرار (تعارض = تجاهل صامت)."""
    row = db.q("""INSERT INTO outbox(chat_id, body, kind, dedupe_key)
                  VALUES (%s,%s,%s,%s)
                  ON CONFLICT DO NOTHING RETURNING id""",
               (chat_id, body[:4000], kind, dedupe_key), one=True)
    return bool(row)


def flush(sender: Callable[[int, str], bool], limit: int = 8) -> int:
    """إرسال الرسائل المستحقة — يرجع عدد المرسل فعليًا."""
    rows = db.q("""SELECT * FROM outbox
                   WHERE sent_at IS NULL AND due_at <= now() AND attempts < 5
                   ORDER BY id LIMIT %s""", (limit,))
    sent = 0
    for r in rows:
        try:
            ok = sender(int(r["chat_id"]), r["body"])
        except Exception as exc:
            config.log(f"outbox send error #{r['id']}: {type(exc).__name__}: {exc}")
            ok = False
        if ok:
            db.x("UPDATE outbox SET sent_at = now() WHERE id=%s", (r["id"],))
            sent += 1
        else:
            db.x("UPDATE outbox SET attempts = attempts + 1 WHERE id=%s", (r["id"],))
    return sent


# ------------------------------------------------------------------ تذكيرات
def process_reminders() -> int:
    """المستحق الآن: صفّ في الصندوق ثم تقدّم الدورة/الإغلاق — بلا حلقات إعادة."""
    due = db.due_reminders()
    for n in due:
        lines = [f"⏰ تذكير #{n['id']}: {n['title']}"]
        if n.get("category"):
            lines.append(f"• التصنيف: {n['category']}")
        if n.get("due_at"):
            due_s = n["due_at"].astimezone().strftime("%Y-%m-%d %H:%M") if hasattr(n["due_at"], "astimezone") else str(n["due_at"])
            lines.append(f"• الميعاد: {due_s}")
        lines.append(f"• للتنفيذ: «تم {n['id']}» — للتأجيل: «أجّل {n['id']}»")
        enqueue(config.OWNER_TELEGRAM_ID, "\n".join(lines), "reminder",
                dedupe_key=f"rem-{n['id']}-{n['remind_at'].isoformat()}")
        every = n.get("remind_every") or "none"
        if every in ("daily", "weekly", "monthly"):
            step = {"daily": "1 day", "weekly": "1 week", "monthly": "30 days"}[every]
            db.x(f"""UPDATE captures
                     SET remind_at = GREATEST(remind_at, now()) + interval '{step}',
                         updated_at = now()
                     WHERE id = %s""", (n["id"],))
        else:
            db.x("""UPDATE captures SET remind_at = NULL, updated_at = now()
                    WHERE id = %s""", (n["id"],))
    return len(due)


# ------------------------------------------------------------------ الجدول اليومي
def _claim_daily(job: str) -> bool:
    """حجز دورة اليوم ذريًا بوقت محلي (القاهرة) — الفائز فقط يرسل."""
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    row = db.q("""INSERT INTO cron_runs(job, run_date, node_id)
                  VALUES (%s, %s, %s)
                  ON CONFLICT DO NOTHING RETURNING id""",
               (job, today, config.NODE_ID), one=True)
    return bool(row)


def _fmt(n: Dict[str, Any]) -> str:
    due = ""
    if n.get("due_at"):
        due_s = n["due_at"].astimezone().strftime("%m-%d %H:%M") if hasattr(n["due_at"], "astimezone") else str(n["due_at"])[:11]
        due = f" ← {due_s}"
    return f"• #{n['id']} {n['title'][:45]}{due}"


def radar_projects() -> List[Dict[str, Any]]:
    """المشاريع النشطة اللي سكنت أكثر من الحد المسموح."""
    days = int(db.get_setting("radar_stagnant_days", config.RADAR_STAGNANT_DAYS) or config.RADAR_STAGNANT_DAYS)
    return db.q("""SELECT * FROM projects
                    WHERE status = 'active'
                      AND last_activity_at < now() - make_interval(days => %s)
                    ORDER BY last_activity_at ASC LIMIT 10""", (days,))


def briefing_text() -> str:
    now = datetime.now()
    s = db.stats()
    parts = [f"☀️ صباح الخير — {now:%Y-%m-%d (%A)}", prayer.prayer_line()]
    parts.append(f"📊 مفتوح: {s['open']} | مهام: {s['tasks']} | متأخر: {s['overdue']}"
                 f" | ورشة: {s['ws_open_jobs']} شغلانة")
    today = db.q("""SELECT * FROM captures WHERE status='open' AND due_at::date = %s
                    ORDER BY due_at LIMIT 6""", (db.now_local_date(),))
    if today:
        parts.append(f"\n📅 مستحق النهاردة ({len(today)}):")
        parts += [_fmt(n) for n in today[:6]]
    late = db.overdue_captures()
    if late:
        parts.append(f"\n🔴 متأخر ({len(late)}):")
        parts += [_fmt(n) for n in late[:5]]
    radar = radar_projects()
    if radar:
        parts.append(f"\n🗂️ رادار المشاريع — واقفين:")
        for p in radar:
            days = (now - p["last_activity_at"].replace(tzinfo=None)).days
            parts.append(f"   ⚠️ «{p['name']}» — آخر حركة من {days} يوم")
    try:
        parts.append("\n" + retail.digest())
    except Exception as exc:
        parts.append(f"\n🏪 المحل: اللقطة غير متاحة ({type(exc).__name__})")
    reports = retail.latest_agent_reports(3)
    if reports:
        parts.append(f"\n🤝 آخر تقارير الفريق:")
        parts += [f"   • [{r['severity']}] {r['agent']}: {r['title'][:60]}" for r in reports]
    parts.append("\n💡 اقتراحي: ابدأ بأقدم متأخر، وبعتلي «تم <رقم>» أول ما تخلّص.")
    return "\n".join(parts)


def morning_briefing_if_due() -> bool:
    """نافذة الملخص الصباحي — مرة واحدة في اليوم مهما نطفت العقد."""
    hh, _mm = (config.MORNING_BRIEFING_AT or "08:00").split(":")[:2] + ["00"]
    try:
        hour = int(hh)
    except ValueError:
        hour = 8
    now = datetime.now()
    if not (hour <= now.hour < hour + 1):
        return False
    if not _claim_daily("morning"):
        return False
    enqueue(config.OWNER_TELEGRAM_ID, briefing_text(), "briefing",
            dedupe_key=f"brief-{now:%Y-%m-%d}")
    return True


def radar_scan_if_due() -> bool:
    """دورة ظهرية للرادار — تنبيه المشاريع الساكنة لو فاتها الملخص الصباحي."""
    now = datetime.now()
    if not (13 <= now.hour < 14):
        return False
    if not _claim_daily("radar"):
        return False
    radar = radar_projects()
    for p in radar:
        days = (now - p["last_activity_at"].replace(tzinfo=None)).days
        enqueue(config.OWNER_TELEGRAM_ID,
                f"⚠️ مشروع واقف: «{p['name']}» — آخر حركة من {days} يوم.\n"
                f"لو خلص، ابعت «مشروع {p['id']} تم» — لو لسه شغال ابعت تحديث.",
                "radar", dedupe_key=f"radar-{p['id']}-{now:%Y-%m-%d}")
    return True


# ------------------------------------------------------------------ بومودورو
def start_pomodoro(minutes: int = 25, label: str = "") -> Dict[str, Any]:
    minutes = max(5, min(120, int(minutes)))
    row = db.q("""INSERT INTO pomodoros(label, minutes, ends_at, node_id)
                  VALUES (%s,%s, now() + make_interval(mins => %s), %s)
                  RETURNING id, ends_at""",
               (label[:100] or "جلسة تركيز", minutes, minutes, config.NODE_ID), one=True)
    return row


def cancel_latest_pomodoro() -> bool:
    return db.x("""UPDATE pomodoros SET status='cancelled'
                   WHERE status='running' AND id = (SELECT id FROM pomodoros
                                                    WHERE status='running' ORDER BY id DESC LIMIT 1)""") > 0


def pomodoro_endings() -> int:
    rows = db.q("""SELECT * FROM pomodoros WHERE status='running' AND ends_at <= now()
                   ORDER BY id LIMIT 5""")
    for p in rows:
        enqueue(config.OWNER_TELEGRAM_ID,
                f"⏰ انتهى البومودورو «{p['label']}» ({p['minutes']} دقيقة).\n"
                f"🌿 خد بريك 5 دقايق — أو ابعت «بومودورو» لجلسة جديدة.",
                "pomodoro", dedupe_key=f"pomo-end-{p['id']}")
        db.x("UPDATE pomodoros SET status='done' WHERE id=%s", (p["id"],))
    return len(rows)


# ------------------------------------------------------------------ الدورة
def run_cycle(sender: Callable[[int, str], bool]) -> Dict[str, int]:
    """دورة كاملة يطلعها القائد — كل وظيفة معزولة الفشل."""
    out: Dict[str, int] = {}
    for name, fn in (("reminders", process_reminders),
                     ("briefing", morning_briefing_if_due),
                     ("radar", radar_scan_if_due),
                     ("pomodoro", pomodoro_endings)):
        try:
            out[name] = 1 if fn() else 0
        except Exception as exc:
            config.log(f"proactive: {name} فشل — {type(exc).__name__}: {exc}")
            out[name] = -1
    try:
        out["sent"] = flush(sender)
    except Exception as exc:
        config.log(f"proactive: flush فشل — {type(exc).__name__}: {exc}")
        out["sent"] = -1
    return out
