# -*- coding: utf-8 -*-
"""منظم الحياة اليومية — شخصية النوت بوك الاستباقية.

يركّز على:
- تجهيز جدول اليوم (مهام المحل + شخصية + مواقيت الصلاة)
- ترحيل المهام غير العاجلة يوم بيوم
- اقتراح خطوات تنفيذ "أفكار البرامج"
- مراجعة المساء وإنجاز اليوم
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

try:
    from . import brain, prayer, store
except ImportError:
    import brain
    import prayer
    import store

# -------------------------------------------------- النوم والراحة
SLEEP_TIME = "23:00"   # وقت النوم المعتاد (قابل للتعديل عبر .env)
SLEEP_WARN_AFTER = "22:30"


def _parse_time_str(ts: str) -> datetime:
    """تحويل نص وقت (HH:MM) إلى datetime اليوم أو بكرة."""
    parts = ts.split(":")
    h, m = int(parts[0]), int(parts[1])
    now = datetime.now()
    dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if dt < now:
        dt += timedelta(days=1)
    return dt


def is_late_night(dt: Optional[datetime] = None) -> bool:
    now = dt or datetime.now()
    warn = _parse_time_str(SLEEP_WARN_AFTER)
    return now >= warn


def bedtime_text(dt: Optional[datetime] = None) -> str:
    """رسالة تذكير بموعد النوم + مراجعة سريعة."""
    now = dt or datetime.now()
    open_notes = store.list_notes(status="open")
    urgent = [n for n in open_notes if n.get("priority") in ("urgent", "high")]
    done_today = _done_today_count()

    lines = [
        "🌙 وقت النوم يا محمود! 😊",
        f"   ✅ اتنهت النهاردة: {done_today} مهمة",
    ]
    if urgent:
        lines.append(f"   🔴 مهام عاجلة متفضّلة ({len(urgent)}):")
        for n in urgent[:3]:
            lines.append(f"      • #{n['id']} {n.get('title','')[:40]}")
    if len(open_notes) > len(urgent):
        rolled = roll_non_urgent_to_tomorrow()
        lines.append(f"   📋 المهام العادية ({len(open_notes) - len(urgent)}): "
                      f"اتحزّت لي بكرة ({rolled} مهمة)")
    lines.append(f"   ⏰ وقت النوم المعتاد: {SLEEP_TIME}")
    lines.append("   تصبح على خير! 🌙")
    return "\n".join(lines)


def sleep_reminder_pending(state: Dict[str, Any]) -> bool:
    """هل أرسلنا تنبيه النوم اليوم؟"""
    today = datetime.now().strftime("%Y-%m-%d")
    return state.get("sleep_alert_date") == today


def mark_sleep_alert_sent(state: Dict[str, Any]) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    state["sleep_alert_date"] = today


# -------------------------------------------------- الترحيل
def roll_non_urgent_to_tomorrow() -> int:
    """نقل المهام غير العاجلة مفتوحة اللي ميعادها اليوم أو قبله → بكرة.

    يرجع عدد المهام المتحزّرة.
    """
    conn = store.connect()
    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """SELECT id, due_at, title FROM notes
               WHERE status='open'
                 AND priority NOT IN ('urgent','high')
                 AND (due_at IS NULL
                      OR due_at < ?)
               ORDER BY due_at ASC""",
            (now.isoformat(sep=" "),),
        ).fetchall()

        count = 0
        stamp = store.now_iso()
        for row in rows:
            old_due = row["due_at"]
            # Keep time if due today, just shift date
            if old_due:
                try:
                    old_dt = datetime.strptime(old_due, "%Y-%m-%d %H:%M")
                    new_due = old_dt.replace(
                        year=tomorrow[:4], month=tomorrow[5:7], day=tomorrow[8:10]
                    )
                    new_due_str = new_due.strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    new_due_str = f"{tomorrow} 09:00"
            else:
                new_due_str = f"{tomorrow} 09:00"

            conn.execute(
                "UPDATE notes SET due_at=?, remind_at=?, updated_at=? WHERE id=?",
                (new_due_str, new_due_str, stamp, row["id"]),
            )
            store.log_event(row["id"], "auto_roll", f"from {old_due} to {new_due_str}", conn=conn)
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


# -------------------------------------------------- خطة اليوم
def build_daily_plan() -> str:
    """يبني ملخص يومي شامل: الصلاة + المهام + التصنيفات."""
    now = datetime.now()
    times = prayer.get_prayer_times(now)
    stats = store.stats()

    open_notes = store.list_notes(status="open")

    # تجهيز تصنيفات المحل (ليزر، طباعة، خامات، عملاء) vs شخصي
    SHOP_CATS = {"ليزر", "طباعة", "خامات", "عملاء", "مشتريات", "صيانة", "شغل"}
    shop = []
    personal = []
    for n in open_notes:
        cat = n.get("category", "")
        if cat in SHOP_CATS:
            shop.append(n)
        else:
            personal.append(n)

    def _sort_key(n):
        """ترتيب: عاجل > مهم > عادي > منخفض، ثم بالميعاد."""
        p = {"urgent": 0, "high": 1, "normal": 2, "low": 3}.get(n.get("priority", "normal"), 4)
        due = n.get("due_at") or "9999"
        return (p, due)

    shop.sort(key=_sort_key)
    personal.sort(key=_sort_key)

    # الصلاة القادمة
    next_p, next_t, next_min = prayer.next_prayer(now)
    prayer_lines = [
        "🕋 مواقيت الصلاة (الخارجة):",
        f"   الفجر   {times.get('الفجر','--:--')}"
        f"   |   الظهر   {times.get('الظهر','--:--')}"
        f"   |   العصر   {times.get('العصر','--:--')}",
        f"   المغرب  {times.get('المغرب','--:--')}"
        f"   |   العشاء  {times.get('العشاء','--:--')}",
        f"   ⏰ الصلاة القادمة: {next_p} بعد {next_min} دقيقة",
    ]

    lines = [
        f"☀️ جدول النهاردة — {now.strftime('%Y-%m-%d')}",
        "",
    ] + prayer_lines + [
        "",
        f"📊 إجمالي مفتوح: {stats['open']} | مهام: {stats['tasks']} | أفكار: {stats['ideas']} | متأخر: {stats['overdue']}",
        "",
    ]

    if shop:
        lines.append(f"📌 مهام المحل ({len(shop)}):")
        for n in shop[:8]:
            due_str = f" ← {n['due_at'][-5:]}" if n.get("due_at") else ""
            prio_icon = {"urgent": "🔴", "high": "🟠", "normal": "🟢", "low": "⚪"}.get(n.get("priority", "normal"), "⚪")
            lines.append(f"   {prio_icon} #{n['id']} {n.get('title','')[:35]}{due_str}")
        if len(shop) > 8:
            lines.append(f"   ... و{len(shop)-8} مهام أخرى")

    if personal:
        lines.append(f"🏠 مهام شخصية ({len(personal)}):")
        for n in personal[:5]:
            due_str = f" ← {n['due_at'][-5:]}" if n.get("due_at") else ""
            lines.append(f"   🟢 #{n['id']} {n.get('title','')[:35]}{due_str}")

    if not shop and not personal:
        lines.append("   ✅ مفيش مهام معلّقة — وقت مرتاح! 😊")

    overdue = store.overdue()
    if overdue:
        lines.append("")
        lines.append(f"🔴 متأخر ({len(overdue)}):")
        for n in overdue[:5]:
            lines.append(f"   • #{n['id']} {n.get('title','')[:35]} (من {n['due_at']})")

    # اقتراح برنامج فكرة
    ideas = store.list_notes(status="open", kind="program_idea")
    if ideas:
        lines.append("")
        lines.append("💡 أفكار برامج تحتاج متابعة:")
        for n in ideas[:2]:
            steps = brain.propose_program_steps(n)
            lines.append(f"   🚀 #{n['id']} {n.get('title','')[:30]}")
            for s in steps[:3]:
                lines.append(f"      {s}")

    return "\n".join(lines)


# -------------------------------------------------- اقتراح خطوات فكرة برنامج
def propose_program_steps(note: Dict[str, Any]) -> List[str]:
    """اقتراح خطوات عملية لتنفيذ فكرة برنامج مسجّلة."""
    title = note.get("title", note.get("body", ""))[:60]
    kind = note.get("kind", "")
    if kind != "program_idea":
        return [
            "📌 هذه الملاحظة ليست فكرة برنامج — لا توجد خطوات مقترحة.",
        ]

    steps = [
        "📋 حدد المشكلة: ما الذي سيحلّه هذا البرنامج؟",
        "👥 حدد المستخدم المستهدف: من سيستخدمه؟",
        "🎯 حدد 3 مزايا أساسية (MVP):",
        "   1. المزية الأولى",
        "   2. المزية الثانية",
        "   3. المزية الثالثة",
        "🛠️ اختر التقنيات: لغة + إطار عمل + قاعدة بيانات",
        "📝 صمّم قاعدة البيانات / هيكل البيانات",
        "💻 ابنِ نسخة تجريبية (MVP) — لا تتقنّن أكثر من اللازم",
        "🧪 اختبر مع مستخدم حقيقي",
        "🚀 انشر واطلب آراء المستخدمين",
        "📢 سوّق وأضف المزايا تدريجياً",
    ]
    return steps


# -------------------------------------------------- مساءً مراجعة
def evening_review_text() -> str:
    """نص مراجعة المساء: ماذا أنجزناه اليوم + ما لم ينجز."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    conn = store.connect()
    try:
        done_today = conn.execute(
            "SELECT COUNT(*) FROM notes WHERE status='done' AND date(done_at)=?",
            (today,),
        ).fetchone()[0] or 0

        open_notes = store.list_notes(status="open")
        urgent = [n for n in open_notes if n.get("priority") == "urgent"]
        high = [n for n in open_notes if n.get("priority") == "high"]
        normal = [n for n in open_notes if n.get("priority") == "normal"]

        lines = [
            f"🌙 مراجعة مساء — {now.strftime('%Y-%m-%d %H:%M')}",
            f"   ✅ اتنهت النهاردة: {done_today} مهمة",
            f"   📋 متبقي: {len(open_notes)} مهمة",
        ]
        if urgent:
            lines.append(f"   🔴 عاجلة: {len(urgent)}")
        if high:
            lines.append(f"   🟠 مهمة: {len(high)}")

        if urgent or high:
            lines.append("")
            lines.append("   ⚡ أنجز الأول:")
            for n in (urgent + high)[:5]:
                lines.append(f"      #{n['id']} {n.get('title','')[:40]}")

        # هل حان وقت النوم؟
        if is_late_night(now):
            lines.append("")
            lines.append(bedtime_text(now))
        else:
            remaining_min = int((_parse_time_str(SLEEP_TIME) - now).total_seconds() / 60)
            if remaining_min > 0:
                lines.append(f"   ⏰ متبقي {remaining_min} دقيقة على وقت النوم")

        return "\n".join(lines)
    finally:
        conn.close()


def _done_today_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = store.connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM notes WHERE status='done' AND date(done_at)=?",
            (today,),
        ).fetchone()[0] or 0
    finally:
        conn.close()
