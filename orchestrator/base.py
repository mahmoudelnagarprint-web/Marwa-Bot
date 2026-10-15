# -*- coding: utf-8 -*-
"""
Sub-agent interface + registry (Phase 1 → Phase 2 auto-discovery).
Every sub-agent is a separate module in agents/*.py implementing SubAgent.
Auto-discovery: AgentRegistry scans agents/ for SubAgent subclasses at init.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SubAgent:
    """Base contract every sub-agent implements."""

    agent_id: str
    name: str
    keywords: List[str] = field(default_factory=list)  # Arabic/English trigger words
    phase: int = 1  # the phase that fully builds this agent

    def can_handle(self, text: str) -> bool:
        t = (text or "").lower()
        return any(k.lower() in t for k in self.keywords if k)

    def handle(
        self, text: str, ctx: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return {"reply": clean Arabic text, "action": Optional[str], "payload": dict}."""
        raise NotImplementedError


class AgentRegistry:
    """Holds every registered sub-agent; routes a message by keyword first.
    Auto-discovers SubAgent subclasses in orchestrator/agents/ at initialization.
    """

    def __init__(self, agents: Optional[List[SubAgent]] = None):
        self._agents: Dict[str, SubAgent] = {}
        # 1) Explicitly passed agents (backward compatibility)
        for a in agents or []:
            self.register(a)
        # 2) Auto-discovery from agents/ package
        self._auto_discover()

    def _auto_discover(self) -> None:
        """Scan orchestrator/agents/*.py for SubAgent subclasses and register them."""
        agents_dir = Path(__file__).resolve().parent / "agents"
        if not agents_dir.exists():
            return
        # Import the agents package to trigger module execution
        try:
            import orchestrator.agents as agents_pkg
        except Exception:
            return
        # Walk all modules in the package
        for _, modname, ispkg in pkgutil.iter_modules(agents_pkg.__path__):
            if ispkg or modname.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"orchestrator.agents.{modname}")
            except Exception:
                continue
            # Find all SubAgent subclasses defined in this module (not imported)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    obj is not SubAgent
                    and issubclass(obj, SubAgent)
                    and obj.__module__ == module.__name__
                ):
                    try:
                        instance = obj()
                        self.register(instance)
                    except Exception:
                        pass  # skip broken agents silently

    def register(self, agent: SubAgent) -> None:
        self._agents[agent.agent_id] = agent

    def get(self, agent_id: str) -> Optional[SubAgent]:
        return self._agents.get(agent_id)

    def all(self) -> List[SubAgent]:
        return list(self._agents.values())

    def route(self, text: str) -> Optional[SubAgent]:
        """Agent with most keyword hits wins (registry insertion order as tie-break)."""
        t = (text or "").lower()
        best = None
        best_hits = 0
        for a in self._agents.values():
            hits = sum(1 for k in a.keywords if k and k.lower() in t)
            if hits > best_hits:
                best = a
                best_hits = hits
        return best if best_hits > 0 else None

    def route_report(self, text: str) -> Dict[str, Any]:
        """Read-only routing report (used by the owner-facing diagnostic)."""
        agent = self.route(text)
        return {
            "text": text[:60],
            "agent_id": agent.agent_id if agent else None,
            "agent_name": agent.name if agent else None,
            "matched_keywords": [
                k for k in (agent.keywords if agent else []) if k and k.lower() in (text or "").lower()
            ],
        }