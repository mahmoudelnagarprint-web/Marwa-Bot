# -*- coding: utf-8 -*-
# إدراج مهمة دورية لفيجن (vision) في Supabase agent_tasks — بالطريقة الرسمية للمشروع
import os, sys, json

ROOT = r"G:\ai\Naggar Print POS Agent"
ENVLOCAL = os.path.join(ROOT, "tsmym-wajht-marwa-core", ".env.local")

def load_env():
    env = {}
    with open(ENVLOCAL, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env()
url = env.get("NEXT_PUBLIC_SUPABASE_URL", "")
anon = env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
if not url or not anon:
    print("ERROR missing supabase env")
    sys.exit(1)

# استخدم REST anon (insert فقط) — نفس ما تستخدمه الواجهة suppress
import urllib.request

payload = {
    "agent_id": "vision",
    "title": "تحديث اللوحة بمهمة صاصا الدورية (كل 48 ساعة) ومواعيدها",
    "description": "أضف مهمة الصيانة الدورية الخاصة بمصطفى (صاصا) إلى لوحة مهام الواجهة في غرفة صاصا بمواعيدها: الدورة #1 اكتملت 2026-10-25 01:40، الدورة #2 2026-10-27 01:40، الدورة #3 2026-10-29 01:40. أبرز حالة كل دورة (معلقة/جارية/منجزة) واقرأ من SASA_WORKSHOP_STATE.md قسم 8 لتكون الواجهة متزامنة.",
    "status": "pending",
    "priority": "normal",
    "source": "ui",
    "created_by": "mahmoud",
    "schedule_type": "daily",
    "scheduled_time": "01:40",
    "schedule_timezone": "Africa/Cairo",
}

req = urllib.request.Request(
    url.rstrip("/") + "/rest/v1/agent_tasks",
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "apikey": anon,
        "Authorization": "Bearer " + anon,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    },
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8")
        print("HTTP", r.status)
        row = json.loads(body)
        print("INSERTED id:", row[0]["id"] if isinstance(row, list) and row else "?")
        print("agent_id:", row[0].get("agent_id") if isinstance(row, list) and row else "?")
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode("utf-8")[:500])
except Exception as e:
    print("ERROR", repr(e))
