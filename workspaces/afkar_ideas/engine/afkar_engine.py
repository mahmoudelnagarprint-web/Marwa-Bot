# -*- coding: utf-8 -*-
"""أداة أفكار: ملاحظات ومسودات وأفكار المنتجات داخل workspaces/afkar_ideas.
مشتق من nb/db.py بنيةً وضماناً — مخزن واحد بصيغة JSON موثقة في active_workspaces،
مع ملف حالة خام بجانب المخزن لضمان الاستمرار في غياب محرك (الخدمة تتحقق من سلامته كل نبضة).

المبادئ (موروثة من db.py):
  * لا أسرار في الكود — لا اتصال خارجي هنا إطلاقاً (كل التخزين ملف محلي في حيازة الورشة).
  * كتابة ذرّية: كتابة مؤقت + استبدال — لا ملف نصف مكتوب أبداً.
  * الصف المحذوف يبقى قابلاً للاسترجاع (status='trashed') ولا يُمحى من المخزن.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# الجذر: workspaces/afkar_ideas — نفس عرف router_daemon (WORKSPACE = جذر المشروع)
AFKAR_ROOT = Path(__file__).resolve().parent.parent          # workspaces/afkar_ideas
WORKSPACE = AFKAR_ROOT.parent.parent                          # جذر المشروع (للسجلات)
ROOT = AFKAR_ROOT
STORE = ROOT / "active_workspaces" / "notes.json"
STATE = ROOT / "active_workspaces" / "notebook_state.json"
ARCHIVE_DIR = ROOT / "archive"

# التصنيفات الثلاثة المطلوبة في أوامر المالك (رادار المواسم ومخزن البرومبتات)
CATEGORIES: List[str] = [
    "فكرة منتج",
    "برومبت تصميم",
    "تجهيزات مواسم",
    "ملاحظة",
    "مسودة",
]

# مواسم الورشة — رادار المواسم يحسب منها (نفس أعراس/العيدية الموسمية المعروفة)
SEASONS: List[Dict[str, str]] = [
    {"name": "موسم الأعراس", "key": "zafaf", "months": "3,4,5"},
    {"name": "موسم عيد الفطر", "key": "eid_fitr", "months": "3"},
    {"name": "موسم عيد الأضحى", "key": "eid_adha", "months": "5,6"},
    {"name": "موسم الدراسة", "key": "school", "months": "9"},
    {"name": "موسم رمضان", "key": "ramadan", "months": "2"},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure() -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def read() -> Dict[str, Any]:
    """قراءة المخزن — أي تلف يعيد قائمة فارغة ويُسجَّل في ملف الحالة (لا كذبة بيانات)."""
    _ensure()
    if not STORE.exists():
        return {"notes": [], "seq": 0}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("notes"), list):
            raise ValueError("بنية غير صالحة")
        return data
    except Exception:
        # نسخة احتياطية من الملف المعطوب قبل إعادة البدء
        bad = STORE.with_suffix(".json.bad")
        try:
            STORE.replace(bad)
        except OSError:
            pass
        _log_state({"error": "مخزن أفكار تالف — أُعيد للمخزن الفارغ", "kept": str(bad)})
        return {"notes": [], "seq": 0}


def write(data: Dict[str, Any]) -> None:
    """كتابة ذرّية — مؤقت في نفس المجلد ثم استبدال."""
    _ensure()
    fd, tmp = tempfile.mkstemp(dir=str(STORE.parent), prefix=".notes-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STORE)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _log_state(rec: Dict[str, Any]) -> None:
    """ملف حالة خام بجانب المخزن — الخدمة تقرأه كل نبضة للتحقق من السلامة."""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    rec = {**rec, "at": now_iso()}
    try:
        STATE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def new_id(data: Dict[str, Any]) -> int:
    seq = int(data.get("seq") or 0) + 1
    data["seq"] = seq
    return seq


def add(title: str, body: str = "", category: str = "ملاحظة",
        tags: Optional[List[str]] = None, project: Optional[str] = None) -> Dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise ValueError("لا عنوان للفكرة")
    cat = category if category in CATEGORIES else "ملاحظة"
    data = read()
    nid = new_id(data)
    note = {
        "id": nid,
        "title": title,
        "body": (body or "").strip(),
        "category": cat,
        "tags": [t for t in (tags or []) if t],
        "project": (project or "").strip() or None,
        "status": "open",  # open | done | trashed
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "spawned": [],
    }
    data["notes"].append(note)
    write(data)
    _log_state({"action": "add", "id": nid, "category": cat})
    return note


def update(nid: int, **fields: Any) -> Optional[Dict[str, Any]]:
    data = read()
    for n in data["notes"]:
        if n.get("id") == nid:
            for k, v in fields.items():
                if k in ("title", "body", "category", "tags", "project", "status", "spawned"):
                    if k == "category" and v not in CATEGORIES:
                        continue
                    n[k] = v
            n["updated_at"] = now_iso()
            write(data)
            _log_state({"action": "update", "id": nid, "fields": sorted(fields)})
            return n
    return None


def remove(nid: int) -> bool:
    """حذف ناعم: ينقل إلى trashed ويبقى قابلاً للاسترجاع من الأرشيف."""
    n = update(nid, status="trashed")
    if n is None:
        return False
    _log_state({"action": "trash", "id": nid})
    return True


def restore(nid: int) -> bool:
    return update(nid, status="open") is not None


def purge(nid: int) -> bool:
    """حذف نهائي — يُرشف نسخة في archive/ قبل المحو (لا مفقود)."""
    data = read()
    kept = []
    target = None
    for n in data["notes"]:
        if n.get("id") == nid:
            target = n
        else:
            kept.append(n)
    if target is None:
        return False
    try:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = now_iso().replace(":", "").replace("-", "")[:14]
        (ARCHIVE_DIR / f"note-{nid}-{stamp}.json").write_text(
            json.dumps(target, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError:
        pass
    data["notes"] = kept
    write(data)
    _log_state({"action": "purge", "id": nid})
    return True


def spawn_record(nid: int, commands: List[str]) -> Optional[Dict[str, Any]]:
    """تسجيل أوامر تحويل الفكرة لمشروع على الملاحظة (أثر التنفيذ)."""
    data = read()
    for n in data["notes"]:
        if n.get("id") == nid:
            n.setdefault("spawned", []).append({"at": now_iso(), "commands": commands})
            n["updated_at"] = now_iso()
            write(data)
            return n
    return None


def list_open() -> List[Dict[str, Any]]:
    data = read()
    return [n for n in data["notes"] if n.get("status") == "open"]


def list_trashed() -> List[Dict[str, Any]]:
    data = read()
    return [n for n in data["notes"] if n.get("status") == "trashed"]


def by_category() -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORIES}
    for n in list_open():
        out.setdefault(n.get("category") or "ملاحظة", []).append(n)
    return out


def season_radar() -> List[Dict[str, Any]]:
    """رادار المواسم: أفكار «تجهيزات مواسم» المفتوحة مصنفة على الموسم القادم."""
    now = datetime.now(timezone.utc)
    month = now.month
    upcoming = []
    for s in SEASONS:
        months = [int(m) for m in s["months"].split(",") if m.strip()]
        delta = min((m - month) % 12 for m in months) if months else 99
        upcoming.append({**s, "months": months, "starts_in_months": delta})
    upcoming.sort(key=lambda x: x["starts_in_months"])
    ideas = [n for n in list_open() if n.get("category") == "تجهيزات مواسم"]
    return [
        {
            "name": s["name"],
            "starts_in_months": s["starts_in_months"],
            "ideas": [
                {"id": n["id"], "title": n["title"], "tags": n.get("tags") or []}
                for n in ideas
                if _season_match(n, s)
            ],
        }
        for s in upcoming[:3]
    ]


def _season_match(note: Dict[str, Any], season: Dict[str, Any]) -> bool:
    text = f"{note.get('title', '')} {' '.join(note.get('tags') or [])}"
    key = season["key"]
    words = {
        "zafaf": ["عرس", "فرح", "زفاف", "تجهيز"],
        "eid_fitr": ["فطر", "عيد"],
        "eid_adha": ["أضحى", "أضاحي", "عيد"],
        "school": ["دراسة", "مدرسة", "لانش", "شنطة"],
        "ramadan": ["رمضان", "فانوس", "مسلسل"],
    }.get(key, [])
    return any(w in text for w in words) or not words


def stats() -> Dict[str, int]:
    open_notes = list_open()
    return {
        "open": len(open_notes),
        "done": sum(1 for n in read()["notes"] if n.get("status") == "done"),
        "trashed": len(list_trashed()),
        "products": sum(1 for n in open_notes if n.get("category") == "فكرة منتج"),
        "prompts": sum(1 for n in open_notes if n.get("category") == "برومبت تصميم"),
        "seasons": sum(1 for n in open_notes if n.get("category") == "تجهيزات مواسم"),
    }


# ------------------------------------------------------------------ CLI (لخدمة الويب)
# بوابة واحدة: python afkar_engine.py dashboard|mutate '<json>'|spawn <id> '<json>'
# لا يستورد Next.js ولا Flask — المحرك نقي تماماً ويُختبر وحده.
def _emit(obj: Dict[str, Any]) -> None:
    import sys as _s
    _s.stdout.write(json.dumps(obj, ensure_ascii=False))
    _s.stdout.flush()


def _payload(args: List[str]) -> None:
    raw = " ".join(args)
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        _emit({"ok": False, "error": f"JSON غير صالح: {exc}"})
        return
    action = str(data.get("action") or "")
    try:
        if action == "add":
            n = add(str(data.get("title") or ""), str(data.get("body") or ""),
                    str(data.get("category") or "ملاحظة"), data.get("tags") or [],
                    data.get("project"))
            _emit({"ok": True, "note": n})
        elif action == "update":
            n = update(int(data["id"]), **{k: v for k, v in data.items() if k != "action" and k != "id"})
            _emit({"ok": bool(n), "note": n})
        elif action == "done":
            n = update(int(data["id"]), status="done")
            _emit({"ok": bool(n), "note": n})
        elif action == "trash":
            _emit({"ok": remove(int(data["id"]))})
        elif action == "restore":
            _emit({"ok": restore(int(data["id"]))})
        elif action == "purge":
            _emit({"ok": purge(int(data["id"]))})
        elif action == "spawn":
            n = spawn_record(int(data["id"]), list(data.get("commands") or []))
            _emit({"ok": bool(n), "note": n})
        else:
            _emit({"ok": False, "error": f"إجراء غير معروف: {action or '(فارغ)'}"})
    except (KeyError, ValueError, TypeError) as exc:
        _emit({"ok": False, "error": str(exc)})


def _dashboard() -> None:
    _emit({
        "ok": True,
        "stats": stats(),
        "by_category": by_category(),
        "trashed": list_trashed(),
        "radar": season_radar(),
        "store": str(STORE),
        "state_file": str(STATE),
        "categories": CATEGORIES,
    })


def main(argv: List[str]) -> int:
    if not argv:
        _emit({"ok": False, "error": "لا أمر"})
        return 2
    cmd = argv[0]
    if cmd == "dashboard":
        _dashboard()
        return 0
    if cmd == "mutate":
        _payload(argv[1:])
        return 0
    if cmd == "spawn":
        try:
            _emit({"ok": bool(spawn_record(int(argv[1]), json.loads(argv[2] or "[]")))})
        except (IndexError, ValueError, json.JSONDecodeError) as exc:
            _emit({"ok": False, "error": str(exc)})
        return 0
    _emit({"ok": False, "error": f"أمر غير معروف: {cmd}"})
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
