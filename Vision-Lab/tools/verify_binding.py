#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار قبول الربط (task-2) — يثبت بنيوياً ورقمياً أن:

  1. المصدر الرسمي الحي مُعتمد، وأي مسار SQLite قديم يُرفض صراحةً.
  2. إجمالي المديونيات من المصدر الحي = 1040.0 جنيه / 4 عملاء (التعريف الرسمي).
  3. النسخة القديمة (مساحة العمل) = 0.0 → إثبات «الصفر الكاذب» رقمياً.
  4. الوكيـل المُعاد ربطه يقرأ من المصدر الحي فعلاً (DB_PATH == الرسمي، بلا اتصال مباشر بـsqlite3).
  5. مطابقة الرقم مع الواجهة الحية (API 7777) — تُتخطى إن كانت الواجهة غير متاحة.

الاستخدام:  python tools\\verify_binding.py
الخروج: 0 = كل الفحوص PASS | 1 = يوجد فشل
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

VISION_LAB = Path(__file__).resolve().parent.parent
AGENT_ROOT = VISION_LAB.parent
if str(VISION_LAB) not in sys.path:
    sys.path.insert(0, str(VISION_LAB))
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from config import data_source as ds  # noqa: E402

PY = sys.executable
DEBT_TOOL = VISION_LAB / "tools" / "debt_total.py"
STALE_DB = r"G:\ai\Naggar Print POS Agent\pos_data.db"
BACKUP_DB = r"G:\ai\Naggar Print POS Agent\backup\pos_data_2026-10-10_1128.db"
API_URL = "http://127.0.0.1:7777/api/dashboard-summary"
EXPECTED = (4, 1040.0)

RESULTS = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"\n         {detail}" if detail else ""))


def skip(name: str, detail: str) -> None:
    RESULTS.append({"name": name, "ok": True, "skipped": True, "detail": detail})
    print(f"  [SKIP] {name}\n         {detail}")


def run_tool(args, env_extra=None):
    import os
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run([PY, str(DEBT_TOOL), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, timeout=120)
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def main() -> int:
    print("═" * 66)
    print("  اختبار قبول الربط — المصدر الرسمي الحي")
    print("═" * 66)

    # 1) تصنيف المصدر الرسمي
    info = ds.describe()
    check("1. المصدر الرسمي الحي مُعتمد (verdict=official)",
          info["verdict"] == "official",
          f"live_db={info['live_db']}")
    check("1b. المسار الرسمي هو قاعدة التطبيق الحي",
          Path(info["live_db"]).as_posix().lower() == Path(ds.DEFAULT_LIVE_DB).as_posix().lower(),
          f"{info['live_db']}")

    # 2) الرقم الحي بالتعريف الرسمي
    live = ds.debt_totals()
    check("2. الرقم الحي = 4 عملاء / 1040.0 جنيه (التعريف الرسمي balance > 0)",
          (live["debt_clients_count"], live["total_receivables"]) == EXPECTED,
          f"got=({live['debt_clients_count']}, {live['total_receivables']})  sql={live['sql'][:70]}...")

    # 3) رفض المسارات القديمة (استثناء صريح)
    for label, path in (("المساحة المتجمدة", STALE_DB), ("نسخة احتياطية", BACKUP_DB),
                        ("الساندبوكس", r"G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pos_data.db")):
        try:
            ds.open_readonly(path)
            check(f"3. رفض القراءة من {label}", False, f"لم يُرفض: {path}")
        except ds.LegacySourceRefused as exc:
            reason = exc.args[0].splitlines()[2].strip() if exc.args else ""
            check(f"3. رفض القراءة من {label}", True, f"{path}  |  {reason}")

    # 4) الصفر الكاذب: نفس التعريف على المصدر القديم
    conn = ds.forensic_open_readonly(STALE_DB)
    try:
        stale = tuple(conn.execute(ds.OFFICIAL_DEBT_SQL).fetchone())
        stale_orders = conn.execute("SELECT COUNT(*), MAX(id), MAX(date) FROM orders").fetchone()
    finally:
        conn.close()
    check("4. المصدر القديم = 0.0 (صفر كاذب) وسياقه أقدم",
          stale == (0, 0) and stale_orders[0] == 50 and stale_orders[1] == 323,
          f"stale_debt={stale} | orders={stale_orders[0]}, max_id={stale_orders[1]}, max_date={stale_orders[2]}")
    delta = live["total_receivables"] - float(stale[1])
    check("4b. الفرق الرقمي المثبت", abs(delta - 1040.0) < 0.005,
          f"الحي {live['total_receivables']} − القديم {stale[1]} = {delta} جنيه")

    # 5) الواجهة الحية (acceptance cross-check)
    try:
        with urllib.request.urlopen(API_URL, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        summary = payload.get("dashboard_summary") or {}
        api_pair = (summary.get("debt_clients_count"), summary.get("total_receivables"))
        check("5. مطابقة سكربتنا لواجهة التطبيق الحي (API 7777)",
              api_pair == (live["debt_clients_count"], live["total_receivables"]),
              f"api={api_pair}  tool=({live['debt_clients_count']}, {live['total_receivables']})")
    except Exception as exc:
        skip("5. مطابقة الواجهة الحية (API 7777)", f"الواجهة غير متاحة الآن: {type(exc).__name__} {exc}")

    # 6) التجاوز بمتغير بيئة لا يسمح بتمرير مسار قديم
    code, out, err = run_tool(["--json"], {"POS_LIVE_DB": STALE_DB})
    check("6. POS_LIVE_DB=<قديم> ⇒ رفض صريح وخروج 2",
          code == 2 and '"refused": true' in out and "pos_data.db" in (err + out),
          f"exit={code}  stderr_first={err.splitlines()[0] if err else ''}")

    # 7) التجاوز بمسار رسمي بديل يعمل
    code, out, err = run_tool(["--json"], {"POS_LIVE_DB": ds.DEFAULT_LIVE_DB})
    ok7 = code == 0 and '"total_receivables_egp": 1040.0' in out
    check("7. POS_LIVE_DB=<الرسمي> ⇒ نجاح 1040.0", ok7, f"exit={code}")

    # 8) الوكلاء مربوطون بالطبقة المركزية
    import importlib
    agents = ["crm", "cfo", "marketing", "data_healer", "manufacturing_agent"]
    official_norm = ds._norm(ds.official_path())
    for mod in agents:
        try:
            m = importlib.import_module(f"orchestrator.agents.{mod}")
        except Exception as exc:
            check(f"8. ربط الوكيل {mod} بالطبقة المركزية", False, f"فشل الاستيراد: {type(exc).__name__}: {exc}")
            continue
        bound = ds._norm(getattr(m, "DB_PATH", "")) == official_norm
        src = Path(m.__file__).read_text(encoding="utf-8")
        no_direct = "sqlite3.connect(" not in src
        legacy_ref = 'ROOT / "pos_data.db"' not in src
        check(f"8. ربط الوكيل {mod} بالطبقة المركزية",
              bound and no_direct and legacy_ref,
              f"DB_PATH={getattr(m, 'DB_PATH', None)} | اتصال مباشر بـsqlite3={not no_direct} | "
              f"مسار قديم في الكود={not legacy_ref}")

    # 9) اختبار وظيفي: وكيل يقرأ أرقاماً حية فعلاً
    try:
        cfo = importlib.import_module("orchestrator.agents.cfo").CfoAgent()
        reply = str(cfo.handle("ديون").get("reply", ""))
        check("9. وكيل (فارس/CFO) يقرأ رقماً حياً بلا سقوط", bool(reply.strip()),
              reply.splitlines()[0][:90] if reply else "(رد فارغ)")
    except Exception as exc:
        check("9. وكيل (فارس/CFO) يقرأ رقماً حياً بلا سقوط", False, f"{type(exc).__name__}: {exc}")

    # 10) الاكتشاف الآلي للوكلاء (AgentRegistry) — التأكد أن الوكلاء لم «يختفوا» بسبب الربط
    try:
        from orchestrator.base import AgentRegistry
        reg = AgentRegistry()
        present = {a.agent_id for a in reg.all()}
        need = {"crm", "cfo", "marketing", "data_healer", "manufacturing"}
        routed = reg.route("ديون ومستحقات")
        check("10. الاكتشاف الآلي (AgentRegistry) يرى الوكلاء الخمسة ويعمل التوجيه",
              need.issubset(present) and routed is not None,
              f"registered={sorted(present)} | route('ديون ومستحقات')={getattr(routed, 'agent_id', None)}")
    except Exception as exc:
        check("10. الاكتشاف الآلي (AgentRegistry) يرى الوكلاء الخمسة ويعمل التوجيه", False,
              f"{type(exc).__name__}: {exc}")

    failed = [r for r in RESULTS if not r["ok"]]
    print("─" * 66)
    print(f"  النتيجة: {len(RESULTS) - len(failed)}/{len(RESULTS)} فحص ناجح "
          f"({sum(1 for r in RESULTS if r.get('skipped'))} متخطى)")
    print("═" * 66)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())