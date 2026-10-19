# -*- coding: utf-8 -*-
"""قياس أعمق: هل الرد فيه JSON فعلا؟ وإيه اللي بيعطّل التفكير فعلًا؟"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")
sys.path.insert(0, str(ROOT))

from nb import ai_router, db, providers, secrets  # noqa: E402

PROMPT = ai_router._CLOUD_PROMPT + "هاي"


def strip_think(text: str) -> str:
    t = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text or "", flags=re.DOTALL | re.I)
    return t.replace("</think>", "").replace("<think>", "").strip()


def find_json(text: str):
    """استخراج متوازن غير جشع."""
    t = strip_think(re.sub(r"```(?:json)?", "", text or ""))
    dec = json.JSONDecoder()
    for m in re.finditer(r"\{", t):
        try:
            obj, _ = dec.raw_decode(t[m.start():])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def main() -> int:
    drow, dmodel = providers.get_default()
    row = db.q("SELECT * FROM ai_providers WHERE id=%s", (drow["id"],), one=True)
    key = secrets.decrypt_secret(row["api_key_enc"])
    print(json.dumps({"provider": row["name"], "base_host_kind": "gateway",
                      "default_model": dmodel}, ensure_ascii=True))

    def run(name, extra, timeout=60):
        payload = {"messages": [{"role": "user", "content": PROMPT}],
                   "temperature": 0.0, "max_tokens": 200,
                   "response_format": {"type": "json_object"}}
        payload.update(extra)
        t0 = time.time()
        try:
            status, body = providers._http_json("POST", f"{row['base_url']}/chat/completions",
                                                key, payload, timeout)
        except Exception as exc:
            print(json.dumps({"v": name, "exc": f"{type(exc).__name__}"}, ensure_ascii=True))
            return
        dt = round(time.time() - t0, 2)
        if not isinstance(body, dict):
            print(json.dumps({"v": name, "status": status, "elapsed": dt,
                              "body": str(body)[:120]}, ensure_ascii=True)); return
        ch = (body.get("choices") or [{}])[0]
        msg = ch.get("message") or {}
        content = msg.get("content") or ""
        obj = find_json(content)
        rec = {"v": name, "status": status, "elapsed": dt,
               "finish": ch.get("finish_reason"),
               "clen": len(content),
               "has_think": "<think" in content.lower(),
               "after_strip_len": len(strip_think(content)),
               "json_found": obj is not None,
               "json_keys": sorted(obj.keys())[:6] if isinstance(obj, dict) else None,
               "ctok": (body.get("usage") or {}).get("completion_tokens"),
               "tail": content[-160:].replace("\n", " ")}
        print(json.dumps(rec, ensure_ascii=True), flush=True)

    run("P1_max200_thinkoff", {"max_tokens": 200, "thinking": {"type": "disabled"}})
    run("P2_max200_reasonnone", {"max_tokens": 200, "reasoning_effort": "none"})
    run("P3_max700_prefill", {"max_tokens": 700})
    run("P4_max1200_reasonnone", {"max_tokens": 1200, "reasoning_effort": "none"})

    # prefill: نبدأ رد المساعد بـ{ عشان نجبره على JSON
    payload = {"messages": [{"role": "user", "content": PROMPT},
                            {"role": "assistant", "content": "{"}],
               "temperature": 0.0, "max_tokens": 700,
               "response_format": {"type": "json_object"}}
    t0 = time.time()
    status, body = providers._http_json("POST", f"{row['base_url']}/chat/completions",
                                        key, payload, 60)
    dt = round(time.time() - t0, 2)
    if isinstance(body, dict):
        ch = (body.get("choices") or [{}])[0]
        content = (ch.get("message") or {}).get("content") or ""
        obj = find_json("{" + content)
        print(json.dumps({"v": "P5_prefill", "status": status, "elapsed": dt,
                          "finish": ch.get("finish_reason"), "clen": len(content),
                          "has_think": "<think" in content.lower(),
                          "json_found": obj is not None,
                          "json_keys": sorted(obj.keys())[:6] if isinstance(obj, dict) else None,
                          "tail": content[-160:].replace("\n", " ")}, ensure_ascii=True))
    else:
        print(json.dumps({"v": "P5_prefill", "status": status, "elapsed": dt,
                          "body": str(body)[:120]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
