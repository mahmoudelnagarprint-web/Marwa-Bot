# -*- coding: utf-8 -*-
"""Marwa Core Workspace — DSH Plugin Data Bridge (JSON-lines over stdio).

يخدم نصف المضيف (index.js) داخل إضافة DSH:
  • notebook.list / notebook.add / notebook.pin  — عبر notebook.store الرسمي (v1 موحد)
  • catalog.rows   — قراءة exports/products_catalog_master.xlsx (openpyxl)
  • pos.stats      — قراءة فقط قاعدة البرنامج الحية (LIVE_DB_PATH من .env، وإلا المرآة)
  • vision.list / vision.file — معمل فيجن Vision-Lab + designs/ (قراءة فقط)
  • squad.prompts  — دفاتر تفعيل الشخصيات من مساراتها الأصلية
  • squad.context  — سياق حي لوكيل: الدستور + الهوية + دفاتر الحالة + المهام المفتوحة
لا تكتب أبداً في قاعدة البرنامج (pos_data.db) — قراءة فقط (ميثاق MARWA_CORE).
"""
import io
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def _detect_repo():
    """ترتيب الثقة: متغير البيئة من نصف المضيف ← جذر المستودع المعروف ← عقدة اللابتوب ← cwd.
    إصلاح «البيانات الوهمية»: الجسر القديم كان يسقط على G:\\Marwa-Bot (مسار اللابتوب غير الموجود
    على عقدة الورشة) فترجع كل المآخذ exists:false وتشبه البيانات الوهمية."""
    cands = []
    env = os.environ.get("MARWA_REPO_ROOT")
    if env:
        cands.append(Path(env))
    cands.append(Path(r"G:\ai\Naggar Print POS Agent"))
    cands.append(Path(r"G:\Marwa-Bot"))
    try:
        cands.append(Path.cwd())
    except OSError:
        pass
    for c in cands:
        try:
            if c and (c / "notebook" / "data" / "notebook.db").exists():
                return c
        except OSError:
            continue
    return cands[0] if cands else Path.cwd()


REPO = _detect_repo()
NOTEBOOK_DB = REPO / "notebook" / "data" / "notebook.db"
CATALOG = REPO / "exports" / "products_catalog_master.xlsx"


def _live_pos_db():
    """قاعدة البرنامج الحية — مصدر الحقيقة على عقدة WORKSHOP (LIVE_DB_PATH من .env).
    لا كتابة أبداً: الاتصال عبر mode=ro + query_only=ON (ميثاق MARWA_CORE)."""
    try:
        m = re.search(
            r'^\s*LIVE_DB_PATH\s*=\s*"?([^"\r\n]+)"?\s*$',
            (REPO / ".env").read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            p = Path(m.group(1).strip())
            if p.exists():
                return p
    except OSError:
        pass
    live = Path(r"G:\ai\Elnagar POS\pos_data.db")
    return live if live.exists() else REPO / "pos_data.db"


POS_DB = _live_pos_db()  # الاسم تاريخي — يقف الآن على القاعدة الحية إن توفرت وإلا المرآة
VISION_LAB = REPO / "Vision-Lab"
VISION_ROOTS = [
    REPO / "designs",
    VISION_LAB / "projects",
    VISION_LAB / "ai_templates",
    VISION_LAB / "studies",
]
IMG_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
           ".webp": "image/webp", ".svg": "image/svg+xml", ".gif": "image/gif"}

SQUAD_PROMPTS = {
    "marwa": REPO / "AGENT.md",
    "afkar": VISION_LAB / "projects" / "notebook-v2" / "NB2_CHAT_BOOTSTRAP_PROMPT.md",
    "hakim": REPO / "orchestrator" / "squad" / "hakim" / "CHAT_BOOTSTRAP_PROMPT.md",
    "rased": REPO / "orchestrator" / "squad" / "rased" / "CHAT_BOOTSTRAP_PROMPT.md",
    "bibo": REPO / "orchestrator" / "squad" / "bibo" / "CHAT_BOOTSTRAP_PROMPT.md",
    "fares": REPO / "orchestrator" / "squad" / "fares" / "CHAT_BOOTSTRAP_PROMPT.md",
    "koko": REPO / "orchestrator" / "squad" / "koko" / "CHAT_BOOTSTRAP_PROMPT.md",
    "salma": REPO / "orchestrator" / "squad" / "salma" / "CHAT_BOOTSTRAP_PROMPT.md",
    "sasa": REPO / "orchestrator" / "squad" / "sasa" / "CHAT_BOOTSTRAP_PROMPT.md",
    "vision": VISION_LAB / "SQUAD_BOOTSTRAP_PROMPT.md",
}

_catalog_cache = {"mtime": None, "payload": None}


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


# --------------------------------------------------------------- notebook
def notebook_list(params):
    limit = int(params.get("limit") or 120)
    if not NOTEBOOK_DB.exists():
        return {"notes": [], "db": str(NOTEBOOK_DB), "exists": False}
    conn = sqlite3.connect("file:{}/{}?mode=ro".format(
        NOTEBOOK_DB.drive.replace("\\", "/"), str(NOTEBOOK_DB)[3:].replace("\\", "/")), uri=True) \
        if False else sqlite3.connect(str(NOTEBOOK_DB))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT n.id, n.kind, n.title, n.body, n.priority, n.status, n.due_at, n.source,"
            " n.tags, n.created_at, n.updated_at, c.name AS category, c.emoji, c.color"
            " FROM notes n LEFT JOIN categories c ON c.id = n.category_id"
            " ORDER BY CASE n.status WHEN 'open' THEN 0 ELSE 1 END,"
            " CASE n.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,"
            " n.updated_at DESC LIMIT ?", (limit,))
        notes = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM notes WHERE status='open'")
        open_count = cur.fetchone()[0]
        return {"notes": notes, "openCount": open_count, "db": str(NOTEBOOK_DB), "exists": True,
                "mtime": _mtime(NOTEBOOK_DB)}
    finally:
        conn.close()


def notebook_add(params):
    sys.path.insert(0, str(REPO))
    from notebook import store  # noqa: E402  — القناة الرسمية (نفس جسر تليجرام)
    nid = store.add_note({
        "kind": params.get("kind") or "note",
        "title": (params.get("title") or "بدون عنوان")[:200],
        "body": params.get("body") or "",
        "category": params.get("category") or "غير مصنف",
        "priority": params.get("priority") or "normal",
        "status": "open",
        "source": params.get("source") or "marwa-core-ui",
        "tags": params.get("tags") or "marwa-core-ui",
        "due_at": params.get("due_at"),
        "meta": "{}",
    })
    return {"id": nid}


def notebook_pin(params):
    nid = int(params.get("id") or 0)
    pinned = 1 if params.get("pinned", True) else 0
    conn = sqlite3.connect(str(NOTEBOOK_DB))
    try:
        conn.execute(
            "UPDATE notes SET priority=?, updated_at=? WHERE id=?",
            ("high" if pinned else "normal",
             time.strftime("%Y-%m-%d %H:%M:%S"), nid))
        conn.commit()
        return {"id": nid, "priority": "high" if pinned else "normal"}
    finally:
        conn.close()


def notebook_pinned(params):
    """ملاحظات مثبتة للوكلاء (📌): أولوية عالية/عاجلة ومفتوحة — تُحقن في تهيئة جلسة كل وكيل."""
    conn = sqlite3.connect(str(NOTEBOOK_DB), timeout=6)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT n.id, n.kind, n.title, n.body, n.priority, n.tags, n.updated_at,"
            " c.name AS category FROM notes n"
            " LEFT JOIN categories c ON c.id = n.category_id"
            " WHERE n.status='open' AND n.priority IN ('high','urgent')"
            " ORDER BY (n.priority='urgent') DESC, n.updated_at DESC LIMIT ?",
            (int(params.get("limit") or 20),))
        notes = [dict(r) for r in cur.fetchall()]
        return {"notes": notes, "count": len(notes)}
    finally:
        conn.close()


# --------------------------------------------------------------- catalog
def catalog_rows(params):
    mtime = _mtime(CATALOG)
    if _catalog_cache["payload"] and _catalog_cache["mtime"] == mtime:
        return dict(_catalog_cache["payload"], cached=True)
    import openpyxl  # noqa: E402
    wb = openpyxl.load_workbook(str(CATALOG), read_only=True, data_only=True)
    try:
        sheet_name = wb.sheetnames[0]
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else str(v) for v in row])
            if len(rows) >= int(params.get("maxRows") or 400):
                break
    finally:
        wb.close()
    headers = rows[0] if rows else []
    payload = {"sheet": sheet_name, "headers": headers, "rows": rows[1:],
               "total": len(rows) - 1 if rows else 0,
               "mtime": mtime, "path": str(CATALOG)}
    _catalog_cache["mtime"] = mtime
    _catalog_cache["payload"] = payload
    return payload


# --------------------------------------------------------------- pos (قراءة فقط)
def _ro_conn():
    """اتصال قراءة فقط فعلي: mode=ro عبر URI + query_only=ON — يستحيل أي كتابة."""
    try:
        conn = sqlite3.connect(POS_DB.as_uri() + "?mode=ro", uri=True, timeout=6)
    except Exception:  # noqa: BLE001 — رجوع آمن للاتصال العادي مع query_only
        conn = sqlite3.connect(str(POS_DB), timeout=6)
    try:
        conn.execute("PRAGMA query_only=ON")
    except Exception:  # noqa: BLE001 — لا يكسر القراءة لو رُفض الـ PRAGMA
        pass
    return conn


def pos_stats(params):
    out = {"db": str(POS_DB), "exists": POS_DB.exists(), "mtime": _mtime(POS_DB), "cards": [], "tables": {}}
    if not POS_DB.exists():
        return out
    conn = _ro_conn()
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        def one(sql, args=()):
            try:
                cur.execute(sql, args)
                r = cur.fetchone()
                return dict(r) if r is not None else {}
            except Exception as exc:  # noqa: BLE001 — كارت فاشل لا يكسر الباقي
                return {"_error": str(exc)}

        out["cards"].append({"id": "clients", "label": "العملاء", **one("SELECT COUNT(*) AS n FROM clients")})
        out["cards"].append({"id": "products", "label": "المنتجات", **one("SELECT COUNT(*) AS n FROM products")})
        out["cards"].append({"id": "ordersOpen", "label": "طلبات مفتوحة",
                             **one("SELECT COUNT(*) AS n FROM orders WHERE status IN ('Under Preparation','Ready')")})
        out["cards"].append({"id": "ordersTotal", "label": "إجمالي الطلبات", **one("SELECT COUNT(*) AS n FROM orders")})
        out["cards"].append({"id": "tx", "label": "حركات مالية", **one("SELECT COUNT(*) AS n FROM transactions")})
        out["cards"].append({"id": "debt", "label": "أرصدة مدينة (مقارنة فقط)",
                             **one("SELECT COALESCE(SUM(balance),0) AS n FROM clients WHERE balance > 0")})
        out["cards"].append({"id": "shift", "label": "الشيفت المفتوح",
                             **one("SELECT opened_at AS n FROM daily_shifts ORDER BY id DESC LIMIT 1")})
        out["cards"].append({"id": "lastOrder", "label": "آخر طلب مسجل",
                             **one("SELECT MAX(date) AS n FROM orders")})
        rows = one("SELECT o.status AS status, COUNT(*) AS n FROM orders o GROUP BY o.status ORDER BY n DESC")
        if "status" in rows or isinstance(rows, list):
            pass
        try:
            cur.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status ORDER BY n DESC")
            out["tables"]["ordersByStatus"] = [dict(r) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            out["tables"]["ordersByStatus"] = [{"_error": str(exc)}]
        try:
            cur.execute(
                "SELECT p.name AS name, SUM(oi.qty) AS qty FROM order_items oi"
                " JOIN products p ON p.id = oi.product_id"
                " JOIN orders o ON o.id = oi.order_id"
                " WHERE o.status != 'Cancelled'"
                " GROUP BY p.name ORDER BY qty DESC LIMIT 8")
            out["tables"]["topProducts"] = [dict(r) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            out["tables"]["topProducts"] = [{"_error": str(exc)}]
        try:
            cur.execute("SELECT name, stock_qty FROM products WHERE stock_qty <= 3 ORDER BY stock_qty LIMIT 8")
            out["tables"]["lowStock"] = [dict(r) for r in cur.fetchall()]
        except Exception as exc:  # noqa: BLE001
            out["tables"]["lowStock"] = [{"_error": str(exc)}]
        return out
    finally:
        conn.close()


# --------------------------------------------------------------- vision
def _safe_children(root: Path):
    try:
        return list(root.iterdir())
    except OSError:
        return []


def vision_list(params):
    entries = []
    for root in VISION_ROOTS:
        if not root.exists():
            continue
        for child in _safe_children(root):
            if child.name.startswith(".") or child.name in ("node_modules", ".venv", "__pycache__"):
                continue
            if child.is_dir():
                kids = _safe_children(child)
                imgs = [k for k in kids if k.suffix.lower() in IMG_EXT]
                entries.append({
                    "name": child.name, "path": str(child), "kind": "dir",
                    "root": root.name, "mtime": _mtime(child),
                    "files": len(imgs), "git": (child / ".git").exists(),
                })
            elif child.suffix.lower() in IMG_EXT:
                entries.append({"name": child.name, "path": str(child), "kind": "image",
                                "root": root.name, "mtime": _mtime(child), "size": child.stat().st_size})
    entries.sort(key=lambda e: e.get("mtime") or 0, reverse=True)
    return {"entries": entries[:80], "roots": [str(r) for r in VISION_ROOTS]}


def vision_file(params):
    p = Path(params.get("path") or "")
    allowed = [r.resolve() for r in VISION_ROOTS]
    try:
        rp = p.resolve()
    except OSError:
        raise ValueError("bad path")
    if not any(str(rp).startswith(str(a)) for a in allowed):
        raise ValueError("path outside Vision roots")
    if rp.suffix.lower() not in IMG_EXT:
        raise ValueError("not an image")
    size = rp.stat().st_size
    if size > 3_500_000:
        raise ValueError("file too large for preview (>3.5MB)")
    import base64
    data = base64.b64encode(rp.read_bytes()).decode("ascii")
    return {"mime": IMG_EXT[rp.suffix.lower()], "dataB64": data, "name": rp.name,
            "path": str(rp), "size": size, "mtime": _mtime(rp)}


def squad_prompts(params):
    out = {}
    for aid, p in SQUAD_PROMPTS.items():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            out[aid] = {"path": str(p), "chars": len(text), "text": text if params.get("withText") else None}
        except OSError as exc:
            out[aid] = {"path": str(p), "error": str(exc)}
    return out


# --------------------------------------------------------------- سياق الوكيل الحي
# دفاتر الحالة الرسمية لكل وكيل (مسارات نسبية من جذر المستودع — سجل راصد المعتمد)
STATE_FILES = {
    "marwa": ["MARWA_HOME_STATE.md", "AGENT.md"],
    "rased": ["RASED_SENTINEL_STATE.md"],
    "hakim": [],
    "fares": ["FARES_CFO_STATE.md"],
    "salma": ["SALMA_CRM_STATE.md"],
    "koko": ["KOKO_MARKETING_STATE.md"],
    "bibo": ["BIBO_MANUFACTURING_STATE.md"],
    "sasa": ["SASA_WORKSHOP_STATE.md"],
    "vision": ["Vision-Lab/AGENT.md", "Vision-Lab/SQUAD_PROFILE.md"],
    "afkar": ["Vision-Lab/projects/notebook-v2/NB2_CHAT_BOOTSTRAP_PROMPT.md"],
}


def _head(p: Path, chars: int = 900):
    """قراءة رأس ملف نصي بأمان — بلا كتابة."""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        return {"path": str(p), "chars": len(text), "head": text[:chars].strip(), "mtime": _mtime(p)}
    except OSError as exc:
        return {"path": str(p), "error": str(exc), "mtime": 0.0}


# --------------------------------------------------------------- مساحات العمل الأصلية (Native Workspaces)
# كل وكيل له مجلد حقيقي = مساحة عمل DSH خاصة به؛ AGENTS.md داخله يُحقن تلقائياً
# كتعليمات نظام لكل جلسة تُفتح في هذا المجلد (dsh-agent-instructions — مفعّل افتراضياً).
AGENT_NAMES = {
    "marwa": "مروة", "afkar": "أفكاري", "rased": "راصد", "hakim": "حكيم",
    "fares": "فارس", "salma": "سلمى", "koko": "كوكو", "bibo": "بيبو",
    "sasa": "مصطفى (صاصا)", "vision": "فيجن",
}
WORKSPACE_DIRS = {
    "marwa": "orchestrator/squad/marwa",
    "afkar": "Vision-Lab/projects/notebook-v2",
    "rased": "orchestrator/squad/rased",
    "hakim": "orchestrator/squad/hakim",
    "fares": "orchestrator/squad/fares",
    "salma": "orchestrator/squad/salma",
    "koko": "orchestrator/squad/koko",
    "bibo": "orchestrator/squad/bibo",
    "sasa": "orchestrator/squad/sasa",
    "vision": "Vision-Lab",
}
AGENTS_MD_MARK = "مولّد من جسر marwa-core-workspace"


def workspaces_ensure(params):
    """تجهيز مساحة عمل الوكيل: المجلد + ملف AGENTS.md (دستور + هوية + دفاتر + مثبتة).
    لا يلمس أي ملف حالة جذري — يكتب AGENTS.md الذي ولّده هو فقط (بعلامة المولد)."""
    aid = params.get("agent") or ""
    if aid not in SQUAD_PROMPTS:
        raise ValueError("unknown agent: %r" % aid)
    rel = WORKSPACE_DIRS.get(aid) or ""
    ws_dir = REPO / rel if rel else REPO / "orchestrator" / "squad" / aid
    ws_dir.mkdir(parents=True, exist_ok=True)
    title = "غرفة عمليات - " + AGENT_NAMES.get(aid, aid)
    try:
        pinned = notebook_pinned({"limit": 12}) or {}
    except Exception:  # noqa: BLE001 — المثبتة تفشل فلا تكسر التجهيز
        pinned = {}
    parts = []
    parts.append("# " + title + " — مساحة عمل DSH لوكيل " + AGENT_NAMES.get(aid, aid))
    parts.append("")
    parts.append("> يُحقن تلقائياً في كل جلسة تُفتح داخل هذا المجلد (dsh-agent-instructions) — " + AGENTS_MD_MARK + ".")
    pr = _head(SQUAD_PROMPTS[aid], 1600)
    if "head" in pr:
        parts.append("")
        parts.append("## الدستور (CHAT_BOOTSTRAP_PROMPT)")
        parts.append(pr["head"])
    prof = REPO / "orchestrator" / "squad" / aid / "AGENT_PROFILE.md"
    if prof.exists():
        ph = _head(prof, 700)
        if "head" in ph:
            parts.append("")
            parts.append("## الهوية (AGENT_PROFILE)")
            parts.append(ph["head"])
    states = [REPO / rel2 for rel2 in STATE_FILES.get(aid, []) if (REPO / rel2).exists()]
    if states:
        parts.append("")
        parts.append("## دفاتر الحالة الرسمية (اقرأها قبل أي رد بأرقام)")
        for f in states:
            parts.append("- `" + str(f.relative_to(REPO)) + "` · آخر تحديث " +
                         time.strftime("%Y-%m-%d %H:%M", time.localtime(_mtime(f))))
    pnotes = pinned.get("notes") or []
    parts.append("")
    parts.append("## 📌 قرارات/ملاحظات المالك المثبتة (نوتبوك notebook.db)")
    if pnotes:
        for n in pnotes:
            parts.append("- [#" + str(n.get("id")) + "][" + str(n.get("kind") or "note") + "] " +
                         str(n.get("title") or "") + (":" + str(n.get("body") or "")[:260] if n.get("body") else ""))
    else:
        parts.append("- لا يوجد حالياً.")
    parts.append("")
    parts.append("---")
    parts.append("آخر تحديث تلقائي: " + time.strftime("%Y-%m-%d %H:%M") + " — " + AGENTS_MD_MARK)
    content = "\n".join(parts) + "\n"
    md_path = ws_dir / "AGENTS.md"
    written = False
    try:
        if (not md_path.exists()) or AGENTS_MD_MARK in md_path.read_text(encoding="utf-8", errors="replace"):
            if (not md_path.exists()) or md_path.read_text(encoding="utf-8", errors="replace") != content:
                md_path.write_text(content, encoding="utf-8")
                written = True
    except OSError:
        pass
    return {"agent": aid, "title": title, "path": str(ws_dir),
            "agentsMd": str(md_path), "agentsMdChars": len(content),
            "written": written, "pinnedCount": len(pnotes)}


def squad_context(params):
    """سياق حي لوكيل واحد: الدستور + ملف الهوية + دفاتر الحالة + المهام المفتوحة
    (نوتبوك موسوم agent:<id> + صندوق الوارد inbox_tasks/<id>). قراءة فقط."""
    aid = params.get("agent") or ""
    if aid not in SQUAD_PROMPTS:
        raise ValueError("unknown agent: %r" % aid)
    out = {"agent": aid}
    pr = _head(SQUAD_PROMPTS[aid], 900)
    out["prompt"] = {"path": pr.get("path"), "chars": pr.get("chars"),
                     "head": pr.get("head"), "error": pr.get("error"), "mtime": pr.get("mtime")}
    prof = REPO / "orchestrator" / "squad" / aid / "AGENT_PROFILE.md"
    out["profile"] = _head(prof, 700) if prof.exists() else None
    out["stateFiles"] = []
    for rel in STATE_FILES.get(aid, []):
        f = REPO / rel
        if f.exists():
            out["stateFiles"].append(_head(f, 1100))
    out["noteTasks"] = []
    conn = None
    try:
        conn = sqlite3.connect(str(NOTEBOOK_DB), timeout=6)
        conn.row_factory = sqlite3.Row
        like = "%agent:" + aid + "%"
        cur = conn.execute(
            "SELECT id, kind, title, priority, status, due_at, updated_at FROM notes"
            " WHERE status='open' AND (tags LIKE ? OR source LIKE ?)"
            " ORDER BY (priority='urgent') DESC, updated_at DESC LIMIT 8",
            (like, "%" + aid + "%"))
        out["noteTasks"] = [dict(r) for r in cur.fetchall()]
    except Exception as exc:  # noqa: BLE001 — المهام تُشير بصدق عند الفشل
        out["noteTasksError"] = str(exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
    inbox = REPO / "inbox_tasks" / aid
    files = []
    if inbox.exists():
        try:
            fl = sorted((f for f in inbox.iterdir() if f.is_file()),
                        key=_mtime, reverse=True)
            out["inbox"] = {"dir": str(inbox), "count": len(fl),
                            "files": [{"name": f.name, "mtime": _mtime(f),
                                       "size": f.stat().st_size} for f in fl[:8]]}
        except OSError as exc:
            out["inbox"] = {"dir": str(inbox), "count": 0, "files": [], "error": str(exc)}
    else:
        out["inbox"] = {"dir": str(inbox), "count": 0, "files": []}
    return out


HANDLERS = {
    "notebook.list": notebook_list,
    "notebook.add": notebook_add,
    "notebook.pin": notebook_pin,
    "notebook.pinned": notebook_pinned,
    "catalog.rows": catalog_rows,
    "pos.stats": pos_stats,
    "vision.list": vision_list,
    "vision.file": vision_file,
    "squad.prompts": squad_prompts,
    "squad.context": squad_context,
    "workspaces.ensure": workspaces_ensure,
}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        rid = req.get("id")
        cmd = req.get("cmd")
        try:
            handler = HANDLERS.get(cmd)
            if handler is None:
                raise ValueError("unknown command: %r" % cmd)
            value = handler(req.get("params") or {})
            resp = {"id": rid, "ok": True, "value": value}
        except Exception as exc:  # noqa: BLE001 — الخطأ يرجع للطالب ولا يقتل الجسر
            resp = {"id": rid, "ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False, default=str) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
