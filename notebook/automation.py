# -*- coding: utf-8 -*-
"""نوتبوك ذكية — سكريبت التشغيل التلقائي للمهام المجدولة.

الأنماط:
  --morning   : إرسال جدول الصباح الكامل (الصلاة + المهام) على تليجرام
  --evening   : إرسال مراجعة المساء + ترحيل المهام غير العاجلة
  --cycle     : فحص كل 30 دقيقة: إرسال التذكيرات المستحقة، تنبيهات الصلاة القادمة،
                واقتراحات تنظيم الوقت (موجز).
  --test      : إرسال رسالة اختبار بسيطة.

يستخدم نفس جسر الإرسال الخاص بالبوت (قراءة التوكن من .env الجذر) لتجنب التعارض.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# قراءة المتغيرات من جذر المشروع (حيث يوجد .env)
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_telegram():
    from telegram_bridge import Telegram  # إعادةימוש نفس الكلاس
    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("TELEGRAM_BOT_TOKEN غير موجود في .env")
        sys.exit(1)
    return Telegram(token)

def get_allowed_chat(tg) -> Optional[int]:
    env = load_env()
    allowed = set()
    for key in ("OWNER_TELEGRAM_ID", "ALLOWED_CHAT_IDS"):
        for part in env.get(key, "").replace(",", " ").split():
            if part.lstrip("-").isdigit():
                allowed.add(int(part))
    if not allowed:
        print("OWNER_TELEGRAM_ID / ALLOWED_CHAT_IDS غير موجودين في .env")
        return None
    return next(iter(allowed))

def send_morning():
    tg = get_telegram()
    chat_id = get_allowed_chat(tg)
    if chat_id is None:
        return
    try:
        # نرسل ملخص الصباح الشامل من brain
        from brain import morning_digest_text
        text = morning_digest_text()
    except Exception as e:
        text = f"❌ فشل توليد ملخص الصباح: {e}"
    ok = tg.send(chat_id, text)
    print(f"Morning sent: {ok}")

def send_evening():
    tg = get_telegram()
    chat_id = get_allowed_chat(tg)
    if chat_id is None:
        return
    try:
        from brain import evening_review_text
        text = evening_review_text()
    except Exception as e:
        text = f"❌ فشل توليد مراجعة المساء: {e}"
    ok = tg.send(chat_id, text)
    print(f"Evening sent: {ok}")

def send_cycle():
    tg = get_telegram()
    chat_id = get_allowed_chat(tg)
    if chat_id is None:
        return
    try:
        # استدعاء دوال التذكير من telegram_bridge مباشرة (ت reuse الحالة)
        from telegram_bridge import reminders_cycle, prayer_cycle, sleep_cycle, _load_state
        state = _load_state()
        sent = reminders_cycle(tg, {chat_id})  # allowed set فقط لدينا chat_id
        sent += prayer_cycle(tg, {chat_id}, state)
        sent += sleep_cycle(tg, {chat_id}, state)
        # لو لم يُرسل أي شيء، نرسل ملخصًا مختصرًا لتأكيد الدورة
        if sent == 0:
            now = datetime.now()
            next_p, pt, mins = None, None, None
            try:
                from prayer import next_prayer
                next_p, pt, mins = next_prayer()
            except Exception:
                pass
            txt = f"🔄 دورة فحص ({now:%H:%M})"
            if next_p:
                txt += f"\n⏰ الصلاة القادمة: {next_p} بعد {mins} دقيقة"
            # تعداد المستحق الآن والمتأخر
            try:
                from store import due_now, overdue
                due = due_now()
                late = overdue()
                txt += f"\n📌 مستحق الآن: {len(due)} | 🔴 متأخر: {len(late)}"
            except Exception:
                pass
            text = txt
        else:
            text = f"✅ دورة فحص أُرسلت ({sent} تذكير/تنبيه)"
        ok = tg.send(chat_id, text)
        print(f"Cycle sent: {ok} (sent {sent} notifications)")
    except Exception as e:
        print(f"Cycle error: {e}")

def send_test():
    tg = get_telegram()
    chat_id = get_allowed_chat(tg)
    if chat_id is None:
        return
    text = "✅ اختبار الاتصال من سكريبت الأتمتة — النوتبوك الذكية متصلة."
    ok = tg.send(chat_id, text)
    print(f"Test sent: {ok}")

def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="نوتبوك ذكية — أتمتة مجدولة")
    parser.add_argument("--morning", action="store_true", help="إرسال جدول الصباح")
    parser.add_argument("--evening", action="store_true", help="إرسال مراجعة المساء")
    parser.add_argument("--cycle", action="store_true", help="دورة فحص 30 دقيقة")
    parser.add_argument("--test", action="store_true", help="إرسال رسالة اختبار")
    args = parser.parse_args(argv)

    if args.test:
        send_test()
        return 0
    if args.morning:
        send_morning()
        return 0
    if args.evening:
        send_evening()
        return 0
    if args.cycle:
        send_cycle()
        return 0

    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())