# -*- coding: utf-8 -*-
"""Elnagar POS — sub-agents package (Phase 2 auto-discovery).
Auto-discovery loads every SubAgent subclass in this directory.
build_registry() kept for backward compatibility (returns empty registry;
auto-discovery in AgentRegistry.__init__ does the real work).
"""
from __future__ import annotations

from ..base import AgentRegistry, SubAgent


def build_registry() -> AgentRegistry:
    """Return an empty registry — auto-discovery populates it."""
    return AgentRegistry()