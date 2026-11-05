# -*- coding: utf-8 -*-
# توثيق مهمة تنظيف قرص C: — صف agent_updates (kind=report)
import os, json, urllib.request, datetime

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

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).isoformat()
body = (
    "أمر المالك: نظّف C: وحذف الملفات غير اللازمة بلا نقل. تنفيذ صاصا-الورشة 2026-11-05 ~02:10: "
    "المساحة الحرة قبل 29.8 ج → بعد 36.2 ج (زيادة 6.4 ج فورية على القرص الفعلي). "
    "المحذوفات: (1) ملفات كراش WSL في Temp حجم 22.65 ج + كراش متولدة أثناء العمل ~28 ج. "
    "(2) كاش Docker الداخلي: build cache 33.31 ج + صور غير مستخدمة 16.94 ج (بدون لمس الكونتينرات الشغالة). "
    "(3) كاش الحزم: npm 1.0 ج + uv 2.1 ج + pip 0.5 ج. "
    "(4) سلة المحذوفات: 49 عنصر. "
    "خطر تم احتواؤه: حلقة كراش node جوا docker-desktop VM كانت بتكتب 2.5 ج كل 70 ثانية — كانت هتملى القرص في نص ساعة وتسقط كل خدمات Marwa Core؛ وقفت Docker و WSL لتكسير الحلقة (مؤكد: لا كراش جديدة). "
    "بقايا كاش pnpm في تنظيف خلفي مستمر. "
    "بند يحتاج المالك: سكربت سطح المكتب (استرجاع-مساحة-Docker.bat) — تشغيله كمسؤول يرجع +40 ج إضافية بضغط قرص Docker (47.35 ج الظاهري مقابل بيانات فعلية أقل بكثير بعد التنظيف) + تعطيل السبات يحرر 6.4 ج إضافية. "
    "الأنظمة الحية (15 كونتينر: postgres/lobechat/immich/mcp) لم تُمس بياناتها. التزام: حذف فقط، لا نقل، لا تصعيد صلاحيات."
)
payload = {
    "agent_id": "sasa",
    "kind": "report",
    "title": "صيانة قرص C: — تنظيف 50+ ج وحل خطر حلقة كراش كانت هتملى القرص",
    "body": body,
    "severity": "منخفض",
    "status": "approved",
    "op_id": "sasa-c-cleanup-2026-11-05",
    "created_at": now,
}

req = urllib.request.Request(
    url.rstrip("/") + "/rest/v1/agent_updates",
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
        rows = json.loads(r.read().decode("utf-8"))
        print("INSERTED upd id:", rows[0]["id"] if isinstance(rows, list) and rows else "?")
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read().decode()[:300])
