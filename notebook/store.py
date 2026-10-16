# -*- coding: utf-8 -*-
"""النوتبوك الذكية — طبقة التخزين (SQLite محلي فقط).

- قاعدة البيانات منفصلة تمامًا عن قاعدة البرنامج (pos_data.db) — لا كتابة على البرنامج أبدًا.
- المسار: notebook/data/notebook.db (ومستبعدة من Git عبر *.db في .gitignore).
- كل الدوال آمنة (تُنشئ المخطط عند أول استخدام).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("NOTEBOOK_DB") or (ROOT / "notebook" / "data" / "notebook.db"))

DEFAULT_CATEGORIES = [
    ("شغل", "📌", "#2563eb"),
    ("طباعة", "🖨️", "#0891b2"),
    ("ليزر", "🔥", "#ea580c"),
    ("خامات", "🪵", "#a16207"),
    ("عملاء", "👥", "#7c3aed"),
    ("حسابات", "💰", "#16a34a"),
    ("تصميم", "🎨", "#db2777"),
    ("مشتريات", "🛒", "#0d9488"),
    ("صيانة", "🛠️", "#64748b"),
    ("برامج", "💻", "#4f46e5"),
    ("أفكار برامج", "💡", "#f59e0b"),
    ("شخصي", "🏠", "#9333ea"),
    ("غير مصنف", "❔", "#94a3b8"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    emoji TEXT DEFAULT '📁',
    color TEXT DEFAULT '#64748b',
    auto INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL DEFAULT 'note',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    category_id INTEGER,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'open',
    due_at TEXT,
    remind_at TEXT,
    remind_every TEXT DEFAULT 'none',
    source TEXT DEFAULT 'ui',
    tags TEXT DEFAULT '',
    confidence REAL DEFAULT 0.0,
    needs_clarification INTEGER DEFAULT 0,
    question TEXT,
    meta TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    done_at TEXT,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER,
    at TEXT NOT NULL,
    type TEXT NOT NULL,
    detail TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);
CREATE INDEX IF NOT EXISTS idx_notes_kind ON notes(kind);
CREATE INDEX IF NOT EXISTS idx_notes_due ON notes(due_at);
CREATE INDEX IF NOT EXISTS idx_notes_remind ON notes(remind_at);
"""


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.executescript(SCHEMA)
        stamp = now_iso()
        for name, emoji, color in DEFAULT_CATEGORIES:
            conn.execute(
                "INSERT OR IGNORE INTO categories(name, emoji, color, auto, created_at) VALUES (?,?,?,0,?)",
                (name, emoji, color, stamp),
            )
        conn.commit()
    finally:
        if own:
            conn.close()


# ------------------------------------------------------------------ categories
def list_categories(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        init_db(conn)
        rows = conn.execute(
            """SELECT c.*, (SELECT COUNT(*) FROM notes n
                            WHERE n.category_id = c.id AND n.status != 'archived') AS count
               FROM categories c ORDER BY c.name"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


def get_category_by_name(name: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def add_category(name: str, emoji: str = "📁", color: str = "#64748b",
                 auto: bool = False, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO categories(name, emoji, color, auto, created_at) VALUES (?,?,?,?,?)",
            (name.strip(), emoji, color, 1 if auto else 0, now_iso()),
        )
        conn.commit()
        return get_category_by_name(name.strip(), conn) or {}
    finally:
        if own:
            conn.close()


def _norm_name(s: str) -> str:
    """تطبيع خفيف لأسماء التصنيفات — «شخصية» و«شخصيه» و«شخصي» تصير واحدة.

    توحّد الهمزات والنهايات، وتُحذف التاء المربوطة/الهاء من آخر الاسم —
    يمنع تكرار التصنيفات بسبب اختلاف الرسم فقط.
    """
    s = (s or "").strip()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"),
                 ("ؤ", "و"), ("ئ", "ي")):
        s = s.replace(a, b)
    s = s.strip()
    if s.endswith("ه"):
        s = s[:-1]
    return s.strip().lower()


def ensure_category(name: str, conn: Optional[sqlite3.Connection] = None,
                    palette: Optional[List[str]] = None) -> Dict[str, Any]:
    """يُرجع التصنيف، ويُنشئه تلقائيًا لو مش موجود (فتح تصنيفات تلقائيًا).

    مطابقة متسامحة: «شخصية» و«شخصيه» و«شخصيه» = نفس التصنيف — لا تكرار أبدًا.
    """
    name = (name or "").strip()
    own = conn is None
    conn = conn or connect()
    try:
        init_db(conn)
        target = _norm_name(name)
        for row in conn.execute("SELECT * FROM categories").fetchall():
            if _norm_name(row["name"]) == target:
                return dict(row)
        palette = palette or ["#4f46e5", "#0891b2", "#db2777", "#16a34a", "#ea580c", "#7c3aed", "#0d9488"]
        count = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        return add_category(name, "🗂️", palette[count % len(palette)], auto=True, conn=conn)
    finally:
        if own:
            conn.close()


# ------------------------------------------------------------------ notes
ALLOWED_KINDS = ("note", "task", "idea", "reminder", "program_idea")
ALLOWED_PRIORITIES = ("low", "normal", "high", "urgent")


def add_note(data: Dict[str, Any], conn: Optional[sqlite3.Connection] = None) -> int:
    own = conn is None
    conn = conn or connect()
    try:
        init_db(conn)
        stamp = now_iso()
        cat_name = (data.get("category") or "غير مصنف").strip()
        cat = ensure_category(cat_name, conn) if cat_name else ensure_category("غير مصنف", conn)
        cur = conn.execute(
            """INSERT INTO notes(kind, title, body, category_id, priority, status, due_at, remind_at,
                                 remind_every, source, tags, confidence, needs_clarification, question,
                                 meta, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("kind") if data.get("kind") in ALLOWED_KINDS else "note",
                (data.get("title") or "")[:300],
                data.get("body") or "",
                cat.get("id"),
                data.get("priority") if data.get("priority") in ALLOWED_PRIORITIES else "normal",
                data.get("status") or "open",
                data.get("due_at"),
                data.get("remind_at"),
                data.get("remind_every") or "none",
                data.get("source") or "ui",
                data.get("tags") or "",
                float(data.get("confidence") or 0.0),
                1 if data.get("needs_clarification") else 0,
                data.get("question"),
                data.get("meta") or "{}",
                stamp, stamp,
            ),
        )
        note_id = int(cur.lastrowid)
        conn.execute("INSERT INTO events(note_id, at, type, detail) VALUES (?,?,?,?)",
                     (note_id, stamp, "created", f"kind={data.get('kind')} source={data.get('source') or 'ui'}"))
        conn.commit()
        return note_id
    finally:
        if own:
            conn.close()


def get_note(note_id: int, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            """SELECT n.*, c.name AS category, c.emoji AS category_emoji, c.color AS category_color
               FROM notes n LEFT JOIN categories c ON c.id = n.category_id WHERE n.id = ?""",
            (note_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own:
            conn.close()


def list_notes(status: Optional[str] = None, kind: Optional[str] = None,
               category: Optional[str] = None, q: Optional[str] = None,
               limit: int = 500, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        init_db(conn)
        sql = """SELECT n.*, c.name AS category, c.emoji AS category_emoji, c.color AS category_color
                 FROM notes n LEFT JOIN categories c ON c.id = n.category_id WHERE 1=1"""
        params: List[Any] = []
        if status:
            sql += " AND n.status = ?"
            params.append(status)
        if kind:
            sql += " AND n.kind = ?"
            params.append(kind)
        if category:
            sql += " AND c.name = ?"
            params.append(category)
        if q:
            sql += " AND (n.title LIKE ? OR n.body LIKE ? OR n.tags LIKE ?)"
            like = f"%{q}%"
            params += [like, like, like]
        sql += " ORDER BY (n.status='done') ASC, COALESCE(n.due_at, n.created_at) ASC, n.id DESC LIMIT ?"
        params.append(int(limit))
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        if own:
            conn.close()


def update_note(note_id: int, conn: Optional[sqlite3.Connection] = None, **fields: Any) -> bool:
    allowed = {"title", "body", "kind", "priority", "status", "due_at", "remind_at",
               "remind_every", "tags", "needs_clarification", "question", "meta", "category_id"}
    sets, params = [], []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            params.append(value)
    if not sets:
        return False
    own = conn is None
    conn = conn or connect()
    try:
        sets.append("updated_at = ?")
        params.append(now_iso())
        params.append(note_id)
        cur = conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        if own:
            conn.close()


def set_status(note_id: int, status: str, conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    conn = conn or connect()
    try:
        stamp = now_iso()
        done = stamp if status == "done" else None
        cur = conn.execute("UPDATE notes SET status=?, done_at=?, updated_at=? WHERE id=?",
                           (status, done, stamp, note_id))
        conn.execute("INSERT INTO events(note_id, at, type, detail) VALUES (?,?,?,?)",
                     (note_id, stamp, "status", status))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if own:
            conn.close()


def delete_note(note_id: int, conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    conn = conn or connect()
    try:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if own:
            conn.close()


def set_category(note_id: int, category_name: str, conn: Optional[sqlite3.Connection] = None) -> bool:
    own = conn is None
    conn = conn or connect()
    try:
        cat = ensure_category(category_name, conn)
        cur = conn.execute("UPDATE notes SET category_id=?, needs_clarification=0, question=NULL, updated_at=? WHERE id=?",
                           (cat.get("id"), now_iso(), note_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        if own:
            conn.close()


# ------------------------------------------------------------------ views
def due_now(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            """SELECT n.*, c.name AS category, c.emoji AS category_emoji, c.color AS category_color
               FROM notes n LEFT JOIN categories c ON c.id = n.category_id
               WHERE n.status = 'open' AND n.remind_at IS NOT NULL AND n.remind_at <= ?
               ORDER BY n.remind_at ASC""",
            (now_iso(),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


def overdue(conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            """SELECT n.*, c.name AS category, c.emoji AS category_emoji, c.color AS category_color
               FROM notes n LEFT JOIN categories c ON c.id = n.category_id
               WHERE n.status = 'open' AND n.due_at IS NOT NULL AND n.due_at < ?
               ORDER BY n.due_at ASC""",
            (now_iso(),),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()


def stats(conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        init_db(conn)
        def one(sql: str, *params: Any) -> int:
            return int(conn.execute(sql, params).fetchone()[0] or 0)
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            "open": one("SELECT COUNT(*) FROM notes WHERE status='open'"),
            "done": one("SELECT COUNT(*) FROM notes WHERE status='done'"),
            "tasks": one("SELECT COUNT(*) FROM notes WHERE status='open' AND kind='task'"),
            "ideas": one("SELECT COUNT(*) FROM notes WHERE kind IN ('idea','program_idea')"),
            "overdue": one("SELECT COUNT(*) FROM notes WHERE status='open' AND due_at IS NOT NULL AND due_at < ?", now_iso()),
            "due_today": one("SELECT COUNT(*) FROM notes WHERE status='open' AND due_at IS NOT NULL AND substr(due_at,1,10)=?", today),
            "need_help": one("SELECT COUNT(*) FROM notes WHERE status='open' AND needs_clarification=1"),
            "categories": one("SELECT COUNT(*) FROM categories"),
        }
    finally:
        if own:
            conn.close()


def log_event(note_id: Optional[int], type_: str, detail: str = "",
              conn: Optional[sqlite3.Connection] = None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        conn.execute("INSERT INTO events(note_id, at, type, detail) VALUES (?,?,?,?)",
                     (note_id, now_iso(), type_, detail))
        conn.commit()
    finally:
        if own:
            conn.close()


def recent_events(limit: int = 30, conn: Optional[sqlite3.Connection] = None) -> List[Dict[str, Any]]:
    own = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own:
            conn.close()