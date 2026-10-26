# -*- coding: utf-8 -*-
# إدراج مهمة فلاشة USB لصاصا في agent_tasks (عرضها على لوحة المهام)
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

payload = {
    "agent_id": "sasa",
    "title": "إصلاح فلاشة USB تظهر بلا وسائط (No Media)",
    "description": "المالك: لدي فلاشة موصلة بالجهاز وتظهر في (Disk Management) بحالة 'No Media' ولا تظهر لها أي مساحة تخزينية. المطلوب إصلاحها جذرياً: (1) شرح استخراج VID/PID عبر Device Manager أو ChipGenius، (2) البحث عن Mass Production Tools المناسبة لإعادة برمجة المتحكم في GitHub/قواعد بيانات الفلاشات، (3) خطوات أداة التفليش لإحياء الفلاشة، (4) أوامر CMD/Diskpart وتهيئة فرضية استباقية، وحلول غير تقليدية لإجبارها على العمل.",
    "status": "pending",
    "priority": "high",
    "source": "marwa",
    "created_by": "mahmoud",
}
req = urllib.request.Request(
    url.rstrip("/") + "/rest/v1/agent_tasks",
    data=json.dumps(payload).encode("utf-8"),
    headers={"apikey": anon, "Authorization": "Bearer " + anon, "Content-Type": "application/json", "Prefer": "return=representation"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        row = json.loads(r.read().decode("utf-8"))
        print("INSERTED", row[0]["id"] if isinstance(row, list) and row else "?")
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode()[:400])
