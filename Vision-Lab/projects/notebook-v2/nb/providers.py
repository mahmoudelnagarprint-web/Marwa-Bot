# -*- coding: utf-8 -*-
"""سجل مزودي الذكاء الاصطناعي السحابيين — R3.

- كل المزودين OpenAI-compatible: DeepSeek / OpenAI / Groq / Dahl / أي بوابة.
- المفاتيح تُخزن مشفرة (nb.secrets) ولا تُقرأ إلا لحظة النداء.
- اكتشاف النماذج: GET {base_url}/models — تُخزن في ai_models.
- التبديل الديناميكي: settings.default_provider_id/default_model_id —
  يأثر فورًا على كل نداءات chat() بلا إعادة تشغيل.
- HTTP بمكتبات بايثون القياسية فقط (urllib) — نفس عرف v1.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from nb import config, db, secrets


class ProviderError(RuntimeError):
    pass


# ------------------------------------------------------------------ التفكير
# نماذج التفكير (reasoning) على بوابة DAHL بترجّع **كتلة تفكير مكتوبة جوه
# `content` نفسه** بوسم <think>…</think>، وبعدها الرد الفعلي. ومن غير تنضيف،
# الرد بيبان للمستخدم كتفكير خام، ولو الرد اتقطع (finish_reason=length) بيبقى
# تفكير ناقص بلا أي JSON → سقوط صامت للقواعد المحلية.
#
# **قياس حيّ (2026-10-19) على الموديل الافتراضي:** `reasoning_effort=none`
# و`thinking.disabled` **مابيوقفوش** التفكير على البوابة دي (الاتنين رجّعوا
# كتلة <think>) — فالتنضيف هنا مش تحسين شكلي، ده المسار الوحيد الموثوق.
_THINK_PATTERNS = (
    re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
    re.compile(r"```(?:think|thinking|reasoning)[^\n]*\n.*?```", re.DOTALL | re.IGNORECASE),
)
# وسم مفتوح بلا إغلاق = الرد اتقطع وسط التفكير: اقطع من أول وسم لآخره.
_UNCLOSED = (
    re.compile(r"<think(?:ing)?>.*\Z", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*\Z", re.DOTALL | re.IGNORECASE),
)


def strip_reasoning(text: str) -> str:
    """يشيل كتل التفكير من رد الموديل.

    لو التنضيف خلّى النص فاضي (الرد كله تفكير) نرجّع النص الأصلي بصدق —
    عشان مستخرج الـJSON (غير الجشع) يقدر يلقط أي كائن جوه التفكير.
    """
    original = text or ""
    out = original
    for pat in _THINK_PATTERNS:
        out = pat.sub("", out)
    for pat in _UNCLOSED:
        out = pat.sub("", out)
    cleaned = out.strip()
    return cleaned or original.strip()


def _has_json_object(text: str) -> bool:
    return "{" in (text or "") and "}" in (text or "")


# ------------------------------------------------------------------ presets
def presets() -> List[Dict[str, str]]:
    out = [
        {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1"},
        {"name": "OpenAI", "base_url": "https://api.openai.com/v1"},
        {"name": "Groq", "base_url": "https://api.groq.com/openai/v1"},
    ]
    dahl = config.get("DAHL_API_URL")
    if dahl:
        out.insert(0, {"name": "Dahl (بوابة DAHL)", "base_url": dahl.rstrip("/")})
    return out


# ------------------------------------------------------------------ HTTP
def _http_json(method: str, url: str, api_key: str,
               payload: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Tuple[int, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", "replace")[:500]
        except Exception:
            body = ""
        return exc.code, body
    except Exception as exc:
        return 0, f"{type(exc).__name__}: {exc}"


def _clean_base(base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base


# ------------------------------------------------------------------ CRUD
def list_providers() -> List[Dict[str, Any]]:
    rows = db.q("""SELECT p.*,
                          (SELECT COUNT(*) FROM ai_models m WHERE m.provider_id = p.id) AS models_count
                   FROM ai_providers p ORDER BY p.id""")
    def_pid = db.get_setting("default_provider_id")
    def_mid = db.get_setting("default_model_id")
    out = []
    for r in rows:
        r["key_masked"] = secrets.mask(r["api_key_enc"])
        r["is_default"] = (r["id"] == def_pid)
        r["default_model_id"] = def_mid if r["is_default"] else None
        r.pop("api_key_enc", None)
        out.append(r)
    return out


def add_provider(name: str, base_url: str, api_key: str,
                 kind: str = "openai-compatible", notes: str = "") -> Dict[str, Any]:
    name = (name or "").strip()
    base = _clean_base(base_url)
    if not name or not base or not api_key:
        raise ProviderError("الاسم و base_url والمفتاح كلهم مطلوبين")
    pid = db.q("""INSERT INTO ai_providers(name, kind, base_url, api_key_enc, notes)
                  VALUES (%s,%s,%s,%s,%s) RETURNING id""",
               (name, kind, base, secrets.encrypt_secret(api_key), notes), one=True)["id"]
    return get_provider(pid)


def get_provider(pid: int, with_key: bool = False) -> Optional[Dict[str, Any]]:
    row = db.q("SELECT * FROM ai_providers WHERE id = %s", (pid,), one=True)
    if row and not with_key:
        row.pop("api_key_enc", None)
    return row


def update_provider(pid: int, name: Optional[str] = None, base_url: Optional[str] = None,
                    api_key: Optional[str] = None, active: Optional[bool] = None,
                    notes: Optional[str] = None) -> bool:
    sets, params = ["updated_at = now()"], []
    if name is not None:
        sets.append("name = %s"); params.append(name.strip())
    if base_url is not None:
        sets.append("base_url = %s"); params.append(_clean_base(base_url))
    if api_key:
        sets.append("api_key_enc = %s"); params.append(secrets.encrypt_secret(api_key))
    if active is not None:
        sets.append("active = %s"); params.append(active)
    if notes is not None:
        sets.append("notes = %s"); params.append(notes)
    params.append(pid)
    return db.x(f"UPDATE ai_providers SET {', '.join(sets)} WHERE id = %s", params) > 0


def delete_provider(pid: int) -> bool:
    ok = db.x("DELETE FROM ai_providers WHERE id = %s", (pid,)) > 0
    if db.get_setting("default_provider_id") == pid:
        db.set_setting("default_provider_id", None)
        db.set_setting("default_model_id", None)
    return ok


def _api_key(pid: int) -> str:
    row = db.q("SELECT api_key_enc, base_url, active, name FROM ai_providers WHERE id = %s",
               (pid,), one=True)
    if not row:
        raise ProviderError(f"مزود {pid} غير موجود")
    if not row["active"]:
        raise ProviderError(f"المزود «{row['name']}» موقوف")
    return secrets.decrypt_secret(row["api_key_enc"])


# ------------------------------------------------------------------ discovery
def discover_models(pid: int) -> List[str]:
    """GET {base}/models ← upsert في ai_models — يرجع قائمة المعرفات."""
    row = get_provider(pid)
    if not row:
        raise ProviderError(f"مزود {pid} غير موجود")
    key = _api_key(pid)
    status, body = _http_json("GET", f"{row['base_url']}/models", key, timeout=30)
    if status != 200 or not isinstance(body, dict):
        _mark_check(pid, False, f"HTTP {status}: {str(body)[:200]}")
        raise ProviderError(f"اكتشاف النماذج فشل (HTTP {status}) — {str(body)[:200]}")
    ids: List[str] = []
    for item in body.get("data") or []:
        mid = item.get("id")
        if mid:
            ids.append(mid)
            db.x("""INSERT INTO ai_models(provider_id, model_id, label, capabilities)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (provider_id, model_id) DO UPDATE
                       SET label = EXCLUDED.label, capabilities = EXCLUDED.capabilities""",
                 (pid, mid, item.get("owned_by") or None,
                  __import__("psycopg2").extras.Json(item)))
    _mark_check(pid, True, f"تم اكتشاف {len(ids)} نموذج")
    return sorted(ids)


def _mark_check(pid: int, ok: bool, msg: str) -> None:
    db.x("""UPDATE ai_providers
            SET last_check_at = now(), last_check_ok = %s, last_check_msg = %s
            WHERE id = %s""", (ok, msg[:300], pid))


def models_of(pid: int) -> List[Dict[str, Any]]:
    return db.q("SELECT model_id, label, active, discovered_at FROM ai_models WHERE provider_id=%s ORDER BY model_id",
                (pid,))


# ------------------------------------------------------------------ defaults
def set_default(pid: int, model_id: str) -> None:
    if not get_provider(pid):
        raise ProviderError(f"مزود {pid} غير موجود")
    if not db.q("SELECT 1 FROM ai_models WHERE provider_id=%s AND model_id=%s", (pid, model_id)):
        raise ProviderError("النموذج غير مكتشف عند هذا المزود — شغّل الاكتشاف الأول")
    db.set_setting("default_provider_id", pid)
    db.set_setting("default_model_id", model_id)


def get_default() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """(صف المزود بدون مفتاح، معرّف النموذج) أو (None, None)."""
    pid = db.get_setting("default_provider_id")
    if pid is None:
        return None, None
    row = get_provider(int(pid))
    if not row or not row["active"]:
        return None, None
    return row, db.get_setting("default_model_id")


def _fallback_providers() -> List[Tuple[Dict[str, Any], str]]:
    """أي مزود نشط لديه نماذج مكتشفة — بديل تلقائي عند فشل الافتراضي."""
    out = []
    for p in db.q("SELECT * FROM ai_providers WHERE active ORDER BY id"):
        m = db.q("SELECT model_id FROM ai_models WHERE provider_id=%s ORDER BY model_id LIMIT 1", (p["id"],))
        if m:
            out.append((p, m[0]["model_id"]))
    return out


# ------------------------------------------------------------------ chat
def _post_chat(row: Dict[str, Any], key: str, payload: Dict[str, Any],
               timeout: float) -> Tuple[int, Any]:
    return _http_json("POST", f"{row['base_url']}/chat/completions", key, payload, timeout)


def _adjust_payload(payload: Dict[str, Any], status: int, body: Any) -> bool:
    """يشيل المفاتيح التجريبية عند رفض المزود لها. True = اتغيّر payload.

    مزودات OpenAI-compatible الصارمة بترفض أي باراميتر مش معروف — فبنشيلها
    بالتدريج بدل ما النداء يفشل كله.
    """
    low = str(body).lower()
    generic = any(w in low for w in ("unknown", "unsupported", "unrecognized",
                                    "invalid", "extra", "valid"))
    for field in ("thinking", "reasoning_effort"):
        if field in payload and (field in low or "reasoning" in low or generic):
            payload.pop(field, None)
            return True
    if status == 400 and "response_format" in payload and (
            "response_format" in low or "json" in low or generic):
        payload.pop("response_format", None)
        return True
    return False


def chat(messages: List[Dict[str, str]], model_id: Optional[str] = None,
         provider_id: Optional[int] = None, max_tokens: int = 600,
         temperature: float = 0.3, json_mode: bool = False,
         timeout: int = 45, reasoning_off: bool = True, retries: int = 1,
         min_tokens: int = 700, total_timeout: float = 0) -> Tuple[str, Dict[str, Any]]:
    """نداء دردشة عبر المزود المحدد ثم الافتراضي ثم أي بديل نشط.

    يرجع (النص بعد تنضيف التفكير، meta{provider_id, provider, model,
    finish_reason, completion_tokens, attempts, elapsed_ms, reasoning_stripped}).

    `reasoning_off`: يمنع التفكير بالباراميترات المعروفة **وبيرفع سقف التوكن
    كشبكة أمان** — نماذج التفكير بتاكل السقف كله جوه التفكير وترجّع محتوى مقطوع.
    ولو رجع 200 بمحتوى فاضي/مقطوع/بلا JSON، بيعيد المحاولة بسقف أكبر.
    """
    cap = max(int(max_tokens), int(min_tokens)) if reasoning_off else int(max_tokens)
    deadline = time.monotonic() + (total_timeout or max(20.0, timeout * 2.0))

    tried: List[Tuple[Dict[str, Any], str]] = []
    if provider_id:
        row = get_provider(provider_id)
        if row:
            key_row = db.q("SELECT api_key_enc FROM ai_providers WHERE id=%s", (provider_id,), one=True)
            tried.append(({**row, "api_key_enc": key_row["api_key_enc"]}, model_id or "default"))
    else:
        drow, dmodel = get_default()
        if drow:
            key_row = db.q("SELECT api_key_enc FROM ai_providers WHERE id=%s", (drow["id"],), one=True)
            tried.append(({**drow, "api_key_enc": key_row["api_key_enc"]}, model_id or dmodel or "default"))
    tried += _fallback_providers()

    errors: List[str] = []
    seen = set()
    attempts_total = 0
    for row, mdl in tried:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        key = secrets.decrypt_secret(row["api_key_enc"])
        cap_here = cap
        for attempt in range(1 + max(0, int(retries))):
            remaining = deadline - time.monotonic()
            if remaining <= 1.0:
                errors.append(f"{row['name']}: انتهت الميزانية الزمنية قبل المحاولة {attempt}")
                break
            payload: Dict[str, Any] = {"messages": messages, "max_tokens": cap_here,
                                       "temperature": temperature}
            if mdl and mdl != "default":
                payload["model"] = mdl
            if reasoning_off:
                payload["reasoning_effort"] = "none"
                payload["thinking"] = {"type": "disabled"}
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            status, body = _post_chat(row, key, payload, min(timeout, remaining))
            for _ in range(3):
                if status != 400 or not _adjust_payload(payload, status, body):
                    break
                signals = [k for k in ("reasoning_effort", "thinking", "response_format")
                           if k in payload]
                config.log(f"providers: المزود «{row['name']}» رفض باراميترات "
                           f"(HTTP 400) — إعادة بدون {signals}")
                status, body = _post_chat(row, key, payload, min(timeout, remaining))
            attempts_total += 1

            if status == 200 and isinstance(body, dict):
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                raw = message.get("content") or ""
                finish = choice.get("finish_reason")
                usage = body.get("usage") or {}
                ctok = usage.get("completion_tokens")
                clean = strip_reasoning(raw)
                stripped = bool(raw) and clean != raw.strip()
                usable = bool(clean)
                if json_mode:
                    usable = _has_json_object(clean) or _has_json_object(raw)
                if usable and clean:
                    if stripped or (finish == "length" and attempt):
                        config.log(f"providers: {row['name']} رد في المحاولة {attempt + 1} "
                                   f"(finish={finish}, ctok={ctok}, "
                                   f"اتشال تفكير={'نعم' if stripped else 'لا'})")
                    return clean.strip(), {
                        "provider_id": row["id"], "provider": row["name"], "model": mdl,
                        "finish_reason": finish, "completion_tokens": ctok,
                        "attempts": attempts_total, "reasoning_stripped": stripped,
                    }
                detail = ("رد فاضي" if not raw else
                          ("رد بلا JSON" if json_mode else "رد غير صالح"))
                errors.append(f"{row['name']}: {detail} (finish={finish}, ctok={ctok}, "
                              f"max_tokens={cap_here}, محاولة {attempt + 1})")
                cap_here = max(cap_here * 2, 1400)
                config.log(f"providers: {errors[-1]} — إعادة بسقف {cap_here}")
            else:
                errors.append(f"{row['name']}: HTTP {status} {str(body)[:160]}")
                break
    raise ProviderError("كل المحاولات فشلت — " + " | ".join(errors[:4]))


def test_provider(pid: int) -> Tuple[bool, str, str]:
    """اختبار حقيقي بمفتاح المزود — يرجع (تم؟, رسالة, النموذج المستخدم)."""
    key = _api_key(pid)
    row = get_provider(pid)
    models = db.q("SELECT model_id FROM ai_models WHERE provider_id=%s ORDER BY model_id LIMIT 1", (pid,))
    mdl = models[0]["model_id"] if models else None
    payload = {"messages": [{"role": "user", "content": "رد بكلمة واحدة: تم"}], "max_tokens": 8}
    if mdl:
        payload["model"] = mdl
    status, body = _http_json("POST", f"{row['base_url']}/chat/completions", key, payload, timeout=45)
    ok = status == 200 and isinstance(body, dict)
    msg = ("✅ المزود يرد." if ok else f"❌ HTTP {status}: {str(body)[:200]}")
    _mark_check(pid, ok, msg)
    return ok, msg, mdl or "default"


# ------------------------------------------------------------------ embeddings
def embed(text: str) -> Optional[List[float]]:
    """تضمين نص لمتجه بحث — عبر أول مزود يوفّر /embeddings، وإلا None بصدق."""
    candidates = db.q("""SELECT p.id, p.base_url, m.model_id
                         FROM ai_providers p JOIN ai_models m ON m.provider_id = p.id
                         WHERE p.active AND m.model_id ILIKE '%embed%'
                         ORDER BY p.id LIMIT 3""")
    for p in candidates:
        key = _api_key(p["id"])
        status, body = _http_json("POST", f"{p['base_url']}/embeddings", key,
                                  {"input": [text], "model": p["model_id"]}, timeout=45)
        if status == 200 and isinstance(body, dict):
            data = body.get("data") or []
            if data and data[0].get("embedding"):
                return data[0]["embedding"]
    return None
