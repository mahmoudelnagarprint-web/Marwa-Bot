# -*- coding: utf-8 -*-
"""بيبو Production — طبقة الملفات (صندوق الوارد، الإنجاز، الماكينات، سحب الخامات).

كل حاجة هنا **ملفات Markdown** جوه `workspaces/<agent>/inbox_tasks/`، بالصيغة
اللي بيكتبها الـslash-command (`/task @bebo …`). مفيش قاعدة بيانات في الطبقة
دي عن قصد: الـworkspaces هي مصدر الحقيقة للوكلاء، وأي جدول جديد كان هيعمل
نسخة تانية من نفس المعلومة تفرق عن الملفات بعد أول تعديل يدوي.

**قاعدة الصيغة (متقاسة على مهمة زينب الحقيقية):**

    # مهمة: <العنوان>

    - **المهمة**: <العنوان>
    - **الوكيل**: @bebo (bebo_production)
    - **الأمر**: /task @bebo <العنوان>
    - **الأولوية**: normal
    - **بواسطة**: mahmoud
    - **op_id**: 01a15a79ebbc-54060d170646
    - **الحالة**: pending

    ---

    مراجعة: <العنوان>

الـparser بيتسامح: بيقبل المسافات الزايدة، والـ`**` مش شرط، والقيم الفاضية،
وبيرجّع `None` بدل ما يرمي استثناء لو الملف مش من الصيغة دي (ملف تالف في
الصندوق مايقفلش الصفحة كلها).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nb import config

# ------------------------------------------------------------------ المسارات
WORKSPACES_DIR = config.MARWA_ROOT / "workspaces"
BEBO_DIR = WORKSPACES_DIR / "bebo_production"
BEBO_INBOX = BEBO_DIR / "inbox_tasks"
BEBO_LOGS = BEBO_DIR / "logs"
AUDIT_FILE = BEBO_LOGS / "audit.jsonl"
SALMA_INBOX = WORKSPACES_DIR / "salma_crm" / "inbox_tasks"
FARES_INBOX = WORKSPACES_DIR / "fares_cfo" / "inbox_tasks"

# مفاتيح الصيغة: (اسم الحقل في الـJSON، التسمية العربية في الملف)
_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("title", "المهمة"),
    ("agent", "الوكيل"),
    ("command", "الأمر"),
    ("priority", "الأولوية"),
    ("by", "بواسطة"),
    ("op_id", "op_id"),
    ("status", "الحالة"),
)

# سطر الميتا: `- **المهمة**: استعجال …` — الـ** اختيارية، والمسافة بعد النقطتين اختيارية
_LINE_RE = re.compile(r"^\s*[-*]?\s*\**\s*(?P<key>[^:*]+?)\s*\**\s*:\s*\**\s*(?P<val>.*?)\s*$")
_TITLE_RE = re.compile(r"^\s*#\s*مهمة\s*:\s*(?P<title>.+?)\s*$")


# ------------------------------------------------------------------ أدوات صغيرة
def utcnow_iso() -> str:
    """وقت UTC بصيغة ISO-8601 بالثواني — نفس شكل باقي سجلات المشروع."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_op_id() -> str:
    """مُعرّف بصيغة ULID-شكل: 12 hex (وقت) + '-' + 12 hex.

    الصيغة متقاسة على `01a15a79ebbc-54060d170646` — الـprefix الأول في
    الملفات الحقيقية طالع من زمن الميلي‑ثانية، فبنبنيه بنفس الطريقة عشان
    الترتيب الزمني يفضل مقروء من الاسم نفسه، وباقي الجزء عشوائي آمن.
    """
    head = format(int(time.time() * 1000), "012x")[-12:]
    return f"{head}-{secrets.token_hex(6)}"


def _slug(text: str, limit: int = 60) -> str:
    """اسم ملف آمن: العربي يتسيب زي ما هو، وكل حاجة تخرّب مسار بتتحول لـ`_`.

    مهم: مابنشيلش العربي — أسماء الملفات الحقيقية عربية
    (`01a15a79ebbc-… .استعجال_طلب_328_زينب___من_لوحة_سلمى.md`)، ولو رميناه
    الملف هيتسمى بحاجة مالهاش معنى للمستخدم.
    """
    out = []
    for ch in text.strip():
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch.isspace() or ch in "،,.!?()[]{}«»\":;'…—–/\\|*<>":
            out.append("_")
        else:
            out.append("_")
    slug = "".join(out)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:limit] or "task"


def _safe_under(base: Path, name: str) -> Path:
    """يمنع أي `..`/مسار مطلق يخرج عن المجلد — حراسة على أسماء الملفات."""
    p = (base / name).resolve()
    root = base.resolve()
    if root != p and root not in p.parents:
        raise ValueError("مسار خارج صندوق الوارد مرفوض")
    return p


# ------------------------------------------------------------------ الـparser
def parse_task_file(path: Path) -> Optional[Dict[str, Any]]:
    """يقرأ ملف مهمة واحد. بيرجّع dict أو None لو الملف مش من الصيغة.

    الحقول المضمونة في الاستجابة: op_id, title, agent, command, priority,
    by, status, body, filename, path, mtime.
    """
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    fields: Dict[str, str] = {}
    title_from_h1: Optional[str] = None
    body_lines: List[str] = []
    seen_sep = False

    for line in raw.splitlines():
        if not seen_sep and line.strip() == "---":
            seen_sep = True
            continue
        if seen_sep:
            body_lines.append(line)
            continue
        m = _TITLE_RE.match(line)
        if m and title_from_h1 is None:
            title_from_h1 = m.group("title")
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        key = m.group("key").strip()
        val = m.group("val").strip().strip("*").strip()
        for json_key, arabic in _FIELDS:
            if key == arabic:
                fields.setdefault(json_key, val)
                break

    # ملف مالوش أي حقل ولا عنوان ⇒ مش مهمة، مانضيّعش وقت
    if not fields and not title_from_h1:
        return None

    op_id = fields.get("op_id") or ""
    if not op_id:
        # احتياطي: أول جزء من اسم الملف قبل أول نقطة
        stem = path.name.split(".")[0]
        op_id = stem if re.fullmatch(r"[0-9a-fA-F-]{8,}", stem) else ""

    title = fields.get("title") or title_from_h1 or path.stem
    body = "\n".join(body_lines).strip()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0

    return {
        "op_id": op_id,
        "title": title,
        "agent": fields.get("agent", ""),
        "command": fields.get("command", ""),
        "priority": (fields.get("priority") or "normal").lower(),
        "by": fields.get("by", ""),
        "status": (fields.get("status") or "pending").lower(),
        "body": body,
        "filename": path.name,
        "path": str(path),
        "mtime": mtime,
    }


def list_inbox(agent_dir: Optional[Path] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """كل المهام في صندوق وارد معيّن، الأحدث تعديلًا الأول.

    `status` اختياري: `pending`/`done` أو None لكل حاجة.
    """
    base = agent_dir or BEBO_INBOX
    if not base.is_dir():
        return []
    tasks: List[Dict[str, Any]] = []
    for p in sorted(base.glob("*.md")):
        if not p.is_file():
            continue
        t = parse_task_file(p)
        if t is None:
            continue
        if status and t["status"] != status:
            continue
        tasks.append(t)
    tasks.sort(key=lambda t: (t["mtime"], t["filename"]), reverse=True)
    return tasks


def find_task(op_id: str, agent_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """يدوّر على مهمة بالـop_id في الصندوق (الحقل الأول، وبعدين اسم الملف)."""
    base = agent_dir or BEBO_INBOX
    if not op_id or not base.is_dir():
        return None
    want = op_id.strip()
    for p in base.glob("*.md"):
        if not p.is_file():
            continue
        if want not in p.name:
            continue
        t = parse_task_file(p)
        if t is not None and t["op_id"] == want:
            return t
    # محاولة تانية: اسم الملف فيه الـid بس الحقل فاضي/مختلف
    for p in base.glob("*.md"):
        if p.is_file() and want in p.name:
            t = parse_task_file(p)
            if t is not None:
                if not t["op_id"]:
                    t["op_id"] = want
                return t
    return None


# ------------------------------------------------------------------ الكتابة
def write_task_file(inbox: Path, title: str, agent_handle: str, agent_slug: str,
                    by: str, body: str = "", priority: str = "normal",
                    op_id: Optional[str] = None) -> Dict[str, Any]:
    """يكتب ملف مهمة جديد بنفس صيغة الـslash-command بالحرف.

    الصيغة دي **مقاسة على مهمة زينب الحقيقية** — نفس ترتيب السطور، ونفس
    السطر `---` الفاصل، ونفس سطر `مراجعة: …` في الآخر، عشان لو الوكيل
    المستقبِل بيقرا الملفات دي بأي طريقة تانية يفضل شغّال.
    """
    oid = op_id or make_op_id()
    inbox.mkdir(parents=True, exist_ok=True)
    name = f"{oid}.{_slug(title)}.md"
    path = _safe_under(inbox, name)
    if path.exists():                      # نادر: نفس الثانية ونفس العنوان
        oid = make_op_id()
        name = f"{oid}.{_slug(title)}.md"
        path = _safe_under(inbox, name)

    text = (
        f"# مهمة: {title}\n"
        f"\n"
        f"- **المهمة**: {title}\n"
        f"- **الوكيل**: @{agent_handle} ({agent_slug})\n"
        f"- **الأمر**: /task @{agent_handle} {title}\n"
        f"- **الأولوية**: {priority}\n"
        f"- **بواسطة**: {by}\n"
        f"- **op_id**: {oid}\n"
        f"- **الحالة**: pending\n"
        f"\n"
        f"---\n"
        f"\n"
        f"{body or ('مراجعة: ' + title)}\n"
    )
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"op_id": oid, "filename": name, "path": str(path), "title": title}


def set_status(path: Path, new_status: str) -> bool:
    """يغيّر سطر `- **الحالة**: …` جوه الملف نفسه. بيرجّع True لو اتغيّر.

    بنستبدل السطر بس (مش نعيد كتابة الملف) عشان أي جسم حر أو تنسيق المستخدم
    يفضل زي ما هو حرفيًا.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = raw.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        m = _LINE_RE.match(line.rstrip("\r\n"))
        if m and m.group("key").strip() == "الحالة":
            eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")
            lines[i] = f"- **الحالة**: {new_status}{eol}"
            changed = True
            break
    if not changed:
        # مفيش سطر حالة أصلاً ⇒ نحطه بعد op_id (أو في آخر الميتا)
        out: List[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            m = _LINE_RE.match(line.rstrip("\r\n"))
            if m and m.group("key").strip() == "op_id" and not inserted:
                out.append(f"- **الحالة**: {new_status}\n")
                inserted = True
        if not inserted:
            out.append(f"- **الحالة**: {new_status}\n")
        lines = out
        changed = True
    try:
        path.write_text("".join(lines), encoding="utf-8", newline="")
    except OSError:
        return False
    return changed


def append_audit(record: Dict[str, Any]) -> bool:
    """append صف JSON واحد في `logs/audit.jsonl` — سطر واحد، UTF-8، ذرّي بما يكفي.

    `ensure_ascii=False` مقصود: العربي في السجل لازم يتقرا كعربي. وبنفتح
    بـ`open(..., 'a')` في نداء واحد عشان مايتقاطعش مع كتابة تانية.
    """
    try:
        BEBO_LOGS.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with open(AUDIT_FILE, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
        return True
    except OSError:
        return False


# ------------------------------------------------------------------ منطق المهمة
def complete_task(op_id: str, by: str = "bebo") -> Dict[str, Any]:
    """ينجز مهمة: الحالة → done، سجل audit، وإشعار للمرسل.

    بيرجّع dict فيه `ok` + تفاصيل ما اتعمل بالظبط، عشان الـendpoint يرجّعه
    للواجهة بلا أي تخمين.
    """
    task = find_task(op_id)
    if task is None:
        return {"ok": False, "error": "مهمة مش موجودة", "op_id": op_id}

    path = Path(task["path"])
    already = task["status"] == "done"
    changed = False if already else set_status(path, "done")

    at = utcnow_iso()
    append_audit({
        "op_id": task["op_id"],
        "action": "done",
        "at": at,
        "by": by,
        "title": task["title"],
        "requested_by": task["by"],
        "file": task["filename"],
        "already_done": already,
    })

    notify = notify_requester(task, by=by)
    return {
        "ok": True,
        "op_id": task["op_id"],
        "status": "done",
        "changed": changed,
        "already_done": already,
        "audit": str(AUDIT_FILE),
        "notify": notify,
    }


def notify_requester(task: Dict[str, Any], by: str = "bebo") -> Dict[str, Any]:
    """يكتب ملف إشعار للمرسل في صندوقه، لو المرسل وكيل تاني.

    القاعدة اللي اتفقنا عليها:
      • `بواسطة: mahmoud` ⇒ مانعملش ملف (المحمول/الواجهة هي اللي تعرضله)،
        بس بنرجّع `ok` مع سبب واضح.
      • `بواسطة: salma` **أو** العنوان فيه «من لوحة سلمى» ⇒ ملف في
        `salma_crm/inbox_tasks/` بعنوان «أنجز بيبو المهمة: <المهمة>».
    """
    requester = (task.get("by") or "").strip()
    low = requester.lower()
    title = task["title"]

    if not requester or low in {"mahmoud", "محمود", "owner"}:
        # لو العنوان نفسه جاي من لوحة سلمى، ده برضه يستحق إشعارها
        if "من لوحة سلمى" not in title:
            return {"written": False, "reason": "المرسل هو المالك — مفيش ملف مطلوب"}

    target = None
    slug = None
    handle = None
    if low.startswith("salma") or "من لوحة سلمى" in title or "سلمى" in requester:
        target, slug, handle = SALMA_INBOX, "salma_crm", "salma"
    elif low.startswith("fares"):
        target, slug, handle = FARES_INBOX, "fares_cfo", "fares"
    else:
        # مرسل مش معروف ⇒ مانخترعش مسار؛ بنسجّل ونرجّع سبب
        return {"written": False,
                "reason": f"مسار إشعار غير معروف للمرسل «{requester}»"}

    note_title = f"أنجز بيبو المهمة: {title}"
    body = (f"تم إنجاز المهمة اللي بعتها لبيبو.\n\n"
            f"- **المهمة الأصلية**: {title}\n"
            f"- **op_id الأصلي**: {task['op_id']}\n"
            f"- **أنجزها**: @{by}\n"
            f"- **وقت الإنجاز**: {utcnow_iso()}")
    written = write_task_file(target, note_title, handle, slug, by=by, body=body)
    return {"written": True, "to": slug, "path": written["path"],
            "op_id": written["op_id"], "title": note_title}


# ------------------------------------------------------------------ الماكينات
# كائن ثابت عن قصد (قراءة-فقط): الليد قال ما نعملش جدول جديد من غير تنسيق.
# لو حبيت يتحرك حقيقي، بديله قراءة من `ws_machines` لما تتوفر.
_MACHINES: Tuple[Dict[str, Any], ...] = (
    {"id": "epson-l1800", "name": "Epson L1800",
     "status": "available", "current_job": None},
    {"id": "laser-co2-rdworks", "name": "ليزر CO2 (RDWorks)",
     "status": "available", "current_job": None},
    {"id": "cutter-plotter", "name": "كاتر بلوتر",
     "status": "available", "current_job": None},
)

_VALID_MACHINE_STATUS = {"available", "busy", "maintenance"}


def machines() -> Dict[str, Any]:
    """حالة الماكينات — كائن ثابت، بنرجّعه كـlist of dicts بالحرف.

    بنعمل نسخة سطحية (dict لكل ماكينة) عشان المستدعي مايعدّلش الكائن الأصلي.
    """
    return {"machines": [dict(m) for m in _MACHINES],
            "source": "initial-static",
            "note": "كائن بدئي ثابت — مفيش جدول قاعدة بيانات للماكينات بعد"}


# ------------------------------------------------------------------ سحب الخامات
def material_checkout(material: str, qty: Any, job_no: str,
                      by: str = "bebo") -> Dict[str, Any]:
    """يسجّل سحب خامات كمهمة في صندوق fares_cfo.

    العنوان بالحرف المتفق عليه: «سحب خامات [job_no]: <material> × <qty> — من بيبو»
    """
    material = (material or "").strip()
    job_no = (job_no or "").strip()
    if not material:
        return {"ok": False, "error": "الخامة مطلوبة (material)"}
    if job_no == "":
        return {"ok": False, "error": "رقم الشغلانة مطلوب (job_no)"}
    try:
        qty_v = float(qty)
    except (TypeError, ValueError):
        return {"ok": False, "error": "الكمية لازم تكون رقم (qty)"}
    if qty_v <= 0:
        return {"ok": False, "error": "الكمية لازم تكون أكبر من صفر"}

    qty_txt = str(int(qty_v)) if float(qty_v).is_integer() else str(qty_v)
    title = f"سحب خامات {job_no}: {material} × {qty_txt} — من بيبو"
    body = (f"سحب خامات من بيبو (شغل الورشة).\n\n"
            f"- **الخامة**: {material}\n"
            f"- **الكمية**: {qty_txt}\n"
            f"- **رقم الشغلانة**: {job_no}\n"
            f"- **الطلب من**: @{by}\n"
            f"- **الوقت**: {utcnow_iso()}\n"
            f"\nخصم الخامة من رصيد المخزن بعد المراجعة.")
    written = write_task_file(FARES_INBOX, title, "fares", "fares_cfo",
                              by="bebo", body=body, priority="normal")
    append_audit({"op_id": written["op_id"], "action": "material_checkout",
                  "at": utcnow_iso(), "by": by, "material": material,
                  "qty": qty_v, "job_no": job_no, "file": written["filename"]})
    return {"ok": True,
            "message": title,
            "op_id": written["op_id"],
            "path": written["path"],
            "task": written}
