# -*- coding: utf-8 -*-
"""الإعدادات الموحدة — تقرأ .env الجذر (G:\\Marwa-Bot\\.env) أولًا
(نفس عرف v1: التوكنات والأسرار في الجذر فقط) ثم تسمح بتجاوز محلي
بملف .env داخل المشروع (مستبعد من Git).

الأمان: لا تُطبع أي قيمة سرية من هذه الوحدة أبدًا.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MARWA_ROOT = PROJECT_ROOT.parents[2]          # G:\Marwa-Bot
ROOT_ENV = MARWA_ROOT / ".env"
LOCAL_ENV = PROJECT_ROOT / ".env"             # تجاوز اختياري

DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "notebook_v2.log"


def _parse_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


_ENV: Dict[str, str] = {}
_ENV.update(_parse_env(ROOT_ENV))
_ENV.update(_parse_env(LOCAL_ENV))            # المحلي يتغلب


def get(key: str, default: str = "") -> str:
    """قيمة من .env ثم من متغيرات البيئة ثم الافتراضي."""
    return _ENV.get(key) or os.environ.get(key, "") or default


def get_int(key: str, default: int) -> int:
    try:
        return int(get(key) or default)
    except ValueError:
        return default


# ------------------------------------------------------------------ الهوية
NODE_ID = get("NODE_ID") or "LAPTOP"
NODE_ROLE = get("NODE_ROLE") or ("workshop_desktop" if NODE_ID == "WORKSHOP" else "surface_laptop")
DEVICE_NAME = {"surface_laptop": "Surface Pro 4", "workshop_desktop": "Workshop Desktop"}.get(NODE_ROLE, NODE_ID)

# ------------------------------------------------------------------ القاعدة
def _db_dsn() -> str:
    for key in ("NB2_DB_URL", "POOLER_URL", "DIRECT_URL", "DATABASE_URL"):
        val = get(key)
        if val:
            return val
    return ""


DB_DSN = _db_dsn()
DB_DSN_HOST = (re.search(r"@([^:/]+)", DB_DSN).group(1) if DB_DSN and "@" in DB_DSN else "غير مضبوط")

# ------------------------------------------------------------------ تليجرام
TELEGRAM_AFKARY_TOKEN = get("TELEGRAM_AFKARY_TOKEN")
TELEGRAM_AFKARY_USERNAME = get("TELEGRAM_AFKARY_USERNAME", "@Afkary22Bot")
OWNER_TELEGRAM_ID = int(get("OWNER_TELEGRAM_ID") or 0)      # 0 = البوت يرفض الجميع (fail-closed)
ALLOWED_CHAT_IDS = {int(x) for x in re.split(r"[,\s]+", get("ALLOWED_CHAT_IDS")) if re.fullmatch(r"-?\d+", x)}

# ------------------------------------------------------------------ أسرار
AI_VAULT_MASTER_KEY = get("AI_VAULT_MASTER_KEY")
NB2_INGEST_TOKEN = get("NB2_INGEST_TOKEN")

# ------------------------------------------------------------------ Retail
POS_DB_PATH = get("NB2_POS_DB_PATH")

# ------------------------------------------------------------------ سلوك
MORNING_BRIEFING_AT = get("NB2_MORNING_BRIEFING_AT", "08:00")
RADAR_STAGNANT_DAYS = get_int("NB2_RADAR_STAGNANT_DAYS", 7)

# ------------------------------------------------------------------ مناداة الفريق
SQUAD_ROLLCALL_AT = get("NB2_SQUAD_ROLLCALL_AT", "09:00")          # ساعة مناداة الوكلاء
SQUAD_ROLLCALL_ENABLED = (get("NB2_SQUAD_ROLLCALL", "1").strip().lower()
                          not in ("0", "false", "no", "off"))
WEB_PORT = get_int("NB2_PORT", 8110)
LEASE_TTL_SECONDS = 45
HEARTBEAT_SECONDS = 15
ALIVE_AFTER_SECONDS = 90

# ------------------------------------------------------------- الكاش (الأداء)
# CACHE_TTL_SECONDS: عمر كاش اللوحة. DASHBOARD_TTL_SECONDS اسم مقروء لنفس الرقم
#   (العقد بينص على dashboard(ttl=45)).
# CACHE_ENABLED=0 أو NB2_CACHE=0: تعطيل كامل — عشان نقدر نقيس الأداء
#   **بارد** بلا كاش ولا نقع في «نجاح كذاب» من الكاش.
CACHE_TTL_SECONDS = get_int("NB2_CACHE_TTL", 45)
CACHE_ENABLED = (get("NB2_CACHE", "1").strip().lower() not in ("0", "false", "no", "off"))
DASHBOARD_TTL_SECONDS = CACHE_TTL_SECONDS
RECONNECT_RETRIES = get_int("NB2_DB_RETRIES", 1)


def log(message: str) -> None:
    """تسجيل موحد: كونسول UTF-8 + ملف logs/notebook_v2.log — بنفس عرف v1."""
    from datetime import datetime
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{NODE_ID}] {message}"
    try:
        import sys
        print(line, flush=True)
    except Exception:
        pass
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def missing() -> list:
    """قائمة الإعدادات الحرجة الناقصة (لعرضها بصدق عند الإقلاع)."""
    miss = []
    if not DB_DSN:
        miss.append("NB2_DB_URL / POOLER_URL — قاعدة البيانات")
    if not TELEGRAM_AFKARY_TOKEN:
        miss.append("TELEGRAM_AFKARY_TOKEN — بوت أفكري")
    if not OWNER_TELEGRAM_ID:
        miss.append("OWNER_TELEGRAM_ID — صاحب البوت")
    if not AI_VAULT_MASTER_KEY:
        miss.append("AI_VAULT_MASTER_KEY — تشفير مفاتيح الـAI")
    return miss
