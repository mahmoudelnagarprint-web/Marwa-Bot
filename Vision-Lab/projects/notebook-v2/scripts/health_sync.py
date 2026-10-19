# -*- coding: utf-8 -*-
"""فحص الصحة والمزامنة يدويًا/مجدولًا — R4.

    python scripts\\health_sync.py --check            # تقرير صحي على الكونسول
    python scripts\\health_sync.py --check --notify   # + إرسال التقرير للمالك تليجرام
    python scripts\\health_sync.py --pull-retail      # سحب لقطة POS الآن (قراءة فقط)
    python scripts\\health_sync.py --once-cron        # دورة مهام واحدة (لطوارئ السجلات)
"""
from __future__ import annotations

import argparse
import importlib
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nb import config, db, ha, retail  # noqa: E402
import nb.bot as bot_mod                # noqa: E402


def out(*parts, **kw) -> None:
    """طباعة آمنة على أي كونسول — ويندوز الافتراضي (cp1252) مش بيفهم العربي.

    بدونه `--check` بيرمي `UnicodeEncodeError` وبيموت، يعني **أداة فحص
    الصحة نفسها مش موجودة عمليًا** عند المالك. لو الترميز الحالي فشل
    بنسقط لـ`backslashreplace` بدل ما نقع. طباعة بس — مفيش أي تحويل
    لمحتوى التقرير ولا لملف.
    """
    text = " ".join(str(p) for p in parts)
    stream = kw.get("file", sys.stdout)
    rest = {k: v for k, v in kw.items() if k != "file"}
    try:
        print(text, file=stream, **rest)
    except UnicodeEncodeError:
        enc = getattr(stream, "encoding", None) or "ascii"
        print(text.encode(enc, "backslashreplace").decode(enc, "replace"),
              file=stream, **rest)


def report() -> str:
    lines = [f"【فحص النوتبوك v2】{datetime.now():%Y-%m-%d %H:%M}"]
    try:
        st = ha.status()
        lines.append(f"• العقدة: {st['device_name']} ({st['node_id']}) — "
                     f"{'⚡ قائد' if st['i_am_leader'] else '🛡️ غطاء'} | القائد الحالي: "
                     f"{st.get('leader', {}).get('holder') or 'لا أحد'}")
        alive = [n["node_id"] for n in st.get("nodes", []) if n.get("alive")]
        lines.append(f"• عقد حية: {alive or 'لا شيء!'}")
    except Exception as exc:
        lines.append(f"• HA: خطأ {type(exc).__name__}: {exc}")
    try:
        s = db.stats()
        lines.append(f"• القاعدة: سليمة | مفتوح {s['open']} | ورشة {s['ws_open_jobs']} | برومبتات {s['vault_prompts']}")
    except Exception as exc:
        lines.append(f"• القاعدة: خطأ {type(exc).__name__}: {exc}")
    try:
        snap = retail.last_snapshot()
        if snap:
            age = (datetime.now().astimezone() - snap["captured_at"].astimezone()).total_seconds() / 60
            lines.append(f"• آخر لقطة محل: منذ {age:.0f} دقيقة (#{snap['id']})")
        else:
            lines.append("• آخر لقطة محل: لا يوجد")
    except Exception as exc:
        lines.append(f"• اللقطة: خطأ {type(exc).__name__}")
    try:
        from nb import providers
        drow, dmodel = providers.get_default()
        if drow:
            lines.append(f"• مزود الـAI: {drow['name']}:{dmodel}")
        else:
            lines.append("• مزود الـAI: لا يوجد")
    except Exception:
        pass
    try:
        me = bot_mod.TelegramClient(config.TELEGRAM_AFKARY_TOKEN).get_me()
        lines.append(f"• البوت: متصل (@{me})" if me else "• البوت: توكن غير صالح!")
    except Exception as exc:
        lines.append(f"• البوت: خطأ {type(exc).__name__}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="فحص صحة النوتبوك v2")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--notify", action="store_true")
    ap.add_argument("--pull-retail", action="store_true")
    ap.add_argument("--once-cron", action="store_true")
    args = ap.parse_args(argv)

    if args.pull_retail:
        try:
            snap = retail.pull_pos_snapshot()
            out(f"✔ لقطة #{snap['id']} — منتجات: {snap['products']} | أخطاء أقسام: {snap['errors']}")
            return 0
        except Exception as exc:
            out(f"✖ فشل السحب: {type(exc).__name__}: {exc}")
            return 2

    if args.once_cron:
        import threading
        from nb import proactive
        tg = bot_mod.TelegramClient(config.TELEGRAM_AFKARY_TOKEN)
        count = proactive.run_cycle(tg.send)
        out(f"✔ دورة واحدة: {count}")
        return 0

    if args.check:
        text = report()
        out(text)
        if args.notify and config.OWNER_TELEGRAM_ID:
            ok = bot_mod.TelegramClient(config.TELEGRAM_AFKARY_TOKEN).send(config.OWNER_TELEGRAM_ID, text)
            out(f"→ أُرسل للمالك: {ok}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
