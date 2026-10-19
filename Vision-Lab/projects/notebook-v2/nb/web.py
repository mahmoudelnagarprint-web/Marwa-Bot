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

from nb import (ai_router, cache, config, db, ha, proactive, providers, prompt_vault,
                retail, workshop)

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


# ------------------------------------------------------------------ helpers
def _ok(**kw) -> Any:
    return jsonify({"ok": True, **kw})


def _bust() -> int:
    """يُلغي كاش اللوحة بعد أي كتابة من الويب.

    ليه محتاجينها هنا بالتحديد: `/` بقى مخدوم من `db.dashboard()` بعمر 45
    ثانية، والكتابات اللي بتعدّي من `db.x()` على طول (حذف/تصنيف/ميعاد)
    **مش** بتنادي `db._invalidate_dashboard()` — فبلا النداء ده، حذف نوتة
    من الويب يخلّي الصفحة تعرضها لحد 45 ثانية كإنها لسه موجودة.
    `cache.invalidate("dash:")` هي الواجهة المجمّدة في العقد (بادئة).
    """
    try:
        return cache.invalidate("dash:")
    except Exception as exc:                       # الكاش مايوقفش أي كتابة
        config.log(f"cache bust error: {type(exc).__name__}: {exc}")
        return 0


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
    """لوحة القيادة من **كاش واحد** بدل ~10 استعلامات لكل زيارة.

    قبل: `db.stats()` + 9 استعلامات منفصلة (كل واحد ~0.6s مصافحة TLS/صلاحيات
    على الـpooler) = **16.2 ثانية** على السيرفر الحيّ. بعد: `db.dashboard()`
    — رحلة واحدة، و**سخن 0.0ms**.

    التصفية (`kind`/`status`/`q`): مفتاح الكاش `dash:{ttl}` **بلا فلتر**،
    فالقائمة المفلترة بتتجاب باستعلام واحد بمفردها — عشان مينفعش نقدّم
    بيانات غير مفلترة كأنها مفلترة. باقي المفاتيح (الإحصاءات/المستحق/المتأخر/
    المشاريع/الحركات/الورشة/المحل) مش بتتأثر بالفلتر أصلًا.
    """
    dash = db.dashboard()
    stats = dash.get("stats") or {}
    kind = request.args.get("kind") or None
    status = request.args.get("status") or "open"
    q = request.args.get("q") or None
    if status == "all" and not kind and not q:
        # نفس استعلام اللوحة بالحرف (نفس الترتيب ونفس الحد) → بلا رحلة إضافية
        captures = dash.get("captures") or []
    else:
        captures = db.list_captures(status=status if status != "all" else None,
                                    kind=kind, search=q, limit=150)
    return render_template(
        "index.html",
        stats=stats, captures=captures,
        due=dash.get("due") or [], late=dash.get("late") or [],
        need_help=dash.get("need_help") or [],
        projects=dash.get("projects") or [], radar=dash.get("radar") or [],
        retail_digest=dash.get("retail_digest") or "🏪 اللقطة غير متاحة الآن.",
        agent_reports=dash.get("agent_reports") or [],
        events=dash.get("events") or [],
        filters={"kind": kind or "", "status": status, "q": q or ""},
        ws_stats=dash.get("ws_stats") or {},
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
    _bust()
    return redirect(request.referrer or url_for("index"))


@app.route("/snooze/<int:cid>", methods=["POST", "GET"])
def snooze(cid: int):
    minutes = int(request.args.get("minutes") or 60)
    db.snooze_capture(cid, minutes)
    return redirect(request.referrer or url_for("index"))


@app.route("/delete/<int:cid>", methods=["POST"])
def delete(cid: int):
    db.x("DELETE FROM captures WHERE id=%s", (cid,))
    _bust()
    return redirect(request.referrer or url_for("index"))


@app.route("/categorize/<int:cid>", methods=["POST"])
def categorize(cid: int):
    name = (request.form.get("category") or "").strip()
    if name:
        db.x("UPDATE captures SET category=%s, needs_clarification=FALSE, question=NULL, updated_at=now() WHERE id=%s",
             (name, cid))
        _bust()
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
    _bust()
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


# ------------------------------------------------------------------ chat + dashboard API
@app.route("/api/chat", methods=["GET", "POST"])
def api_chat():
    """نفس بوابة النوايا — من غير تليجرام.

    واجهة رقيقة على `bot.process_text`: **صفر منطق هنا** (لا حفظ ولا تفنيد
    نوايا)، عشان الويب والتليجرام والبريدج يعدّوا من نفس الشبكة بالحرف:
    «نفس الجملة تتحفظ من التليجرام وما تتحفظش من الويب» ممنوعة بالعقد.
    `process_text` **مابتبعتش حاجة لأي حد** — الإرسال مسؤولية اللي بينادي،
    وهنا محدش بينده تليجرام أصلًا.

    استيراد `bot` جوه الدالة مقصود: `bot` بيستورد شبكة كاملة (polling،
    squad، workshop) و`web` محتاجه في **راوت واحد** بس — الاستيراد الجوّاني
    بيخلّي بدء الويب ما يدفعش تمنه، وبيقطع أي احتمال لدورة استيراد لو
    حد ضاف `from nb import web` جوه `bot` بعدين.
    """
    from nb import bot

    data = request.get_json(silent=True) or {}
    if request.method == "POST":
        text = (data.get("text") or request.form.get("text") or "").strip()
    else:
        text = (request.args.get("text") or "").strip()
    if not text:
        return _err("ابعت نص في text", 400)

    # نفس هوية محادثة المالك → نفس الذاكرة ونفس سياق فوفا حرفيًا
    raw_chat = data.get("chat_id") if request.method == "POST" else request.args.get("chat_id")
    try:
        chat_id = (int(raw_chat) if raw_chat not in (None, "")
                   else int(config.OWNER_TELEGRAM_ID or 0))
    except (TypeError, ValueError):
        chat_id = int(config.OWNER_TELEGRAM_ID or 0)
    res = bot.process_text(text, chat_id=chat_id, source="web")
    return jsonify({**res, "ok": bool(res.get("ok")), "source": "web"})


@app.route("/api/dashboard")
def api_dashboard():
    """اللوحة كاملة JSON من كاش واحد — نفس مفاتيح `db.dashboard()`."""
    try:
        ttl = int(request.args.get("ttl") if request.args.get("ttl") is not None
                  else config.DASHBOARD_TTL_SECONDS)
    except (TypeError, ValueError):
        ttl = config.DASHBOARD_TTL_SECONDS
    try:
        return jsonify(db.dashboard(ttl=ttl))
    except Exception as exc:
        return _err(f"{type(exc).__name__}: {exc}", 500)


@app.route("/api/capture/<int:cid>/action", methods=["POST"])
def api_capture_action(cid: int):
    """أفعال النوتة من الويب/البريدج: done | snooze | category | delete.

    نفس الأفعال الموجودة كروت في `/done/<id>` … إلخ — بس بترجّع JSON بدل
    redirect عشان الـAJAX والـbridge يستخدموها. كلها بتعدّي على دوال `db`
    المجمّدة، وبعدها `_bust()` عشان اللوحة تعكس التغيير فورًا.
    """
    d = request.get_json(silent=True) or {}
    action = (d.get("action") or request.form.get("action") or "").strip().lower()
    value = d.get("value", request.form.get("value"))

    if action == "done":
        ok = db.set_capture_status(cid, "done")
    elif action == "reopen":
        ok = db.x("UPDATE captures SET status='open', updated_at=now() WHERE id=%s", (cid,)) > 0
    elif action == "snooze":
        try:
            minutes = int(value if value not in (None, "") else 60)
        except (TypeError, ValueError):
            return _err("value لازم يكون عدد دقايق", 400)
        ok = db.snooze_capture(cid, minutes)
    elif action == "category":
        name = (str(value) if value is not None else "").strip()
        if not name:
            return _err("value لازم يكون اسم التصنيف", 400)
        ok = db.x("""UPDATE captures SET category=%s, needs_clarification=FALSE,
                     question=NULL, updated_at=now() WHERE id=%s""", (name, cid)) > 0
    elif action == "delete":
        ok = db.x("DELETE FROM captures WHERE id=%s", (cid,)) > 0
    else:
        return _err("action لازم تكون واحدة من: done | reopen | snooze | category | delete", 400)

    _bust()
    return _ok(id=cid, action=action, changed=bool(ok),
               message="تم" if ok else "مفيش صف بالمعرف ده")


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
