# -*- coding: utf-8 -*-
"""
Elnagar POS — Local Orchestrator core (Phase 1).
Composes the registry, routes a message, runs the chosen sub-agent, and returns a
CLEAN ARABIC reply. Callable from supabase_sync.pull_queue (action='orchestrate').
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

from .base import AgentRegistry
from .agents import build_registry


class Orquesta:
    """المنسق العام — بيستقبل كلام المستخدم → يوجه للوكيل الصح → رد عربي نظيف."""

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or build_registry()

    def route(self, text: str) -> Dict[str, Any]:
        picked, hit = self._pick_agent(text)
        if picked == "marwa":
            return {
                "text": (text or "")[:60],
                "agent_id": "marwa",
                "agent_name": "مروة — المنسق العام (الوكيل الأصلي)",
                "matched_keywords": [hit["name"]] if hit else [],
            }
        agent = picked
        if hit is not None and agent is not None:
            matched = [hit["name"]]
        else:
            matched = [
                k for k in (agent.keywords if agent else [])
                if k and k.lower() in (text or "").lower()
            ]
        return {
            "text": (text or "")[:60],
            "agent_id": agent.agent_id if agent else None,
            "agent_name": agent.name if agent else None,
            "matched_keywords": matched,
        }

    def _pick_agent(self, text: str):
        """النداء بالاسم أولًا (router.py — قاعدة «يا <اسم>») ثم التوجيه الوظيفي
        المعتاد. أي عطل في الـrouter = سقوط آمن لسلوك اليوم بالضبط."""
        try:
            from . import router
            hit = router.detect(text or "")
        except Exception:
            hit = None
        if hit:
            if hit.get("agent_id") == "marwa":
                return "marwa", hit
            agent = self.registry.get(hit.get("agent_id") or "")
            if agent is not None:
                return agent, hit
        return self.registry.route(text), None

    def _signature(self, agent) -> str:
        """سطر التوقيع باسم الشخصية — عشان المالك يعرف مين اللي رد عليه."""
        try:
            from . import router
            return router.signature(agent.agent_id)
        except Exception:
            return ""

    def handle(self, text: str) -> Dict[str, Any]:
        picked, hit = self._pick_agent(text)
        # 0) نداء «مروة» = الوكيل الأصلي — بطاقة تعريفها، ولا يمرَّر لأي وكيل فرعي
        if picked == "marwa":
            reply = None
            try:
                from . import router
                reply = router.persona_card("marwa")
            except Exception:
                reply = None
            reply = reply or (
                "أنا مروة — المنسق العام لفريق النجار برنت، والوكيل الأصلي بتاعك. 🧠"
            )
            self._record("marwa", text, [hit["name"]] if hit else [], {"reply": reply}, None)
            return {"reply": reply, "agent_id": "marwa"}
        agent = picked
        if agent is None:
            self._record(None, text, [], {"reply": "", "action": None}, "unrouted")
            return {
                "reply": (
                    "مقدرش أحدد نيتك لحالها — احكيلنا اللي محتاجه وأنا أبعته القسم الصح. 🧠"
                ),
                "agent_id": None,
            }
        t = (text or "").lower()
        matched = [k for k in agent.keywords if k and k.lower() in t]
        # 1) نداء مجرد بلا طلب («يا كوكو» وحدها) → بطاقة هوية الشخصية (إن وُجدت)
        if hit is not None:
            try:
                from . import router
                if router.is_bare_call(text or "", hit):
                    card = router.persona_card(agent.agent_id)
                    if card:
                        self._record(
                            agent.agent_id, text, [hit["name"]], {"reply": card}, None
                        )
                        return {"reply": card, "agent_id": agent.agent_id}
            except Exception:
                pass
        try:
            result = agent.handle(text)
            error = None
        except Exception as exc:  # honest failure: report + record, never invent
            result = {
                "reply": (
                    f"حصل خطأ داخل وحدة «{agent.name}» — ما افترضتش أي نتيجة. "
                    "التفاصيل اتحطت في سجل الخبرة، وابعتها للمالك فورًا."
                ),
                "action": None,
                "payload": {},
            }
            error = f"{type(exc).__name__}: {exc}"
        self._record(agent.agent_id, text, matched, result, error)
        reply = (result or {}).get("reply") or "تمام، تمام."
        sig = self._signature(agent)
        if sig:
            reply = f"{sig}\n{reply}"
        return {"reply": reply, "agent_id": agent.agent_id}

    @staticmethod
    def _record(agent_id, text, matched, result, error) -> None:
        """Best-effort ledger write — never breaks the reply flow."""
        try:
            from .agents.meta_agent import MetaAgent

            MetaAgent.record_invocation(agent_id, text, matched, result, error)
        except Exception:
            pass


# --------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Elnagar POS Local Orchestrator (Phase 1)")
    ap.add_argument("--route", type=str, help="اختبار التوجيه: --route 'كلمة'")
    ap.add_argument("--message", type=str, help="تشغيل المعالجة الكاملة: --message 'رساله'")
    args = ap.parse_args(argv)
    o = Orquesta()
    if args.route is not None:
        report = o.route(args.route)
        print(report)
        return 0
    if args.message is not None:
        out = o.handle(args.message)
        print(out.get("reply"))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
