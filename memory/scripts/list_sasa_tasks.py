# -*- coding: utf-8 -*-
import os, sys, json, urllib.request, urllib.parse

ROOT = r"G:\ai\Naggar Print POS Agent"
ENVLOCAL = os.path.join(ROOT, "tsmym-wajht-marwa-core", ".env.local")

def load_env():
    env = {}
    with open(ENVLOCAL, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

env = load_env()
url = env.get("NEXT_PUBLIC_SUPABASE_URL", "")
anon = env.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

# مهام صاصا غير المؤرشفة، الأحدث أولاً
q = url.rstrip("/") + "/rest/v1/agent_tasks?agent_id=eq.sasa&archived_at=is.null&order=created_at.desc&limit=15"
req = urllib.request.Request(q, headers={"apikey": anon, "Authorization": "Bearer " + anon})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        rows = json.loads(r.read().decode("utf-8"))
        print("عدد مهام صاصا الحالية:", len(rows))
        for row in rows:
            st = row.get("schedule_type") or "none"
            print(f"- [{row.get('status','?')}] ({st}) {row.get('title','')[:90]}")
except Exception as e:
    print("ERROR", repr(e))
