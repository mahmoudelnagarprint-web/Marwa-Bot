#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""router_daemon — محرك التوجيه ونظام أوامر السلاش (Workspace OS).
بأمر المالك 2026-10-20 — تكليف راصد 👁️ (المرحلة 3).

المبدأ (نفس منظومة fast_ops):
  * دالة parse(text) تعترض أي مدخل يبدأ بـ `/`:
      /task @fares مراجعة حساب زينب
      /task @sasa تشغيل الليزر عدد 2 [urgent]
      /summon @koko حملة عيد الأضحى
      /status @fares
    → يتجاوز الرد اللفظي ويُنفّذ فوراً.
  * /task: يكتب ملف مهمة markdown في workspaces/<agent>/inbox_tasks/
    (اسم الملف: op_id.slug.md) ثم يدفع صفّاً لجدول agent_tasks في Supabase
    عبر العميل الرسمي HermesSyncManager (مفاتيح من .env فقط — لا أسرار بالكود).
  * فشل السحابة لا يفقد شيئاً: الصف يُخزن في logs/router_outbox.jsonl.
  * لا حذف من السحابة إطلاقاً (نفس قاعدة W3).

الاستخدام:
  python workspaces/system_engine/router_daemon.py parse "/task @fares مراجعة حساب زينب"
  python workspaces/system_engine/router_daemon.py watch [--interval 2]
  python workspaces/system_engine/router_daemon.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent  # G:\ai\Naggar Print POS Agent
sys.path.insert(0, str(WORKSPACE / "cloud"))
sys.path.insert(0, str(WORKSPACE))

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

WORKSPACES = WORKSPACE / "workspaces"
OUTBOX = WORKSPACE / "logs" / "router_outbox.jsonl"
LOG = WORKSPACE / "logs" / "router_daemon.log"

# خريطة @alias psychological → مجلد العضو (الأسماء الحضرية للمكتب)
AGENTS = {
    "marwa": "marwa_maestro",
    "fares": "fares_cfo",
    "salma": "salma_crm",
    "bebo": "bebo_production",
    "sasa": "sasa_devices",
    "vision": "vision_coder",
    "koko": "koko_marketing",
    "hakim": "hakim_advisor",
    "afkar": "afkar_ideas",
}
COMMANDS = ("/task", "/summon", "/status")

SLASH_RE = re.compile(r"^\s*/(?P<cmd>\w+)\s+(?P<rest>.+)$", re.S)


def new_op_id() -> str:
    return f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}"


def log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {line}\n")


def outbox_append(table: str, row: dict, reason: str) -> None:
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    rec = {"queued_at": datetime.now(timezone.utc).isoformat(),
           "table": table, "row": row, "reason": reason}
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _quiet_flush() -> None:
    try:
        sys.path.insert(0, str(WORKSPACE / "tools"))
        from fast_ops import flush_outbox  # type: ignore
        flush_outbox()
    except Exception:
        pass


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"\s+", "_", text.strip())
    s = re.sub(r"[^\w\u0600-\u06FF\-]", "", s)
    return s[:max_len] or "task"


def parse(text: str) -> dict | None:
    """محلل السلاش: يعيد قراراً قابلاً للتنفيذ أو None للكلام اللفظي العادي."""
    if not text or not text.strip().startswith("/"):
        return None
    m = SLASH_RE.match(text.strip())
    if not m:
        return {"ok": False, "error": "أمر غير مكتمل — اكتب /task @agent التفاصيل",
                "cmd": text.strip()[:40], "executed": False}
    cmd = m.group("cmd").lower()
    rest = m.group("rest").strip()
    if cmd not in ("task", "summon", "status"):
        return {"ok": False, "error": f"أمر غير معروف /{cmd} — المتاح: {', '.join(COMMANDS)}",
                "cmd": f"/{cmd}", "executed": False}
    m2 = re.match(r"@(?P<alias>\w+)\s*(?P<body>[\s\S]*)", rest)
    if not m2:
        return {"ok": False, "error": "لا وكيل في الأمر — الصيغة: /task @fares التفاصيل",
                "cmd": f"/{cmd}", "executed": False}
    alias = m2.group("alias").lower()
    body = m2.group("body").strip()
    if alias not in AGENTS:
        return {"ok": False, "error": f"وكيل غير معروف @{alias} — المتاح: {', '.join(AGENTS)}",
                "cmd": f"/{cmd}", "executed": False}
    return {"ok": True, "cmd": f"/{cmd}", "agent": alias, "folder": AGENTS[alias], "body": body,
            "executed": False}


# ---------------------------------------------------------------- /task
def execute_task(decision: dict, created_by: str = "mahmoud",
                 priority: str = "normal") -> dict:
    op = new_op_id()
    title = decision["body"] or "مهمة بلا عنوان"
    agent_dir = WORKSPACES / decision["folder"]
    inbox = agent_dir / "inbox_tasks"
    inbox.mkdir(parents=True, exist_ok=True)
    fname = f"{op}.{slugify(decision['body'] or 'task')}.md"
    fpath = inbox / fname
    stamp = datetime.now().isoformat(timespec="seconds")
    fpath.write_text(
        f"# مهمة: {title}\n\n"
        f"- **المهمة**: {decision['body']}\n"
        f"- **الوكيل**: @{decision['agent']} ({decision['folder']})\n"
        f"- **الأمر**: /task @{decision['agent']} {decision['body']}\n"
        f"- **الأولوية**: {priority}\n"
        f"- **بواسطة**: {created_by}\n"
        f"- **op_id**: {op}\n"
        f"- **الحالة**: pending\n\n"
        f"---\n\n"
        f"مراجعة: {title}\n",
        encoding="utf-8",
    )
    row = {
        "agent_id": decision["agent"],
        "title": title,
        "description": f"مهمة من أمر سلاش: /task @{decision['agent']} {title}",
        "status": "pending",
        "priority": priority,
        "source": "ui",  # قيد agent_tasks_source_check لا يقبل قيماً جديدة — نستخدم ui مع وسم slash بالوصف
        "created_by": created_by,
        "op_id": op,
    }
    push_state = "OK"
    cloud_id = None
    try:
        from supabase_sync import HermesSyncManager  # noqa: E402
        cli = HermesSyncManager()._get_client()
        res = cli.table("agent_tasks").insert(row).execute()
        cloud_id = (res.data or [{}])[0].get("id")
    except Exception as exc:
        push_state = f"DEFERRED({type(exc).__name__})"
        outbox_append("agent_tasks", row, f"{type(exc).__name__}: {str(exc)[:120]}")
    log(f"TASK {decision['agent']} op_id={op} file={fpath} push={push_state}")
    return {
        "ok": True, "executed": True, "cmd": "/task", "agent": decision["agent"],
        "folder": decision["folder"], "file": str(fpath), "op_id": op,
        "push": push_state, "cloud_id": cloud_id,
    }


# ---------------------------------------------------------------- /summon و /status
def execute_summon(decision: dict) -> dict:
    dir_ = WORKSPACES / decision["folder"] / "chats"
    dir_.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    fpath = dir_ / f"summon_{stamp.replace(':', '')}.md"
    fpath.write_text(
        f"# استدعاء @{decision['agent']}\n\n"
        f"- **الأمر**: /summon @{decision['agent']} {decision['body']}\n"
        f"- **الوقت**: {stamp}\n"
        f"- **بواسطة**: المالك عبر نظام السلاش\n",
        encoding="utf-8",
    )
    log(f"SUMMON {decision['agent']} file={fpath}")
    return {"ok": True, "executed": True, "cmd": "/summon",
            "agent": decision["agent"], "message": f"استُدعي @{decision['agent']} — فُتح سجل استدعاء في ملفه"}


def execute_status(decision: dict) -> dict:
    active = WORKSPACES / decision["folder"] / "active_workspaces"
    inbox = WORKSPACES / decision["folder"] / "inbox_tasks"
    n_active = len([p for p in active.glob("*") if p.is_file()]) if active.exists() else 0
    n_inbox = len([p for p in inbox.glob("*.md") if p.is_file()]) if inbox.exists() else 0
    return {"ok": True, "executed": True, "cmd": "/status",
            "agent": decision["agent"],
            "message": f"@{decision['agent']}: {n_active} ملف عمل نشط • {n_inbox} مهمة معلقة في الـInbox"}


def dispatch(text: str, created_by: str = "mahmoud") -> dict:
    decision = parse(text)
    if not decision:
        return {"ok": False, "executed": False, "message": "كلام عادي — ليسوا أمر سلاش"}
    if not decision.get("ok"):
        return {**decision, "message": decision.get("error", "أمر غير صالح")}
    cmd = decision["cmd"]
    if cmd == "/task":
        return execute_task(decision, created_by=created_by)
    if cmd == "/summon":
        return execute_summon(decision)
    if cmd == "/status":
        return execute_status(decision)
    return {"ok": False, "executed": False, "cmd": cmd, "message": "أمر مدعوم غير قائم"}


# ---------------------------------------------------------------- watch
def watch(interval: float = 2.0) -> None:
    """دايمون مراقبة: يقرأ أمر سلاش من workspaces/system_engine/pending_slash.txt (سطر واحد لكل أمر)"""
    pending = WORKSPACES / "system_engine" / "pending_slash.txt"
    pending.parent.mkdir(parents=True, exist_ok=True)
    log(f"WATCH start interval={interval}s pending_file={pending}")
    print(f"[router_daemon] WATCH — يراقب {pending}")
    while True:
        try:
            if pending.exists():
                lines = [l.strip() for l in pending.read_text(encoding="utf-8").splitlines()
                         if l.strip().startswith("/")]
                if lines:
                    pending.write_text("", encoding="utf-8")
                    for line in lines:
                        out = dispatch(line)
                        print(f"[dispatch] {line[:60]} → ok={out.get('ok')} executed={out.get('executed')} {out.get('message', '')}")
        except Exception as exc:
            log(f"WATCH ERROR {type(exc).__name__}: {str(exc)[:120]}")
        time.sleep(interval)


def selftest() -> int:
    print("== selftest: router_daemon ==")
    ok = True
    cases = [
        ("/task @fares مراجعة حساب زينب", True),
        ("/task @sasa تشغيل الليزر عدد 2 [urgent]", True),
        ("/summon @koko حملة جديدة", True),
        ("/status @fares", True),
        ("مرحبا يا فارس", False),
        ("/task بدون وكيل", False),
        ("/task @unknown غريب", False),
        ("/unknown @fares", False),
    ]
    for text, expect in cases:
        d = parse(text)
        good = bool(d and d.get("ok")) if expect else (d is None or not d.get("ok"))
        print(f"{'PASS' if good else 'FAIL'} — {text[:45]!r} → ok={bool(d and d.get('ok'))}")
        ok = ok and good
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Router daemon with slash commands (Workspace OS)")
    sub = p.add_subparsers(dest="mode", required=True)
    p_parse = sub.add_parser("parse", help="تنفيذ أمر سلاش واحد")
    p_parse.add_argument("text")
    p_watch = sub.add_parser("watch", help="دايمون مراقبة pending_slash.txt")
    p_watch.add_argument("--interval", type=float, default=2.0)
    sub.add_parser("selftest", help="اختبار ذاتي للمحلل")
    a = p.parse_args()
    if a.mode == "selftest":
        return selftest()
    if a.mode == "parse":
        out = dispatch(a.text)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out.get("ok") else 1
    watch(a.interval)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
