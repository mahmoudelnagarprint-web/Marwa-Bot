# -*- coding: utf-8 -*-
"""واجهة الويب ومركز القيادة — R3 (Flask).

الصفحات: / لوحة القيادة • /providers مزودو الـAI • /workshop الورشة • /vault الخزنة.
كل الـAPIs استجابة JSON — مع توثيق الـRetail و outbox وـHA كاملة.
استقبال تقارير الوكلاء يتطلب X-NB2-Token (403 بدونه).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

import psycopg2.extras

from nb import ai_router, config, db, ha, proactive, providers, prompt_vault, retail, workshop

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ------------------------------------------------------------------ helpers
def _ok(**kw) -> Any:
    return jsonify({"ok": True, **kw})


def _err(msg: str, code: int = 400) -> Any:
    return jsonify({"ok": False, "error": msg}), code


def _token_ok() -> bool:
    return bool(config.NB2_INGEST_TOKEN and request.headers.get("X-NB2-Token") == config.NB2_INGEST_TOKEN)


@app.context_processor
def _inject_globals() -> Dict[str, Any]:
    try:
        st = ha.status()
        node = {"id": st["node_id"], "device": st["device_name"], "leader": st["i_am_leader"]}
    except Exception:
        node = {"id": config.NODE_ID, "device": config.DEVICE_NAME, "leader": False}
    return {
        "node_badge": f"{node['device']} ({node['id']}) — " + ("⚡ قائد" if node["leader"] else "🛡️ غطاء"),
        "kind_labels": ai_router.KIND_LABELS,
        "priority_labels": ai_router.PRIORITY_LABELS,
    }


# ------------------------------------------------------------------ pages
@app.route("/")
def index():
    stats = db.stats()
    kind = request.args.get("kind") or None
    status = request.args.get("status") or "open"
    q = request.args.get("q") or None
    captures = db.list_captures(status=status if status != "all" else None,
                                kind=kind, search=q, limit=150)
    due = db.due_reminders()
    late = db.overdue_captures()
    need_help = db.q("""SELECT * FROM captures
                        WHERE status='open' AND needs_clarification = TRUE
                        ORDER BY id DESC LIMIT 10""")
    projects = db.q("""SELECT *, (last_activity_at < now() - make_interval(days => stagnant_after_days)) AS stagnant
                       FROM projects WHERE status='active' ORDER BY stagnant DESC, id DESC LIMIT 10""")
    radar = [p for p in projects if p.get("stagnant")]
    try:
        retail_digest = retail.digest()
    except Exception:
        retail_digest = "🏪 اللقطة غير متاحة الآن."
    return render_template(
        "index.html",
        stats=stats, captures=captures, due=due, late=late, need_help=need_help,
        projects=projects, radar=radar, retail_digest=retail_digest,
        agent_reports=retail.latest_agent_reports(6),
        events=db.q("SELECT capture_id, at, type, detail FROM capture_events ORDER BY id DESC LIMIT 15"),
        filters={"kind": kind or "", "status": status, "q": q or ""},
        ws_stats=workshop.stats(),
        now=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
    )


@app.route("/providers")
def providers_page():
    return render_template("providers.html", presets=providers.presets())


@app.route("/workshop")
def workshop_page():
    return render_template("workshop.html",
                           status_labels=workshop.STATUS_LABELS,
                           machine_labels=workshop.MACHINE_LABELS)


@app.route("/vault")
def vault_page():
    return render_template("vault.html")


# ------------------------------------------------------------------ actions
@app.route("/done/<int:cid>", methods=["POST", "GET"])
def done(cid: int):
    db.set_capture_status(cid, "done")
    return redirect(request.referrer or url_for("index"))


@app.route("/reopen/<int:cid>", methods=["POST", "GET"])
def reopen(cid: int):
    db.x("UPDATE captures SET status='open', updated_at=now() WHERE id=%s", (cid,))
    return redirect(request.referrer or url_for("index"))


@app.route("/snooze/<int:cid>", methods=["POST", "GET"])
def snooze(cid: int):
    minutes = int(request.args.get("minutes") or 60)
    db.snooze_capture(cid, minutes)
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:cid>", methods=["POST"])
def delete(cid: int):
    db.x("DELETE FROM captures WHERE id=%s", (cid,))
    return redirect(request.referrer or url_for("index"))


@app.route("/categorize/<int:cid>", methods=["POST"])
def categorize(cid: int):
    name = (request.form.get("category") or "").strip()
    if name:
        db.x("UPDATE captures SET category=%s, needs_clarification=FALSE, question=NULL, updated_at=now() WHERE id=%s",
             (name, cid))
    return redirect(request.referrer or url_for("index"))


@app.route("/setwhen/<int:cid>", methods=["POST"])
def setwhen(cid: int):
    raw = (request.form.get("when") or "").strip()
    when = ai_router.parse_when(raw)
    db.x("""UPDATE captures
            SET due_at=%s, remind_at=%s, remind_every=%s,
                needs_clarification=FALSE, question=NULL, updated_at=now()
            WHERE id=%s""",
         (when.get("due_at"), when.get("remind_at"), when.get("remind_every") or "none", cid))
    return redirect(request.referrer or url_for("index"))


# ------------------------------------------------------------------ capture API
@app.route("/api/capture", methods=["POST"])
def api_capture():
    data = request.get_json(silent=True) or {}
    text = data.get("text") or request.form.get("text") or ""
    source = data.get("source") or "api"
    analysis = ai_router.route(text, source=source)
    if not analysis.get("ok"):
        return _err(analysis.get("error") or "نص غير صالح")
    cid = db.add_capture(analysis)
    return _ok(id=cid, note=analysis, message=ai_router.confirm_message(analysis, cid))


@app.route("/api/notes")
def api_notes():
    return jsonify(db.list_captures(
        status=request.args.get("status"),
        kind=request.args.get("kind"),
        search=request.args.get("q"),
        limit=int(request.args.get("limit") or 200),
    ))


@app.route("/api/due")
def api_due():
    return jsonify({"due": db.due_reminders(), "overdue": db.overdue_captures(),
                    "generated_at": datetime.now().isoformat(sep=" ")})


@app.route("/api/stats")
def api_stats():
    return jsonify(db.stats())


# ------------------------------------------------------------------ providers API
@app.route("/api/providers", methods=["GET", "POST"])
def api_providers():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        try:
            p = providers.add_provider(d.get("name"), d.get("base_url"), d.get("api_key"),
                                       d.get("kind") or "openai-compatible", d.get("notes") or "")
            return _ok(provider=p, message="اتسجل المزود — شغّل الاكتشاف لتحميل النماذج")
        except Exception as exc:
            return _err(f"{type(exc).__name__}: {exc}")
    return jsonify(providers.list_providers())


@app.route("/api/providers/presets")
def api_providers_presets():
    return jsonify(providers.presets())


@app.route("/api/providers/<int:pid>/models")
def api_provider_models(pid: int):
    return jsonify(providers.models_of(pid))


@app.route("/api/providers/<int:pid>/discover", methods=["POST"])
def api_provider_discover(pid: int):
    try:
        ids = providers.discover_models(pid)
        return _ok(models=ids, message=f"تم اكتشاف {len(ids)} نموذج")
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/providers/<int:pid>/test", methods=["POST"])
def api_provider_test(pid: int):
    try:
        ok, msg, model = providers.test_provider(pid)
        return {"ok": ok, "message": msg, "model": model}, (200 if ok else 400)
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/providers/<int:pid>/default", methods=["POST"])
def api_provider_default(pid: int):
    d = request.get_json(silent=True) or {}
    model = d.get("model_id") or ""
    try:
        providers.set_default(pid, model)
        return _ok(message=f"الافتراضي صار: {model} — يُطبَّق فورًا")
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/providers/<int:pid>", methods=["DELETE", "PATCH"])
def api_provider(pid: int):
    if request.method == "DELETE":
        providers.delete_provider(pid)
        return _ok(message="اتحذف المزود")
    d = request.get_json(silent=True) or {}
    try:
        providers.update_provider(pid, name=d.get("name"), base_url=d.get("base_url"),
                                  api_key=d.get("api_key"), active=d.get("active"),
                                  notes=d.get("notes"))
        return _ok(message="اتحدّث")
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


# ------------------------------------------------------------------ workshop API
@app.route("/api/workshop/stats")
def api_ws_stats():
    return jsonify(workshop.stats())


@app.route("/api/workshop/jobs", methods=["GET", "POST"])
def api_ws_jobs():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        try:
            jid = workshop.create_job(
                title=d.get("title"), customer=d.get("customer"), phone=d.get("phone"),
                description=d.get("description") or "", machine_type=d.get("machine_type") or "other",
                qty=float(d.get("qty") or 1), price=float(d.get("price") or 0),
                due_date=d.get("due_date"), priority=d.get("priority") or "normal", notes=d.get("notes") or "")
            return _ok(job=workshop.get_job(jid), message="اتسجلت الشغلانة")
        except Exception as exc:
            return _err(f"{type(exc).__name__}: {exc}")
    return jsonify(workshop.list_jobs(status=request.args.get("status"),
                                      limit=int(request.args.get("limit") or 60)))


@app.route("/api/workshop/jobs/<int:jid>", methods=["GET"])
def api_ws_job(jid: int):
    job = workshop.get_job(jid)
    if not job:
        return _err("شغلانة غير موجودة", 404)
    job["events"] = workshop.job_events(jid)
    return jsonify(job)


@app.route("/api/workshop/jobs/<int:jid>/advance", methods=["POST"])
def api_ws_job_advance(jid: int):
    d = request.get_json(silent=True) or {}
    try:
        job = workshop.advance_job(jid, d.get("status"), d.get("detail") or "")
        return _ok(job=job, message="اتحدثت الحالة")
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/workshop/jobs/<int:jid>/pay", methods=["POST"])
def api_ws_job_pay(jid: int):
    d = request.get_json(silent=True) or {}
    try:
        return _ok(job=workshop.pay_job(jid, float(d.get("amount") or 0)))
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/workshop/materials", methods=["GET", "POST"])
def api_ws_materials():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        try:
            mid = workshop.add_material(name=d.get("name"), kind=d.get("kind") or "other",
                                        unit=d.get("unit") or "قطعة", qty=float(d.get("qty") or 0),
                                        min_qty=float(d.get("min_qty") or 0),
                                        unit_cost=float(d.get("unit_cost") or 0),
                                        supplier=d.get("supplier") or "")
            return _ok(material=db.q("SELECT * FROM ws_materials WHERE id=%s", (mid,), one=True))
        except Exception as exc:
            return _err(f"{type(exc).__name__}: {exc}")
    return jsonify(workshop.list_materials(limit=int(request.args.get("limit") or 200)))


@app.route("/api/workshop/materials/<int:mid>/adjust", methods=["POST"])
def api_ws_material_adjust(mid: int):
    d = request.get_json(silent=True) or {}
    try:
        mat = workshop.adjust_material(mid, float(d.get("delta") or 0), d.get("reason") or "تعديل يدوي")
        return _ok(material=mat)
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/workshop/low")
def api_ws_low():
    return jsonify(workshop.low_stock())


@app.route("/api/workshop/customers")
def api_ws_customers():
    return jsonify(workshop.list_customers(limit=int(request.args.get("limit") or 100)))


# ------------------------------------------------------------------ vault API
@app.route("/api/vault", methods=["GET", "POST"])
def api_vault():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        try:
            pid = prompt_vault.save_prompt(title=d.get("title") or "", body=d.get("body") or "",
                                           category=d.get("category") or "عام",
                                           tags=d.get("tags") or [], source="web")
            return _ok(id=pid, message="اتحفظ البرومبت في الخزنة")
        except Exception as exc:
            return _err(f"{type(exc).__name__}: {exc}")
    q = (request.args.get("q") or "").strip()
    if q:
        return jsonify(prompt_vault.search(q, k=int(request.args.get("k") or 5)))
    return jsonify(prompt_vault.list_prompts(limit=int(request.args.get("limit") or 50)))


@app.route("/api/vault/<int:pid>", methods=["DELETE"])
def api_vault_delete(pid: int):
    prompt_vault.delete_prompt(pid)
    return _ok(message="اتحذف")


# ------------------------------------------------------------------ agents / retail / ha
def _require_agent_token():
    if not _token_ok():
        return _err("غير مصرح — X-NB2-Token مطلوب", 403)
    return None


@app.route("/api/agents/report", methods=["POST"])
def api_agent_report():
    blocked = _require_agent_token()
    if blocked:
        return blocked
    d = request.get_json(silent=True) or {}
    agent = d.get("agent") or ""
    title = d.get("title") or d.get("summary") or ""
    if not agent or not title:
        return _err("agent و title مطلوبان")
    row = retail.ingest_agent_report(
        agent=agent, title=title, body=d.get("body") or "",
        scope=d.get("scope") or "", severity=d.get("severity") or "info",
        payload=d.get("payload") or {}, source="api")
    return _ok(report=row, message="اتسجل التقرير" + (" — وخرط critical واتصدر للمالك" if d.get("severity") == "critical" else ""))


@app.route("/api/agents/reports")
def api_agent_reports():
    return jsonify(retail.latest_agent_reports(limit=int(request.args.get("limit") or 15)))


@app.route("/api/agents/ack/<int:rid>", methods=["POST"])
def api_agent_ack(rid: int):
    retail.ack_report(rid)
    return _ok(message="تأكيد الاطلاع")


@app.route("/api/retail/snapshot")
def api_retail_snapshot():
    return jsonify(retail.last_snapshot())


@app.route("/api/retail/pull", methods=["POST"])
def api_retail_pull():
    """سحب لقطة الآن من قاعدة POS على هذه العقدة (قراءة فقط)."""
    try:
        snap = retail.pull_pos_snapshot()
        return _ok(snapshot=snap)
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}")


@app.route("/api/projects", methods=["GET", "POST"])
def api_projects():
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        try:
            rid = db.q("""INSERT INTO projects(name, area, goal, notes, stagnant_after_days)
                          VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                       (d.get("name"), d.get("area") or "personal", d.get("goal"),
                        d.get("notes"), int(d.get("stagnant_after_days") or 7)), one=True)["id"]
            return _ok(id=rid, message="اتضاف المشروع")
        except Exception as exc:
            return _err(f"{type(exc).__name__}: {exc}")
    return jsonify(db.q("SELECT * FROM projects ORDER BY status='active' DESC, id DESC LIMIT 50"))


@app.route("/api/ha/status")
def api_ha_status():
    return jsonify(ha.status())


@app.route("/health")
def health():
    try:
        st = ha.status()
        return jsonify({"ok": True, "node": config.NODE_ID, "leader": st["i_am_leader"],
                        "db": "ok", "time": datetime.now().isoformat(sep=" "), "stats": db.stats()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), 500


def run(host: str = "0.0.0.0", port: int = 0, debug: bool = False) -> None:
    app.run(host=host, port=port or config.WEB_PORT, debug=debug, threaded=True)
