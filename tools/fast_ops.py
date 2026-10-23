#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""fast_ops — أداة الوكلاء السريعة: كتابة في الدفتر المحلي + دفع فوري للسحابة.
بأمر المالك 2026-10-20 (الميثاق المعماري لواجهة MARWA CORE — تكليف راصد).

المبدأ (كما كل المنظومة):
  * كتابة محلية أولاً (النوتبوك — notebook/store.py) ثم دفع سحابي idempotent
    (op_id ULID) إلى جداول agent_tasks / agent_updates عبر العميل الرسمي
    HermesSyncManager (cloud/supabase_sync.py — لا ازدواج منطق ولا مفاتيح في الكود).
  * فشل السحابة لا يُفقد شيئاً: الصف يُخزن في logs/fast_ops_outbox.jsonl
    ويُدفع تلقائياً في أول تشغيل تالٍ (flush).
  * لا حذف من السحابة إطلاقاً (W3) — لا يوجد أمر delete هنا.

الاستخدام:
  python tools/fast_ops.py task add --agent fares --title "..." [--description ...] [--priority high] [--source notebook] [--created-by marwa]
  python tools/fast_ops.py task done <note_id> [--result "..."]
  python tools/fast_ops.py update add --agent fares --kind suggestion|complaint|alert|report --title "..." [--body "..."] [--severity متوسط]
  python tools/fast_ops.py update decide <update_id> approved|rejected [--by mahmoud]
  python tools/fast_ops.py tasks [--agent fares] [--limit 20]
  python tools/fast_ops.py updates [--agent fares] [--limit 20]
  python tools/fast_ops.py flush
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE / "cloud"))
sys.path.insert(0, str(WORKSPACE))

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

OUTBOX = WORKSPACE / "logs" / "fast_ops_outbox.jsonl"

VALID_AGENTS = ("salma", "fares", "bebo", "koko", "rased", "vision", "marwa")
VALID_KINDS = ("suggestion", "complaint", "alert", "report")
VALID_SEV = ("عالي", "متوسط", "منخفض")
VALID_PRIORITY = ("low", "normal", "high", "urgent")


def new_op_id() -> str:
    """ULID مبسّط — نفس أسلوب marwa_pulse.new_op_id (idempotency)."""
    import time as _t
    import uuid as _u
    return f"{int(_t.time() * 1000):012x}-{_u.uuid4().hex[:12]}"


def get_client():
    """العميل الرسمي — يقرأ .env داخلياً (مفتاح الخدمة لا يُطبع ولا يُنسخ)."""
    from supabase_sync import HermesSyncManager  # noqa: E402 — المسار الرسمي
    return HermesSyncManager()._get_client()


def outbox_append(table: str, row: dict, reason: str) -> None:
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)
    rec = {"queued_at": datetime.now(timezone.utc).isoformat(),
           "table": table, "row": row, "reason": reason}
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def push(table: str, row: dict) -> dict | None:
    """Upsert idempotent على op_id — إعادة الدفع آمنة دائماً."""
    cli = get_client()
    res = cli.table(table).upsert(row, on_conflict="op_id").execute()
    data = res.data or []
    return data[0] if data else None


def flush_outbox() -> int:
    """دفع كل ما تأخر من دورات سابقة (انقطاع سحابة) — best effort."""
    if not OUTBOX.exists():
        return 0
    sent = 0
    kept: list[str] = []
    for line in OUTBOX.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        try:
            push(rec["table"], rec["row"])
            sent += 1
        except Exception:
            kept.append(line)
    if sent:
        OUTBOX.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
        print(f"flush: دُفع {sent} من الـoutbox المعلق")
    return sent


def _quiet_flush() -> None:
    try:
        flush_outbox()
    except Exception:
        pass  # لا يمنع الأمر الحالي أبداً


# ---------------------------------------------------------------- commands
def cmd_task_add(a) -> int:
    from notebook import store
    op = new_op_id()
    note_id = store.add_note({
        "kind": "task",
        "title": a.title,
        "body": a.description or "",
        "priority": a.priority,
        "status": "open",
        "source": f"fast_ops:{a.source}",
        "tags": f"agent:{a.agent},cloud:agent_tasks",
        "meta": json.dumps({"op_id": op, "agent_id": a.agent}, ensure_ascii=False),
    })
    row = {
        "agent_id": a.agent,
        "title": a.title,
        "description": a.description or "",
        "status": "pending",
        "priority": a.priority,
        "source": a.source,
        "created_by": a.created_by,
        "op_id": op,
    }
    try:
        cloud = push("agent_tasks", row)
        cid = (cloud or {}).get("id")
        print(f"PUSH=OK  note_id={note_id}  cloud_id={cid}  op_id={op}")
    except Exception as exc:
        outbox_append("agent_tasks", row, f"{type(exc).__name__}: {str(exc)[:120]}")
        print(f"PUSH=DEFERRED(outbox)  note_id={note_id}  op_id={op}  ({type(exc).__name__})")
    return 0


def cmd_task_done(a) -> int:
    from notebook import store
    note = store.get_note(a.note_id)
    if not note:
        print(f"FAIL: لا يوجد note id={a.note_id} في الدفتر المحلي")
        return 1
    store.set_status(a.note_id, "done")
    if a.result:
        store.update_note(a.note_id, body=((note.get("body") or "") + f"\n[نتيجة] {a.result}").strip())
    meta = {}
    try:
        meta = json.loads((note.get("meta") or "{}"))
        op = meta.get("op_id")
    except Exception:
        op = None
    if op:
        try:
            cli = get_client()
            upd = {"status": "done", "updated_at": datetime.now(timezone.utc).isoformat()}
            if a.result:
                upd["result_note"] = a.result
            res = cli.table("agent_tasks").update(upd).eq("op_id", op).execute()
            n = len(res.data or [])
            print(f"LOCAL done note_id={a.note_id}  CLOUD updated={n}  op_id={op}")
            return 0
        except Exception as exc:
            print(f"LOCAL done ✓  CLOUD FAILED ({type(exc).__name__}) — أعد المحاولة أو استخدم flush")
            return 1
    print(f"LOCAL done note_id={a.note_id} — المهمة محلية بلا op_id (سابقة على fast_ops)")
    return 0


def cmd_update_add(a) -> int:
    from notebook import store
    if a.kind not in VALID_KINDS or a.severity not in VALID_SEV:
        print("FAIL: قيمة kind/severity خارج المسموح")
        return 2
    op = new_op_id()
    local_kind = "idea" if a.kind == "suggestion" else "note"
    note_id = store.add_note({
        "kind": local_kind,
        "title": a.title,
        "body": a.body or "",
        "priority": "high" if a.severity == "عالي" else "normal",
        "status": "open",
        "source": f"fast_ops:{a.source}",
        "tags": f"agent:{a.agent},cloud:agent_updates,kind:{a.kind}",
        "meta": json.dumps({"op_id": op, "agent_id": a.agent, "update_kind": a.kind,
                            "severity": a.severity}, ensure_ascii=False),
    })
    row = {
        "agent_id": a.agent, "kind": a.kind, "title": a.title, "body": a.body or "",
        "severity": a.severity, "status": "pending", "op_id": op,
    }
    try:
        cloud = push("agent_updates", row)
        print(f"PUSH=OK  note_id={note_id}  cloud_id={(cloud or {}).get('id')}  op_id={op}")
    except Exception as exc:
        outbox_append("agent_updates", row, f"{type(exc).__name__}: {str(exc)[:120]}")
        print(f"PUSH=DEFERRED(outbox)  note_id={note_id}  op_id={op}  ({type(exc).__name__})")
    return 0


def cmd_update_decide(a) -> int:
    try:
        cli = get_client()
        res = cli.table("agent_updates").update({
            "status": a.decision,
            "decided_by": a.by,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", a.update_id).execute()
        n = len(res.data or [])
        print(f"CLOUD updated={n}  update_id={a.update_id}  status={a.decision}")
        return 0 if n else 1
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {str(exc)[:160]}")
        return 1


def cmd_tasks(a) -> int:
    cli = get_client()
    q = cli.table("agent_tasks").select(
        "id,agent_id,title,status,priority,source,created_by,created_at").order(
        "created_at", desc=True).limit(a.limit)
    if a.agent:
        q = q.eq("agent_id", a.agent)
    rows = q.execute().data or []
    print(f"agent_tasks ({len(rows)}):")
    for r in rows:
        print(f"  [{r['status']:<11}] {r['agent_id']:<7} {r['title'][:60]}  ({r['id'][:8]})")
    return 0


def cmd_updates(a) -> int:
    cli = get_client()
    q = cli.table("agent_updates").select(
        "id,agent_id,kind,title,severity,status,created_at").order(
        "created_at", desc=True).limit(a.limit)
    if a.agent:
        q = q.eq("agent_id", a.agent)
    rows = q.execute().data or []
    print(f"agent_updates ({len(rows)}):")
    for r in rows:
        print(f"  [{r['status']:<8}] {r['agent_id']:<7} {r['kind']:<10} "
              f"{r['severity'] or '-':<6} {r['title'][:50]} ({r['id'][:8]})")
    return 0


def cmd_flush(_a) -> int:
    n = flush_outbox()
    print(f"flush: {n} صف دُفع")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="fast_ops", description="أداة الوكلاء السريعة: دفتر محلي + سحابة فورية")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_task = sub.add_parser("task", help="مهام الوكلاء")
    task_sub = p_task.add_subparsers(dest="op", required=True)
    p_ta = task_sub.add_parser("add")
    p_ta.add_argument("--agent", required=True, choices=VALID_AGENTS)
    p_ta.add_argument("--title", required=True)
    p_ta.add_argument("--description", default="")
    p_ta.add_argument("--priority", default="normal", choices=VALID_PRIORITY)
    p_ta.add_argument("--source", default="notebook")
    p_ta.add_argument("--created-by", default="mahmoud")
    p_ta.set_defaults(func=cmd_task_add)

    p_td = task_sub.add_parser("done")
    p_td.add_argument("note_id", type=int)
    p_td.add_argument("--result", default="")
    p_td.set_defaults(func=cmd_task_done)

    p_upd = sub.add_parser("update", help="اقتراحات وشكاوى الوكلاء")
    upd_sub = p_upd.add_subparsers(dest="uop", required=True)
    p_ua = upd_sub.add_parser("add")
    p_ua.add_argument("--agent", required=True, choices=VALID_AGENTS)
    p_ua.add_argument("--kind", default="suggestion", choices=VALID_KINDS)
    p_ua.add_argument("--title", required=True)
    p_ua.add_argument("--body", default="")
    p_ua.add_argument("--severity", default="متوسط", choices=VALID_SEV)
    p_ua.add_argument("--source", default="notebook")
    p_ua.set_defaults(func=cmd_update_add)

    p_ud = upd_sub.add_parser("decide")
    p_ud.add_argument("update_id")
    p_ud.add_argument("decision", choices=["approved", "rejected"])
    p_ud.add_argument("--by", default="mahmoud")
    p_ud.set_defaults(func=cmd_update_decide)

    p_tl = sub.add_parser("tasks", help="عرض مهام السحابة")
    p_tl.add_argument("--agent", choices=VALID_AGENTS, default=None)
    p_tl.add_argument("--limit", type=int, default=20)
    p_tl.set_defaults(func=cmd_tasks)

    p_ul = sub.add_parser("updates")
    p_ul.add_argument("--agent", choices=VALID_AGENTS)
    p_ul.add_argument("--limit", type=int, default=20)
    p_ul.set_defaults(func=cmd_updates)

    p_f = sub.add_parser("flush")
    p_f.set_defaults(func=cmd_flush)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
