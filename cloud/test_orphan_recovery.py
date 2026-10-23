#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار حي شامل لآلية تحرير المهام العالقة (Orphaned Task Recovery).

أربعة سيناريوهات، كلها على السحابة الحقيقية:
  A. زومبي عمره 20 دقيقة  → يجب أن يُحرَّر (release_count +1، status=pending، الحجز ممسوح)
  B. مهمة جارية عمرها دقيقتان → يجب ألا تُلمس (العامل شغّال عليها فعلاً)
  C. مهمة سبق تحريرها 5 مرات (حد أقصى) → يجب أن تُؤرشف «مسمومة» لا أن تدور للأبد
  D. الإرجاء القديم (deferred_until في الماضي) لا يخفي المهمة المحرَّرة

الاستخدام:  python cloud/test_orphan_recovery.py all
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud"))

from schema_migrator import _connect_cloud  # noqa: E402

BASE = "http://127.0.0.1:3000"
TAG = "ORPHANTEST"
MAX_RELEASES = 5


def _token() -> str:
    for line in (ROOT / "tsmym-wajht-marwa-core" / ".env.local").read_text(encoding="utf-8").splitlines():
        if line.startswith("AGENT_TASK_WORKER_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("FAIL: AGENT_TASK_WORKER_TOKEN مش موجود في .env.local")


def release_only() -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/tasks/supervisor",
        data=json.dumps({"release_only": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def worker_beat() -> dict:
    req = urllib.request.Request(
        f"{BASE}/api/tasks/worker",
        data=b"{}",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_token()}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 202/502 حالة متوقعة
        return json.loads(exc.read().decode("utf-8"))


def seed(cur, label: str, *, minutes_ago: int, releases: int = 0, claimed_by: str | None = "worker",
         deferred_past: bool = False) -> str:
    ts = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    cur.execute(
        """
        insert into public.agent_tasks
          (agent_id, title, description, status, priority, source, created_by,
           schedule_type, last_run_at, claimed_by, claimed_at, release_count,
           deferred_until, created_at, updated_at)
        values ('koko', %s, %s, 'in_progress', 'normal', 'ui', 'mahmoud',
                'none', %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (f"{TAG} {label}",
         "مهمة اختبار تحرير تلقائي — ممنوع تبقى عالقة.",
         ts, claimed_by, ts, releases,
         ts if deferred_past else None, ts, ts),
    )
    return str(cur.fetchone()[0])


def state(cur, task_id: str) -> dict:
    cur.execute(
        """select status, claimed_by, release_count, archived_at, coalesce(result_note,'')
           from public.agent_tasks where id = %s""",
        (task_id,),
    )
    row = cur.fetchone()
    return {"status": row[0], "claimed_by": row[1], "releases": row[2],
            "archived": row[3] is not None, "note": row[4]}


def main() -> int:
    conn, route = _connect_cloud()
    cur = conn.cursor()
    print(f"CLOUD: {route}")

    zombie = seed(cur, "زومبي 20 دقيقة", minutes_ago=20)
    fresh = seed(cur, "جارية دقيقتين", minutes_ago=2)
    poisoned = seed(cur, "تحرير متكرر مسموم", minutes_ago=30, releases=MAX_RELEASES)
    deferred = seed(cur, "بإرجاء قديم", minutes_ago=25, deferred_past=True)
    conn.commit()
    print(f"SEEDED   zombie={zombie[:8]} fresh={fresh[:8]} poisoned={poisoned[:8]} deferred={deferred[:8]}")

    report = release_only()
    print(f"RELEASE  scanned={report.get('scanned')} released={report.get('released_count')} poisoned={report.get('poisoned_count')}")

    z, f, p, d = (state(cur, x) for x in (zombie, fresh, poisoned, deferred))
    conn.commit()

    checks = [
        ("A: زومبي 20د اتحرر", z["status"] == "pending" and z["claimed_by"] is None and z["releases"] == 1, z),
        ("B: الجارية دقيقتين ما اتلمست", f["status"] == "in_progress" and f["releases"] == 0, f),
        ("C: المسمومة اتأرشفت", p["archived"] and p["status"] == "rejected", p),
        ("D: الإرجاء القديم ما خبّاش المهمة", d["status"] == "pending" and d["releases"] == 1, d),
    ]
    ok = True
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  →  {detail['status']} releases={detail['releases']} archived={detail['archived']}")
        if not passed:
            ok = False
            print(f"      note: {detail['note'][:160]}")

    # الأهم: النبضة التالية تلتقط المحرَّرة فعلاً من طابور الإسناد السريع
    beat = worker_beat()
    print(f"WORKER   claimed={beat.get('claimed')} orphans={beat.get('orphans')}")
    reclaimed = beat.get("claimed") in {zombie, poisoned, deferred}
    print(f"{'PASS' if reclaimed else 'INFO'}  E: العامل التقط مهمة محرَّرة في نفس النبضة (claimed={beat.get('claimed') and str(beat['claimed'])[:8]})")

    # تنظيف: أرشفة مهام الاختبار (لا حذف — قاعدة سجل التدقيق)
    cur.execute(
        "update public.agent_tasks set archived_at = now(), status = 'rejected' where title like %s",
        (f"{TAG}%",),
    )
    conn.commit()
    print(f"CLEANUP  أُرشفت {cur.rowcount} مهمة اختبار (بلا حذف)")
    conn.close()
    print("RESULT", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
