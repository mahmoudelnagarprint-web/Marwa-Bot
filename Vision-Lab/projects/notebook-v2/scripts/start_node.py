# -*- coding: utf-8 -*-
"""نقطة تشغيل العقدة الكاملة — R4 (Dual-Node HA).

نفس الأمر على الجهازين (Workshop Desktop + Surface Pro 4):
    python scripts\\start_node.py            # ويب + HA + (بوت/مهام إن كنت القائد)
    python scripts\\start_node.py --headless # بدون واجهة ويب

Each node: نبضة كل 15 ثانية + محاولة أخذ/تجديد إيجار القيادة (TTL 45s بوقت
السيرفر). القائد الوحيد هو اللي يشغّل polling تليجرام + الدورة الاستباقية.
لو القائد وقع، العقدة الثانية تلتقط خلال ≤ 45 ثانية — البوت لا يفصل.
"""
from __future__ import annotations

import argparse
import importlib
import socket
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nb import config, db, ha  # noqa: E402
import nb.bot as bot_mod       # noqa: E402
import nb.web as web_mod       # noqa: E402

migrate_mod = importlib.import_module("db.migrate")


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.2)
        return s.connect_ex((host, port)) == 0


def ensure_schema() -> None:
    row = db.q("SELECT to_regclass('public.settings') AS t", one=True)
    if not row or row.get("t") is None:
        config.log("قاعدة البيانات فاضية — تشغيل migrate تلقائيًا (idempotent)...")
        migrate_mod.apply()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="نقطة تشغيل عقدة النوتبوك v2")
    ap.add_argument("--port", type=int, default=config.WEB_PORT)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--headless", action="store_true", help="بدون واجهة ويب")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    # ترميز UTF-8 للكونسول (نفس إصلاح v1 لعقدة الورشة)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    miss = config.missing()
    if miss:
        config.log("مفقود في .env الجذر: " + "; ".join(miss))
        print("❌ أكمل الإعدادات الناقصة أولًا ثم أعد التشغيل.")
        return 2

    if not args.headless and port_in_use(args.port):
        config.log(f"المنفذ {args.port} مشغول — نسخة v2 شغّالة على هذا الجهاز (single instance). خروج صادق.")
        return 0

    try:
        ensure_schema()
    except Exception as exc:
        config.log(f"فشل التحقق من القاعدة: {type(exc).__name__}: {exc}")
        return 2

    stop = threading.Event()
    run_state = {"bot": None}   # {"stopev": ..., "thread": ...}

    def reconcile(is_leader: bool) -> None:
        cur = run_state["bot"]
        running = bool(cur and cur["stopev"] and cur["thread"].is_alive())
        if is_leader and not running:
            stopev = threading.Event()
            th = threading.Thread(target=bot_mod.run,
                                  args=(config.TELEGRAM_AFKARY_TOKEN, stopev),
                                  daemon=True, name="afkary-bot")
            th.start()
            run_state["bot"] = {"stopev": stopev, "thread": th}
            config.log("⚡ حصلت على عقدة القيادة — تشغيل بوت @Afkary22Bot + المحرك الاستباقي")
        elif not is_leader and running:
            config.log("🛡️ فقدت القيادة — إيقاف البوت هنا (العقدة التانية تولت)")
            run_state["bot"]["stopev"].set()
            run_state["bot"] = None

    def ha_loop() -> None:
        while not stop.is_set():
            try:
                ha.heartbeat()
                is_leader = ha.try_acquire_lease()
                reconcile(is_leader)
            except Exception as exc:
                config.log(f"خطأ HA: {type(exc).__name__}: {exc}")
            stop.wait(config.HEARTBEAT_SECONDS)
        try:
            ha.release()
            config.log("تم تسليم القيادة عند الإيقاف المرتب")
        except Exception:
            pass

    if not args.headless:
        threading.Thread(target=web_mod.run,
                         args=(args.host, args.port, args.debug),
                         daemon=True, name="web").start()
        config.log(f"الواجهة: http://127.0.0.1:{args.port}")

    ha_thread = threading.Thread(target=ha_loop, daemon=True, name="ha")
    ha_thread.start()
    config.log(f"العقدة {config.NODE_ID} ({config.DEVICE_NAME}) بدأت — القلب النابض يعمل")
    config.log(f"· قاعدة البيانات: {config.DB_DSN_HOST}")

    print("\n💡 النوتبوك v2 شغّالة على هذه العقدة.")
    print(f"   الواجهة (الجهاز الثاني برضه): http://127.0.0.1:{args.port}")
    if config.TELEGRAM_AFKARY_TOKEN:
        print("   البوت: @Afkary22Bot — القائد فقط يسمعه.")
    print("   Ctrl+C للإيقاف المرتب (تسليم القيادة).")
    try:
        while True:
            stop.wait(5)
    except KeyboardInterrupt:
        print("\nإيقاف مرتب...")
        stop.set()
    return 0


if __name__ == "__main__":
    sys.exit(main())
