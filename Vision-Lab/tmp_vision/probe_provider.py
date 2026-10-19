# -*- coding: utf-8 -*-
"""قياس حيّ لعطل المزود — تحقق مستقل من فرضية الـLead.

بيطبع JSON بـensure_ascii=True عشان كونسول ويندوز. مفيش أي مفتاح بيُطبع.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")
sys.path.insert(0, str(ROOT))

from nb import db, providers, secrets  # noqa: E402

PROMPT = "أنت مصنّف ملاحظات. صنّف النص وأعد JSON خامًا فقط بالحقول kind/category/priority.\n\nالنص:\nهاي"


def call_raw(row, payload, timeout=45):
    key = secrets.decrypt_secret(row["api_key_enc"])
    t0 = time.time()
    status, body = providers._http_json("POST", f"{row['base_url']}/chat/completions",
                                        key, payload, timeout)
    dt = time.time() - t0
    return status, body, dt


def describe(status, body, dt):
    out = {"status": status, "elapsed_s": round(dt, 2)}
    if isinstance(body, dict):
        ch = (body.get("choices") or [{}])[0]
        msg = ch.get("message", {}) or {}
        out["finish_reason"] = ch.get("finish_reason")
        out["content_len"] = len(msg.get("content") or "")
        out["content_head"] = (msg.get("content") or "")[:180]
        out["reasoning_len"] = len(msg.get("reasoning_content") or "")
        out["usage"] = body.get("usage")
        out["model"] = body.get("model")
    else:
        out["body"] = str(body)[:200]
    return out


def main() -> int:
    drow, dmodel = providers.get_default()
    if not drow:
        print(json.dumps({"error": "no default provider"}, ensure_ascii=True))
        return 1
    row = db.q("SELECT * FROM ai_providers WHERE id=%s", (drow["id"],), one=True)
    base = {"messages": [{"role": "user", "content": PROMPT}], "temperature": 0.0,
            "response_format": {"type": "json_object"}}

    variants = []

    def add(name, extra):
        p = dict(base)
        p.update(extra)
        variants.append((name, p))

    add("A_max200_current", {"max_tokens": 200})
    add("B_max200_reasonnone", {"max_tokens": 200, "reasoning_effort": "none"})
    add("C_max700", {"max_tokens": 700})
    add("D_max700_reasonnone", {"max_tokens": 700, "reasoning_effort": "none"})
    add("E_max200_repeat", {"max_tokens": 200})
    add("F_max700_nojsonmode", {"max_tokens": 700})

    results = []
    for name, payload in variants:
        try:
            status, body, dt = call_raw(row, payload)
            d = describe(status, body, dt)
        except Exception as exc:
            d = {"exc": f"{type(exc).__name__}: {exc}"}
        d["variant"] = name
        d["keys"] = sorted(k for k in payload if k != "messages")
        results.append(d)
        print(json.dumps(d, ensure_ascii=True), flush=True)

    print(json.dumps({"provider_id": row["id"], "model": dmodel,
                      "host": None, "n": len(results)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
