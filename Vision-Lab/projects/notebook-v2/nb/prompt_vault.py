# -*- coding: utf-8 -*-
"""خزنة البرومبتات — R5 (Prompt Vault).

- حفظ/تصنيف/وسم برومبتاتك الممتازة.
- بحث دلالي pgvector (`embedding <=> query` cosine) عند توفر خدمة embeddings.
- بديل صادق: بحث كلمات ILIKE — البحث يعمل دائمًا حتى بدون متجهات.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import psycopg2.extras

from nb import db, providers


def _vec_param(vec: Optional[List[float]]) -> Optional[str]:
    if not vec:
        return None
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


def save_prompt(title: str, body: str, category: str = "عام",
                tags: Optional[List[str]] = None, source: str = "manual") -> int:
    if not (title or "").strip() or not (body or "").strip():
        raise ValueError("العنوان والنص مطلوبين")
    vec = None
    embed_model = None
    try:
        vec = providers.embed(f"{title}\n{body}")
        if vec:
            embed_model = "auto"
    except Exception:
        vec = None
    row = db.q(
        """INSERT INTO vault_prompts(title, body, category, tags, source, embedding, embed_model)
           VALUES (%s,%s,%s,%s,%s,%s::vector,%s) RETURNING id""",
        (title.strip()[:200], body.strip(), (category or "عام").strip()[:60],
         tags or [], source, _vec_param(vec), embed_model), one=True)
    return row["id"]


def list_prompts(limit: int = 50, category: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = "SELECT id, title, body, category, tags, use_count, created_at FROM vault_prompts"
    params: List[Any] = []
    if category:
        sql += " WHERE category = %s"
        params.append(category)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(int(limit))
    return q_rows(sql, params)


def q_rows(sql: str, params: List[Any]) -> List[Dict[str, Any]]:
    return db.q(sql, params)


def get_prompt(pid: int) -> Optional[Dict[str, Any]]:
    return db.q("SELECT * FROM vault_prompts WHERE id = %s", (pid,), one=True)


def mark_used(pid: int) -> None:
    db.x("""UPDATE vault_prompts
            SET use_count = use_count + 1, last_used_at = now() WHERE id = %s""", (pid,))


def delete_prompt(pid: int) -> bool:
    return db.x("DELETE FROM vault_prompts WHERE id = %s", (pid,)) > 0


def search(query: str, k: int = 5) -> Dict[str, Any]:
    """بحث دلالي إن وُجدت embeddings — وإلا بحث كلمات. يرجع {mode, results}."""
    q = (query or "").strip()
    if not q:
        return {"mode": "empty", "results": []}

    vec = None
    try:
        vec = providers.embed(q)
    except Exception:
        vec = None

    if vec:
        rows = db.q(
            """SELECT id, title, body, category, tags, use_count,
                      1 - (embedding <=> %s::vector) AS score
               FROM vault_prompts
               WHERE embedding IS NOT NULL
               ORDER BY embedding <=> %s::vector
               LIMIT %s""",
            [_vec_param(vec), _vec_param(vec), int(k)])
        if rows:
            return {"mode": "semantic", "results": rows}
        # متجهات موجودة عندنا بس مفيش صف مضمّن؟ نكمل للبديل بصدق.

    like = f"%{q}%"
    rows = db.q(
        """SELECT id, title, body, category, tags, use_count, 0.0 AS score
           FROM vault_prompts
           WHERE title ILIKE %s OR body ILIKE %s OR %s = ANY(tags) OR category ILIKE %s
           ORDER BY use_count DESC, id DESC LIMIT %s""",
        [like, like, q, like, int(k)])
    return {"mode": "keyword", "results": rows}


def format_result(p: Dict[str, Any]) -> str:
    """عرض برومبت للبوت (مرقّم)."""
    tags = " ".join(f"#{t}" for t in (p.get("tags") or []))
    head = f"📜 #{p['id']} «{p['title']}» [{p.get('category') or 'عام'}]"
    if tags:
        head += f" {tags}"
    body = (p.get("body") or "").strip()
    if len(body) > 900:
        body = body[:900] + "…"
    return head + "\n\n" + body
