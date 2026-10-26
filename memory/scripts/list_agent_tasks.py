# -*- coding: utf-8 -*-
# قراءة مهام الأجنت المدرجة — للأدلة فقط (لا تعديل)
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
q = url.rstrip("/") + "/rest/v1/agent_tasks?select=id,agent_id,title,status,created_at&order=created_at.desc&limit=10"
req = urllib.request.Request(q, headers={"apikey": anon, "Authorization": "Bearer " + anon})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read().decode("utf-8"))
        for row in rows:
            print(f"- [{row.get('agent_id','?')}] {row.get('status','?')} :: {row.get('title','')[:80]}")
except Exception as e:
    print("ERROR", repr(e))
