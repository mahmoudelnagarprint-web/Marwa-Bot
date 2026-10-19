# -*- coding: utf-8 -*-
"""جسر «أفكاري» لسطر الأوامر — JSON داخل، JSON خارج.

كل حاجة هنا بتعدّي على `nb.bridge` (غلاف رقيق على `bot.process_text` وعلى
دوال `nb.db` المجمّدة) — يعني **نفس جداول المنظومة** ونفس منطق النوايا
اللي التليجرام والويب بيستخدموه. مفيش SQL ولا تفنيد نوايا مكتوب في السكربت ده.

    python scripts\\dsh_bridge.py chat "هاي" --json
    python scripts\\dsh_bridge.py add "فكرني بكرة الساعة 5" --json
    python scripts\\dsh_bridge.py list --status open --kind task --limit 20 --json
    python scripts\\dsh_bridge.py today --json
    python scripts\\dsh_bridge.py done 19 | snooze 19 60 | category 19 "تشغيل" | delete 19
    python scripts\\dsh_bridge.py search "ليزر" --json
    python scripts\\dsh_bridge.py stats --json
    python scripts\\dsh_bridge.py status --json

**مفيش أمر `send` — عن قصد.** العقد بيقول: «ممنوع أي إرسال لتليجرام من
الـbridge إلا بأمر صريح `send` + تأكيد». أخطر حاجة في جسر بيتكلم مع بوت
هو إنه يبعت رسالة لمحمود بالغلط، فسكبناه من الأصل بدل ما نحطّه وأحنا
مطمّنين؛ اللي عايز يبعت بجد يمر من `nb.bot.TelegramClient` بنداء صريح.
`chat`/`add` مابيبعتوش حاجة خالص — `process_text` بيرجّع الرد للمتصل بس.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nb import bridge  # noqa: E402


def _stdout_utf8() -> None:
    """كونسول ويندوز (cp1252) بيرمي `UnicodeEncodeError` على العربي.

    بنحوّل الستريم لـUTF-8 مع `errors="replace"` بدل ما نفشل: أي حرف
    مايتطبعش يتحوّل لـ`?` بدل ما يوقّف الأمر كله.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:                                            # noqa: BLE001
            pass


# الـstdout الحقيقي، بيتحفظ في `main` قبل ما نحوّل الباقي لـstderr.
# `None` = لسه مااتحفظش (يعني `_emit` اتنادى من بره `main`، زي اختبار).
_OUT = None


def _emit(data: Any, as_json: bool = True, human: Optional[str] = None) -> None:
    """**المكان الوحيد اللي بيطبع على `stdout`.** الباقي كله بيروح stderr.

    العقد مع العميل الآلي: `stdout` = JSON وبس. أي سطر لوج بيتخلط معاه
    بيكسّر `json.loads` عند العميل (وده اتقاس فعليًا: `config.log` بيكتب
    على stdout). فبنكتب على الستريم الحقيقي المحفوظ، وبنسيب `sys.stdout`
    متحوّل لـstderr جوّه `main` — يعني حتى لو مكتبة تانية طلعت لوج، مش
    هيلخبط المخرَج.
    """
    stream = _OUT if _OUT is not None else sys.stdout
    if as_json:
        # ensure_ascii=True: عربي آمن على أي كونسول، وأي عميل JSON بيقراه
        text = json.dumps(data, ensure_ascii=True, indent=2, sort_keys=False)
    else:
        text = human if human is not None else json.dumps(data, ensure_ascii=True)
    print(text, file=stream, flush=True)


def _table(rows: List[Dict[str, Any]], cols: tuple) -> str:
    if not rows:
        return "  (مفيش صفوف)"
    lines = []
    for r in rows:
        bits = [f"#{r.get('id')}" if "id" in cols else ""]
        for c in cols:
            if c == "id":
                continue
            val = r.get(c)
            if val is None or val == "":
                continue
            bits.append(f"{c}={val}")
        lines.append("  " + " · ".join(b for b in bits if b))
    return "\n".join(lines)


def _rows_line(rows: List[Dict[str, Any]]) -> str:
    return "\n".join(f"  #{r.get('id')} [{r.get('kind') or '-'}] {r.get('title') or r.get('content') or ''}"
                     f" | {(r.get('status') or '-')} | {r.get('due_at') or 'بلا ميعاد'}"
                     for r in rows)


# ------------------------------------------------------------------ commands
def cmd_chat(a) -> int:
    res = bridge.chat(a.text, chat_id=a.chat_id, source="bridge")
    _emit(res, a.json, f"فوفا: {res.get('reply') or '(بلا رد)'}  [{res.get('routed_by')}]")
    return 0 if res.get("ok") else 1


def cmd_add(a) -> int:
    res = bridge.add(a.text, chat_id=a.chat_id, source="bridge")
    if a.json:
        _emit(res, True)
    else:
        note = f" (#{res['note_id']})" if res.get("note_id") else ""
        _emit(res, False, f"{res.get('reply') or '(بلا رد)'}{note} | "
                          f"اتحفظ={res.get('saved')} | عبر={res.get('routed_by')}")
    return 0 if res.get("ok") else 1


def cmd_list(a) -> int:
    rows = bridge.list_captures(status=a.status, kind=a.kind, limit=a.limit)
    _emit(rows, a.json, f"{len(rows)} صف:\n{_rows_line(rows)}")
    return 0


def cmd_today(a) -> int:
    data = bridge.today()
    if a.json:
        _emit(data, True)
    else:
        _emit(data, False, f"📅 {data.get('date')} — مستحق {len(data.get('due') or [])} · "
                           f"متأخر {len(data.get('overdue') or [])} · "
                           f"النهاردة {len(data.get('due_today') or [])}\n"
                           + _rows_line((data.get("due_today") or [])[:10]))
    return 0


def cmd_search(a) -> int:
    rows = bridge.search(a.text, limit=a.limit)
    _emit(rows, a.json, f"{len(rows)} نتيجة على «{a.text}»:\n{_rows_line(rows)}")
    return 0


def cmd_stats(a) -> int:
    data = bridge.stats()
    _emit(data, a.json, " · ".join(f"{k}={v}" for k, v in data.items()))
    return 0


def cmd_status(a) -> int:
    data = bridge.status()
    _emit(data, a.json,
          f"عقدة={data.get('node')} ({data.get('device')}) · قاعدة={data.get('db')} · "
          f"قائد={data.get('leader')}")
    return 0 if data.get("db") == "ok" else 1


def cmd_action(a) -> int:
    if a.cmd == "done":
        res = bridge.done(a.id)
    elif a.cmd == "reopen":
        res = bridge.reopen(a.id)
    elif a.cmd == "snooze":
        res = bridge.snooze(a.id, a.minutes)
    elif a.cmd == "category":
        res = bridge.category(a.id, a.category)
    elif a.cmd == "delete":
        res = bridge.delete(a.id)
    else:                                              # pragma: no cover
        res = {"ok": False, "error": f"أمر مش معروف: {a.cmd}"}
    _emit(res, a.json,
          f"{res.get('action')} #{res.get('id')} → "
          + ("تم" if res.get("changed") else "مفيش صف بالمعرف ده"))
    return 0 if res.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dsh_bridge.py",
        description="جسر أفكاري — نفس جداول المنظومة، وبنفس منطق نوايا البوت.",
    )
    # `--json` على الأب عشان يشتغل قبل الأمر أو بعده بالظبط زي العقد
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="اطبع JSON")
    common.add_argument("--chat-id", type=int, default=None,
                        help="هوية المحادثة (افتراضيًا محادثة المالك)")

    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("chat", parents=[common], help="كلام حر مع فوفا (بلا تليجرام)")
    s.add_argument("text")
    s.set_defaults(func=cmd_chat)

    s = sub.add_parser("add", parents=[common], help="بوابة النوايا: تحفظ لو فيها إشارة التقاط")
    s.add_argument("text")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("list", parents=[common], help="نفس صفوف الويب")
    s.add_argument("--status", default="open", help="open | done | all (افتراضي open)")
    s.add_argument("--kind", default=None, help="task | idea | reminder | …")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("today", parents=[common], help="مستحق + متأخر + ميعاد النهاردة")
    s.set_defaults(func=cmd_today)

    s = sub.add_parser("search", parents=[common], help="بحث في كل الحالات")
    s.add_argument("text")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("stats", parents=[common], help="أرقام اللوحة")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("status", parents=[common], help="حالة العقدة والقاعدة والتوفّر العالي")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("done", parents=[common], help="خلّص نوتة")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_action)

    s = sub.add_parser("reopen", parents=[common], help="رجّعها مفتوحة")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_action)

    s = sub.add_parser("snooze", parents=[common], help="أخّرها كام دقيقة")
    s.add_argument("id", type=int)
    s.add_argument("minutes", type=int)
    s.set_defaults(func=cmd_action)

    s = sub.add_parser("category", parents=[common], help="حدّد التصنيف")
    s.add_argument("id", type=int)
    s.add_argument("category")
    s.set_defaults(func=cmd_action)

    s = sub.add_parser("delete", parents=[common], help="امسح نوتة")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_action)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    global _OUT
    _stdout_utf8()
    _OUT = sys.stdout                       # نحفظه قبل التحويل
    # كل لوج (من `config.log` أو غيره) لازم يروح stderr — العقد بيقول
    # stdout = JSON وبس. الاستيراد فوق بيحصل قبل ده، فبنحرّك الستريم هنا
    # كمان عشان أي استيراد جوّه الأمر يطلع على stderr برضه.
    sys.stdout = sys.stderr
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:                                  # pragma: no cover
        _emit({"ok": False, "error": "اتقاطع"}, getattr(args, "json", True))
        return 130
    except Exception as exc:                                   # noqa: BLE001
        _emit({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
              getattr(args, "json", True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
