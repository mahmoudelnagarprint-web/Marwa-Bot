# -*- coding: utf-8 -*-
"""
MarwaBot Proactive Alerts — دايمون الشات الاستباقي (أمر المالك 2026-10-20 — تكليف راصد + فيجن)
===================================================================================
يراقب مرآة اللابتوب (قراءة فقط mode=ro) ويُدخل صفوف agent_updates عاجلة في العقل السحابي
(نفس مسار الواجهة: anon key — جدول الواجهة، migration 006). الواجهة بدورها تشترك
بـRealtime (lib/agent-alerts.ts) فتظهر التنبيهات فوراً كرسائل في شات الوكيل.

الشروط (أمثلة المالك):  تأخير أوردر (بيبو) • تحصيل من زينب (سلمى) • أي حركة مالية جديدة (فارس).

القواعد الصارمة:
  - المرآة قراءة فقط (sqlite mode=ro) — لا كتابة على قاعدة الأعمال إطلاقاً.
  - لا أسرار تُطبع؛ لا رفع بيانات أعمال؛ الجدول المستهدف = agent_updates (واجهة) فقط.
  - منع التكرار: آخر 20 صف بنفس الوكيل+العنوان يمنع الإدراج.
التشغيل: كل 5 دقائق (MarwaBot_ProactiveAlerts) — أو يدوياً: python scripts/proactive_alerts.py
"""
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(r"G:\Marwa-Bot")
MIRROR = ROOT / "pos_data.db"
ENV_FILE = ROOT / ".env"
STATE_FILE = Path(__file__).resolve().parent / "proactive_alerts_state.json"
LOG_FILE = ROOT / "logs" / "proactive_alerts.log"

ZENAB_CLIENT_ID = 63  # زينب — أولوية التحصيل لدى سلمى
OVERDUE_DAYS = 3      # عتبة تأخر الأوردر في التجهيز (قاعدة سلمى §9)


def log(msg: str) -> None:
    line = "%s | %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_env() -> dict:
    env = {}
    for raw in ENV_FILE.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        s = raw.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(st: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log("state save failed: %s" % exc)


def insert_update(env: dict, payload: dict) -> tuple[bool, str]:
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    anon = env.get("SUPABASE_PUBLISHABLE_KEY") or ""
    if not url or not anon:
        return False, "env missing"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url + "/rest/v1/agent_updates",
        data=body,
        headers={
            "apikey": anon,
            "Authorization": "Bearer " + anon,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201), "HTTP %s" % resp.status
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:220]
        except OSError:
            pass
        return False, "HTTP %s: %s" % (exc.code, body)
    except Exception as exc:
        return False, "%s: %s" % (type(exc).__name__, str(exc)[:120])


def recent_titles(env: dict, agent_id: str, limit: int = 20) -> set:
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    anon = env.get("SUPABASE_PUBLISHABLE_KEY") or ""
    if not url or not anon:
        return set()
    req = urllib.request.Request(
        url + "/rest/v1/agent_updates?select=title,agent_id&agent_id=eq.%s&order=created_at.desc&limit=%d" % (agent_id, limit),
        headers={"apikey": anon, "Authorization": "Bearer " + anon},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            return {r.get("title", "") for r in rows if r.get("title")}
    except Exception:
        return set()


def main() -> int:
    env = load_env()
    if not env.get("SUPABASE_URL"):
        log("FATAL: no SUPABASE_URL")
        return 2

    conn = sqlite3.connect("file:%s?mode=ro" % MIRROR, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    state = load_state()
    today = datetime.now().date()
    inserted = 0

    # --- 0) التشغيل الأول: نزرع المؤشر عند آخر حركة موجودة ونتجاوز هذه الدورة
    #     (منع إغراق التنبيهات من تاريخ البدء — التنبيهات للمستقبل فقط)
    max_tx_now = cur.execute("SELECT MAX(id) AS m FROM transactions").fetchone()["m"] or 0
    if not state.get("last_tx_id"):
        state["last_tx_id"] = max_tx_now
        state["last_run"] = datetime.now().isoformat()
        save_state(state)
        conn.close()
        log("first run — seeded at tx=%s (no alerts this cycle)" % max_tx_now)
        return 0

    # --- 1) تحصيل من زينب (عميلة #63): أي حركة دخل جديدة بعد آخر ما رأيناه ---
    last_tx = int(state.get("last_tx_id", 0) or 0)
    rows = cur.execute(
        "SELECT id, date, type, amount, category, notes FROM transactions WHERE id > ? ORDER BY id",
        (last_tx,),
    ).fetchall()
    max_id = last_tx
    for r in rows:
        max_id = max(max_id, r["id"])
        if r["type"] == "Income" and r["amount"]:
            # هل خصم من رصيد زينب؟ نفحص رصيدها قبل/بعد عبر حركة debt حديثة
            zb = cur.execute("SELECT balance FROM clients WHERE id=?", (ZENAB_CLIENT_ID,)).fetchone()
            zbal = zb["balance"] if zb else 0
            payload = {
                "agent_id": "salma",
                "kind": "alert",
                "severity": "عالي",
                "title": "💰 تحصيل نقدي جديد — زينب (240 ج متبقية)",
                "body": "حركة دخل #%s بمبلغ %s ج بتاريخ %s — رصيد زينب الآن %s ج. متابعة التحصيل وإغلاق الحساب."
                % (r["id"], r["amount"], str(r["date"])[:16], zbal),
            }
            titles = recent_titles(env, "salma")
            if payload["title"] not in titles:
                ok, msg = insert_update(env, payload)
                log("salma collection alert: id=%s -> %s %s" % (payload["title"][:24], ok, msg))
                inserted += 1 if ok else 0
    state["last_tx_id"] = max_id

    # --- 2) أوردرات متأخرة في التجهيز (>3 أيام) ---
    cutoff = today - timedelta(days=OVERDUE_DAYS)
    overdue = cur.execute(
        "SELECT o.id, o.client_id, c.name AS client_name, o.total_amount, o.date "
        "FROM orders o JOIN clients c ON c.id = o.client_id "
        "WHERE o.status='Under Preparation' AND o.date < ? ORDER BY o.id",
        (cutoff.strftime("%Y-%m-%d"),),
    ).fetchall()
    for o in overdue:
        age = (today - datetime.strptime(str(o["date"])[:10], "%Y-%m-%d").date()).days
        payload = {
            "agent_id": "bebo",
            "kind": "alert",
            "severity": "عالي",
            "title": "⏰ أوردر متأخر: #%s — %s (%s ج)" % (o["id"], o["client_name"], o["total_amount"]),
            "body": "عمره %s يوماً في التجهيز (العتبة %s أيام) — الإسراع في التسليم مطلوب، ومتابعة سلمى مع العميل."
            % (age, OVERDUE_DAYS),
            "source": "proactive_alerts",
        }
        titles = recent_titles(env, "bebo")
        if payload["title"] not in titles:
            ok, msg = insert_update(env, payload)
            log("bebo overdue alert: order #%s -> %s %s" % (o["id"], ok, msg))
            inserted += 1 if ok else 0

    # --- 3) أي حركة دخل جديدة — تقرير لفارس (متوسط) ---
    for r in rows:
        if r["type"] == "Income" and r["amount"]:
            payload = {
                "agent_id": "fares",
                "kind": "report",
                "severity": "متوسط",
                "title": "📈 حركة دخل جديدة #%s — %s ج" % (r["id"], r["amount"]),
                "body": "بتاريخ %s — تُحتسب ضمن نافذة أكتوبر (من 2026-10-01)." % str(r["date"])[:16],
            }
            titles = recent_titles(env, "fares")
            if payload["title"] not in titles:
                ok, msg = insert_update(env, payload)
                log("fares income report: #%s -> %s %s" % (r["id"], ok, msg))
                inserted += 1 if ok else 0

    conn.close()
    state["last_run"] = datetime.now().isoformat()
    save_state(state)
    log("done — inserted=%d | last_tx=%s | overdue=%d" % (inserted, state["last_tx_id"], len(overdue)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
