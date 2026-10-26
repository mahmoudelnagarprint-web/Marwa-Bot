# -*- coding: utf-8 -*-
# إدراج مهمة الصيانة الدورية لصاصا — وسم «كل 48 ساعة» (جدولة فعلية في agent_tasks)
import os, sys, json, urllib.request

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

# 1) تحقق: هل توجد مهمة صيانة موسومة بالفعل؟
q = url.rstrip("/") + "/rest/v1/agent_tasks?agent_id=eq.sasa&title=ilike.*كل 48 ساعة*&select=id,title,status,schedule_type&limit=5"
req = urllib.request.Request(q, headers={"apikey": anon, "Authorization": "Bearer " + anon})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        existing = json.loads(r.read().decode("utf-8"))
except Exception as e:
    existing = []
    print("فحص مسبق فشل:", repr(e))

if existing:
    print("الموجود فعلا:", json.dumps([{"id": x["id"], "title": x["title"], "status": x["status"], "st": x["schedule_type"]} for x in existing], ensure_ascii=False))
else:
    payload = {
        "agent_id": "sasa",
        "title": "[كل 48 ساعة] صيانة دورية شاملة للنظام",  # الوسم يفعّل جدولة كل 48 ساعة في الـ worker
        "description": "الصيانة الدورية لصاصا (مصطفى): إفراغ Temp، تنظيف ملفات الكاش، مراقبة مساحة C: وفحص العمليات العالقة، وإرسال التقرير للوحة. تنفذ كل 48 ساعة (الدورة الأولى اكتملت 2026-10-25 01:40، القادمة 2026-10-27 01:40).",
        "status": "pending",
        "priority": "normal",
        "source": "marwa",
        "created_by": "mahmoud",
        "schedule_type": "daily",          # قيد DB يسمح none/daily/weekly فقط
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
            row = json.loads(r.read().decode("utf-8"))
            print("INSERTED", row[0]["id"] if isinstance(row, list) and row else "?")
    except urllib.error.HTTPError as e:
        print("HTTPError", e.code, e.read().decode("utf-8")[:400])
