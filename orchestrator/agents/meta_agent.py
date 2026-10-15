# -*- coding: utf-8 -*-
"""Meta-Agent (المراقب الذاتي) — سجل خبرة تراكمي للتطوير الذاتي.
Full build: Phase 7+ (سجل الخبرة + اقتراح تحسينات على تعليمات الوكلاء).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SubAgent


def _fmt(n) -> str:
    try:
        f = float(n)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(n)


class MetaAgent(SubAgent):
    LEDGER_PATH = (
        Path(r"G:\ai\Naggar Print POS Agent\memory\experience_ledger.json")
    )
    _lock = threading.Lock()

    def __init__(self):
        super().__init__(
            agent_id="meta",
            name="المراقب الذاتي (Meta-Agent)",
            keywords=[
                "راقب نفسك", "تقييم ذاتي", "طور نفسك", "meta", "مراجعه ذاتيه",
                "سجل الخبرة", "خبرة", "ledger", "تحسين", "تطوير ذاتي",
                "سجل درس", "add lesson", "درس",
                "إحصائيات", "stats", "statistics", "إحصائي", "تقرير",
                "استدعاء", "استدعاءات",
                "اقتراحات", "تطوير ذاتي", "تحسين ذاتي", "أداء", "أداء الوكلاء", "تقرير الأداء",
            ],
            phase=7,
        )

    @classmethod
    def _read_ledger(cls) -> Dict[str, Any]:
        try:
            if cls.LEDGER_PATH.exists():
                return json.loads(cls.LEDGER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"schema_version": 1, "entries": []}

    @classmethod
    def _write_ledger(cls, data: Dict[str, Any]) -> bool:
        try:
            with cls._lock:
                cls.LEDGER_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            return True
        except Exception:
            return False

    @classmethod
    def record_invocation(
        cls,
        agent_id: str,
        text: str,
        matched_keywords: List[str],
        result: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """Record an agent invocation in the experience ledger."""
        data = cls._read_ledger()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "input_text": text[:200],
            "matched_keywords": matched_keywords,
            "result_action": (result or {}).get("action"),
            "result_keys": list((result or {}).keys()),
            "error": error,
        }
        data.setdefault("entries", []).append(entry)
        cls._write_ledger(data)

    @classmethod
    def record_lesson(cls, lesson: str, source_agent: str, confidence: float = 1.0) -> None:
        """Record a learned lesson for future self-improvement."""
        data = cls._read_ledger()
        data.setdefault("lessons", []).append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "lesson": lesson,
                "source_agent": source_agent,
                "confidence": confidence,
            }
        )
        cls._write_ledger(data)

    def handle(self, text, ctx=None):
        t = (text or "").lower()
        ledger = self._read_ledger()
        entries = ledger.get("entries", [])
        lessons = ledger.get("lessons", [])

        if "سجل درس" in t or "add lesson" in t:
            lesson_text = text.split(":", 1)[-1].strip() if ":" in text else text.replace("سجل درس", "").strip()
            if lesson_text:
                self.record_lesson(lesson_text, "meta", 0.9)
                return {
                    "reply": f"✅ تم تسجيل الدرس: {lesson_text[:80]}",
                    "action": "record_lesson",
                    "payload": {"lesson": lesson_text},
                }
            return {
                "reply": "اكتب الدرس بعد «سجل درس: ...» أو «add lesson: ...»",
                "action": None,
                "payload": {},
            }

        if "آخر" in t and ("استدعاء" in t or "invocation" in t):
            recent = entries[-5:] if entries else []
            lines = []
            for e in recent:
                ts = (e.get("timestamp") or "")[:19].replace("T", " ")
                aid = e.get("agent_id") or "غير موجَّه"
                act = e.get("result_action") or "—"
                err = f" ⚠️ {(e.get('error') or '')[:60]}" if e.get("error") else ""
                lines.append(f"{ts} | {aid} | {act}{err}")
            return {
                "reply": "آخر الاستدعاءات:\n" + ("\n".join(lines) if lines else "لا يوجد استدعاءات بعد."),
                "action": "show_recent_invocations",
                "payload": {"recent": recent},
            }

        if "إحصائيات" in t or "stats" in t:
            by_agent = {}
            for e in entries:
                aid = e.get("agent_id") or "غير موجَّه"
                by_agent[aid] = by_agent.get(aid, 0) + 1
            return {
                "reply": (
                    f"إحصائيات الاستدعاءات ({len(entries)} إجمالي):\n"
                    + "\n".join(
                        f"• {aid}: {cnt}"
                        for aid, cnt in sorted(by_agent.items(), key=lambda kv: str(kv[0]))
                    )
                    + f"\n\nدروس مستفادة: {len(lessons)}"
                ),
                "action": "show_stats",
                "payload": {"by_agent": by_agent, "lessons": len(lessons)},
            }

        if "سجل" in t or "ledger" in t or "خبرة" in t:
            return {
                "reply": (
                    f"سجل الخبرة الحالي: {len(entries)} استدعاء، {len(lessons)} درس.\n"
                    f"الملف: {self.LEDGER_PATH}\n\n"
                    "يمكنك أن تطلب:\n"
                    "• «آخر استدعاءات»\n"
                    "• «سجل درس: كذا وكذا»\n"
                    "• «إحصائيات الوكلاء»"
                ),
                "action": "show_ledger_summary",
                "payload": {"entries_count": len(entries), "lessons_count": len(lessons)},
            }

        if any(k in t for k in ("اقتراحات التطوير", "طور نفسك", "تطوير ذاتي", "تحسين ذاتي", "اقتراح تحسين", "اقتراحات")):
            unrouted = [e for e in entries if not e.get("agent_id") or e.get("agent_id") == "غير موجَّه"]
            err_by_agent: Dict[str, int] = {}
            for e in entries:
                if e.get("error"):
                    aid = e.get("agent_id") or "غير موجَّه"
                    err_by_agent[aid] = err_by_agent.get(aid, 0) + 1
            lines = [
                f"• اقتراحات مبنية على السجل ({len(entries)} استدعاء):",
            ]
            if unrouted:
                lines.append(f"• عدد الرسائل غير الموجَّهة (فرصة كلمات توجيه جديدة): {len(unrouted)}")
                samples = [e.get("input_text") or "" for e in unrouted[-5:]]
                lines.append("  أمثلة: " + " | ".join(s[:60] for s in samples))
            if err_by_agent:
                lines.append("• أخطاء مسجلة بالوكيل:")
                lines.append("  " + "\n  ".join(
                    f"{aid}: {cnt}" for aid, cnt in sorted(err_by_agent.items(), key=lambda kv: str(kv[0]))))
            else:
                lines.append("• أخطاء مسجلة: صفر ✅")
            lines.append(f"• دروس مستفادة: {len(lessons)}")
            lines.append("🔒 مقترحات فقط — تطبيقها (تعديل تعليمات/كلمات التوجيه) بموافقتك عبر DSH.")
            return {
                "reply": "\n".join(lines),
                "action": "self_improve_proposals",
                "payload": {"unrouted": len(unrouted), "errors_by_agent": err_by_agent,
                            "lessons": len(lessons)},
            }

        if "أداء الوكلاء" in t or ("تقرير" in t and "استدعاء" in t) or "تقرير الأداء" in t:
            per: Dict[str, Dict[str, Any]] = {}
            for e in entries:
                aid = e.get("agent_id") or "غير موجَّه"
                d = per.setdefault(aid, {"total": 0, "errors": 0, "last": ""})
                d["total"] += 1
                if e.get("error"):
                    d["errors"] += 1
                ts = e.get("timestamp") or ""
                if ts > d["last"]:
                    d["last"] = ts
            lines = [f"• تقرير أداء الوكلاء (آخر {len(entries)} استدعاء من السجل):"]
            for aid, d in sorted(per.items(), key=lambda kv: (-kv[1]["errors"], -kv[1]["total"], str(kv[0]))):
                rate = f" ({_fmt(d['errors'] * 100 / d['total'])}% خطأ)" if d["errors"] else ""
                lines.append(
                    f"  • {aid}: {d['total']} استدعاء — {d['errors']} خطأ{rate}"
                    f" — آخر استخدام {(d['last'][:19]).replace('T', ' ') if d['last'] else '—'}")
            lines.append("💡 للإصلاح: «رصد الأخطاء» (كودر) أو «اقتراحات التطوير» (هنا).")
            return {
                "reply": "\n".join(lines),
                "action": "show_performance",
                "payload": {"by_agent": per},
            }

        return {
            "reply": (
                "المراقب الذاتي (Meta-Agent) — سجل خبرة تراكمي جاهز.\n"
                "الأوامر: «سجل الخبرة»، «آخر استدعاءات»، «سجل درس: ...»، «إحصائيات الوكلاء»، "
                "«تقرير الأداء»، «اقتراحات التطوير».\n"
            ),
            "action": None,
            "payload": {},
        }