# -*- coding: utf-8 -*-
"""النوتبوك الذكية — واجهة الويب (Flask) + واجهة برمجية للالتقاط من أي مكان.

تشغيل:
    python -m notebook.app                 # أو: python notebook/app.py
    python -m notebook.app --port 8100

المزايا: التقاط ذكي، تصنيف تلقائي، فتح تصنيفات، تذكيرات، متابعة، أفكار برامج.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from notebook import brain, store  # type: ignore
else:
    from . import brain, store

from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _capture(text: str, source: str = "ui") -> Dict[str, Any]:
    analysis = brain.analyze(text, source=source)
    if not analysis.get("ok"):
        return {"ok": False, "error": analysis.get("error") or "نص غير صالح"}
    note_id = store.add_note(analysis)
    note = store.get_note(note_id) or {}
    return {
        "ok": True,
        "id": note_id,
        "note": note,
        "analysis": analysis,
        "message": brain.confirm_message(analysis, note_id),
    }


# --------------------------------------------------------------------- pages
@app.route("/")
def index():
    stats = store.stats()
    kind = request.args.get("kind") or None
    status = request.args.get("status") or "open"
    category = request.args.get("category") or None
    q = request.args.get("q") or None

    notes = store.list_notes(status=status if status != "all" else None, kind=kind, category=category, q=q)
    due = store.due_now()
    late = store.overdue()
    need_help = [n for n in store.list_notes(status="open") if n.get("needs_clarification")]
    return render_template(
        "index.html",
        stats=stats,
        notes=notes,
        due=due,
        late=late,
        need_help=need_help,
        categories=store.list_categories(),
        events=store.recent_events(12),
        filters={"kind": kind or "", "status": status, "category": category or "", "q": q or ""},
        kind_labels=brain.KIND_LABELS,
        priority_labels=brain.PRIORITY_LABELS,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/capture", methods=["POST"])
def capture_form():
    text = request.form.get("text") or ""
    result = _capture(text, source=request.form.get("source") or "ui")
    return redirect(url_for("index", ok="1" if result.get("ok") else "0", nid=result.get("id") or ""))


@app.route("/done/<int:note_id>", methods=["POST", "GET"])
def done(note_id: int):
    store.set_status(note_id, "done")
    return redirect(request.referrer or url_for("index"))


@app.route("/reopen/<int:note_id>", methods=["POST", "GET"])
def reopen(note_id: int):
    store.set_status(note_id, "open")
    return redirect(request.referrer or url_for("index"))


@app.route("/archive/<int:note_id>", methods=["POST", "GET"])
def archive(note_id: int):
    store.set_status(note_id, "archived")
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:note_id>", methods=["POST"])
def delete(note_id: int):
    store.delete_note(note_id)
    return redirect(request.referrer or url_for("index"))


@app.route("/snooze/<int:note_id>", methods=["POST", "GET"])
def snooze(note_id: int):
    minutes = int(request.args.get("minutes") or 60)
    note = store.get_note(note_id) or {}
    base = note.get("remind_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        when = datetime.strptime(base, "%Y-%m-%d %H:%M") + timedelta(minutes=minutes)
    except ValueError:
        when = datetime.now() + timedelta(minutes=minutes)
    store.update_note(note_id, remind_at=when.strftime("%Y-%m-%d %H:%M"))
    store.log_event(note_id, "snooze", f"+{minutes}m")
    return redirect(request.referrer or url_for("index"))


@app.route("/categorize/<int:note_id>", methods=["POST"])
def categorize(note_id: int):
    name = (request.form.get("category") or "").strip()
    if name:
        store.set_category(note_id, name)
    return redirect(request.referrer or url_for("index"))


@app.route("/setwhen/<int:note_id>", methods=["POST"])
def setwhen(note_id: int):
    raw = (request.form.get("when") or "").strip()
    parsed = brain.parse_when(raw)
    store.update_note(note_id, due_at=parsed.get("due_at"), remind_at=parsed.get("remind_at"),
                      remind_every=parsed.get("remind_every") or "none",
                      needs_clarification=0, question=None)
    store.log_event(note_id, "reschedule", raw)
    return redirect(request.referrer or url_for("index"))


# --------------------------------------------------------------------- API
@app.route("/api/capture", methods=["POST"])
def api_capture():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or request.form.get("text") or ""
    source = data.get("source") or "api"
    result = _capture(text, source=source)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/notes")
def api_notes():
    return jsonify(store.list_notes(
        status=request.args.get("status"),
        kind=request.args.get("kind"),
        category=request.args.get("category"),
        q=request.args.get("q"),
        limit=int(request.args.get("limit") or 200),
    ))


@app.route("/api/stats")
def api_stats():
    return jsonify(store.stats())


@app.route("/api/categories", methods=["GET", "POST"])
def api_categories():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or request.form.get("name") or "").strip()
        if not name:
            return jsonify({"ok": False, "error": "الاسم مطلوب"}), 400
        return jsonify({"ok": True, "category": store.add_category(
            name, data.get("emoji") or "📁", data.get("color") or "#64748b")})
    return jsonify(store.list_categories())


@app.route("/api/due")
def api_due():
    return jsonify({"due": store.due_now(), "overdue": store.overdue(),
                    "generated_at": datetime.now().isoformat(sep=" ")})


@app.route("/api/note/<int:note_id>", methods=["GET", "PATCH"])
def api_note(note_id: int):
    if request.method == "PATCH":
        data = request.get_json(silent=True) or {}
        if data.get("category"):
            store.set_category(note_id, data["category"])
        fields = {k: v for k, v in data.items() if k in
                  ("title", "body", "kind", "priority", "status", "due_at", "remind_at", "remind_every", "tags")}
        if fields:
            store.update_note(note_id, **fields)
    note = store.get_note(note_id)
    return (jsonify(note), 200) if note else (jsonify({"ok": False, "error": "مش موجود"}), 404)


@app.route("/health")
def health():
    return jsonify({"ok": True, "db": str(store.DB_PATH), "time": datetime.now().isoformat(sep=" "),
                    "stats": store.stats()})


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="النوتبوك الذكية — واجهة الويب")
    ap.add_argument("--host", default=os.environ.get("NOTEBOOK_HOST") or "0.0.0.0")
    ap.add_argument("--port", type=int, default=int(os.environ.get("NOTEBOOK_PORT") or 8100))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    store.init_db()
    print(f"💡 النوتبوك الذكية شغّالة: http://127.0.0.1:{args.port}  |  من الموبايل: http://{_local_ip()}:{args.port}")
    print(f"   قاعدة البيانات: {store.DB_PATH}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())