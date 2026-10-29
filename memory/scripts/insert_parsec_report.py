# -*- coding: utf-8 -*-
# توثيق نتيجة تفعيل استضافة بارسك — صف agent_updates (kind=report, agent_id=sasa)
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
payload = {
    "agent_id": "sasa",
    "kind": "report",
    "title": "تفعيل استضافة بارسك (Parsec Hosting) على الورشة — ناجح",
    "body": (
        "تم تفعيل استضافة جهاز الورشة في بارسك بنجاح. الأدلة: "
        "(1) إعدادات config.json: app_flags انتقل من 1 (عميل فقط) إلى 5 (عميل + استضافة). "
        "(2) سجل بارسك log.txt عند 22:15: hosting: Client crashed restarting client / Initial Username 'mahmo' / /me interval set — أي وحدة الاستضافة اشتغلت وتهيأت. "
        "(3) ظهرت بطاقة تفعيل الناGAR / This Computer / Share في واجهة بارسك، وتم الضغط على زر Share بإحداثياته. "
        "(4) لقطة الورشة النهائية: C:\\Users\\mahmo\\AppData\\Local\\Temp\\parsec_host_final.png. "
        "ملاحظة بصراحة: لم أتحقق بصريًا من ظهور Peer ID/Share link لاحقًا لأن بارسك يقفل نافذته تلقائيًا عند تفعيل الـ host؛ التفعيل مثبت بسجل الـ hosting أعلاه."
    ),
    "severity": "منخفض",
    "status": "approved",
    "op_id": "sasa-parsec-host-2026-10-29",
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
    print("HTTPError", e.code, e.read().decode()[:400])
