# -*- coding: utf-8 -*-
"""التوفر العالي للعقدتين — R4 (Dual-Node HA).

- كل عقدة تنبض في nodes كل 15 ثانية.
- عقدة القيادة (leader) = الوحيدة اللي تشغّل polling تليجرام + المهام المجدولة.
- الإيجار leader_lease TTL 45 ثانية **بوقت السيرفر** (يمنع انحراف ساعات
  الجهازين) — العقدة الثانية تلتقط خلال ≤ 45 ثانية من سقوط القائد.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from nb import config, db


def heartbeat() -> None:
    db.x("""INSERT INTO nodes(node_id, device_name, role, last_seen, started_at, meta)
            VALUES (%s, %s, %s, now(), now(), %s::jsonb)
            ON CONFLICT (node_id) DO UPDATE SET
                device_name = EXCLUDED.device_name,
                role        = EXCLUDED.role,
                last_seen   = now(),
                meta        = EXCLUDED.meta""",
         (config.NODE_ID, config.DEVICE_NAME, config.NODE_ROLE,
          __import__("psycopg2").extras.Json({"version": "2.0.0",
                                              "web_port": config.WEB_PORT})))


def try_acquire_lease() -> bool:
    """آخذ/جدّد إيجار القيادة ذريًا — يرجع هل أنا القائد الآن؟"""
    sql = """INSERT INTO leader_lease(id, holder, expires_at, acquired_at, updated_at)
             VALUES (1, %s, now() + make_interval(secs => %s), now(), now())
             ON CONFLICT (id) DO UPDATE SET
                 holder     = EXCLUDED.holder,
                 expires_at = EXCLUDED.expires_at,
                 acquired_at = CASE WHEN leader_lease.holder = EXCLUDED.holder
                                    THEN leader_lease.acquired_at ELSE now() END,
                 updated_at = now()
             WHERE leader_lease.expires_at < now() OR leader_lease.holder = EXCLUDED.holder
             RETURNING holder"""
    row = db.q(sql, (config.NODE_ID, config.LEASE_TTL_SECONDS), one=True)
    return bool(row and row["holder"] == config.NODE_ID)


def status() -> Dict[str, Any]:
    """حالة الـHA — و`i_am_leader` بتحسب انتهاء الإيجار **بوقت القاعدة**.

    العطل اللي اتصلّح هنا: الكود القديم كان بيفحص `lease.get("expires_at")`
    على إنه **قيمة موجودة** (`truthy`) من غير ما يقارنه بـ`now()`، ومعندوش
    شرط على `holder IS NULL`. النتيجة: إيجار قائد ميّت (أو مسلّم بـ`holder
    = NULL`) بيفضل `expires_at` بتاعه موجود → العقدة تعلن نفسها قائدة وهي
    مش كده = **split-brain في العرض**: `/health` و`/api/ha/status` وشارة
    الويب كلهم بيورّوا «أنا القائد» غلط، ومحدش يعرف إن مفيش قائد فعلًا.

    الحساب كله **في SQL بوقت السيرفر** (`expires_at > now()`) — مفيش أي
    مقارنة بوقت الجهاز، عشان فارق ساعات اللابتوب ما يقلبش النتيجة.
    """
    lease = db.q("""
        SELECT id, holder, expires_at, acquired_at, updated_at,
               (expires_at > now())              AS is_live,
               (holder IS NOT NULL)              AS has_holder,
               (holder IS NOT NULL AND expires_at > now()) AS is_valid,
               GREATEST(0, EXTRACT(EPOCH FROM (expires_at - now()))::int) AS secs_left
        FROM leader_lease WHERE id = 1""", one=True)
    nodes = db.q("""SELECT node_id, device_name, role, last_seen,
                           (last_seen > now() - make_interval(secs => %s)) AS alive
                    FROM nodes ORDER BY last_seen DESC""", (config.ALIVE_AFTER_SECONDS,))

    # القائد الفعلي = حامل الإيجار **وإيجاره لسه ساري**. غير كده مفيش قائد.
    lease_valid = bool(lease and lease.get("is_valid"))
    if not lease_valid and lease:
        # نبيّن السبب بوضوح بدل ما النسخة القديمة تقول «لسه موجود» وهي ميتة
        lease["expired"] = not lease.get("is_live")
        lease["released"] = not lease.get("has_holder")
    me_leader = bool(lease_valid and lease.get("holder") == config.NODE_ID)
    effective_leader = lease.get("holder") if lease_valid else None

    return {
        "node_id": config.NODE_ID,
        "device_name": config.DEVICE_NAME,
        "role": config.NODE_ROLE,
        "i_am_leader": me_leader,
        "leader": lease,
        "effective_leader": effective_leader,   # None = مفيش قائد ساري الآن
        "lease_valid": lease_valid,
        "nodes": nodes,
        "web_port": config.WEB_PORT,
    }


def release() -> None:
    """تسليم طوعي للإيجار (إيقاف مرتب) — العقدة الثانية تلتقط فورًا."""
    db.x("""UPDATE leader_lease
            SET holder = NULL, expires_at = now() - interval '1 second', updated_at = now()
            WHERE id = 1 AND holder = %s""", (config.NODE_ID,))


def set_bot_state(key: str, value: str, bot: str = "afkary") -> None:
    db.x("""INSERT INTO bot_state(bot, key, value, updated_at)
            VALUES (%s,%s,%s, now())
            ON CONFLICT (bot, key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
         (bot, key, str(value)))


def get_bot_state(key: str, default: str = "0", bot: str = "afkary") -> str:
    row = db.q("SELECT value FROM bot_state WHERE bot=%s AND key=%s", (bot, key), one=True)
    return row["value"] if row else default
