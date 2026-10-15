# -*- coding: utf-8 -*-
"""
Elnagar POS — Local Orchestrator (Phase 1)
=========================================
The "مسند" (Orchestrator) brain of the workshop, running LOCALLY (per owner's
decision 2: logic always on the shop machine; cloud webhook stays a queue/fallback).
Phase 1 = routing foundation + sub-agent interfaces + stubs. Final per-phase builds
of each sub-agent land in orchestrator/agents/*.py.

Safety rules enforced inside the module:
  * NEVER auto-executes a financial write (payments, price changes, debt write-off).
    Those return a prompt asking the owner to confirm, or are moved to `commands`
    for the sync engine's official local functions.
  * No fabricated data: if a DB/cloud call fails, it says so truthfully.
  * Telegram replies are clean Arabic text, no code, no thinking tokens — this is
    enforced by the replies being the single text `reply` returned by each agent.
"""
