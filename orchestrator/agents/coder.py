# -*- coding: utf-8 -*-
"""Coder Agent (الكودر) — Phase 7 FULL BUILD.
- مراجعة كود بايثون أمانة: py_compile لملف واحد + عدّاد ملفات وسطور في نطاقات آمنة.
- بحث في الكود عن نص (grep) داخل نطاقات آمنة فقط (بلا مجلدات ضخمة/سرية).
- رصد الأخطاء: قراءة experience_ledger لأخطاء الوكلاء والفشل.
- Git/GitHub: حالة المستودع وعرض branch/status/log (قراءة فقط) — لو المشروع مش repo يُقال بصدق.
- **لا يعدّل أي كود بنفسه أبدًا**: التعديلات تتم من المنسق في DSH بموافقة المالك؛ الكودر يحدد المشكلة ويكتب الاقتراح بالضبط فقط.
قواعد صارمة: قراءة فقط، نطاقات آمنة، لا بيانات مخترعة — فشل أي أداة يُبلَّغ بصدق.
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import SubAgent

ROOT = Path(__file__).resolve().parent.parent.parent          # G:\ai\Elnagar POS
COMPILE_DIR = ROOT                                            # نطاق البحث الأوسع
LEDGER = Path(r"G:\ai\Naggar Print POS Agent\memory\experience_ledger.json")
CAP = 10
EXCLUDE_DIRS = {
    ".venv", "venv", "env", "node_modules", "__pycache__", "Backups",
    "SAFE_BACKUP_BEFORE_REPAIR", "_quarantine", "_ARCHIVE_SCRIPTS",
    "_sandbox_pos_writer", "build", "dist", ".git", ".dart_tool", ".firebase",
    "tools", "conan", "vcpkg",
}


def _safe_py_files(root: Path, limit: int = 100000) -> List[Path]:
    out: List[Path] = []
    root_abs = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_abs):
        dp = Path(dirpath)
        rel_parts = dp.relative_to(root_abs).parts
        # تجاهل الأدلة الحصرية أثناء المسح (يمنع الدخول لمجلدات ضخمة/مؤرشفة)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                out.append(dp / fn)
                if len(out) >= limit:
                    return out
    return out


def _fmt(n) -> str:
    try:
        f = float(n)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(n)


class CoderAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="coder",
            name="الكودر (Coder Agent)",
            keywords=[
                "راجع الكود", "كودر", "فحص بايثون", "شف البرمجيات",
                "git", "github", "مستودع", "repo", "كوميت", "commit",
                "فرع", "branch", "مرج", "merge", "سحب", "pull", "دفع", "push",
                "خطأ", "error", "استثناء", "exception", "traceback",
                "اصلاح", "fix", "تصحيح", "debug", "lint", "تنسيق", "format",
                "اعادة هيكلة", "refactor", "تنظيف", "cleanup",
                "ابحث في الكود", "بحث", "grep", "رصد الأخطاء", "أخطاء الوكلاء",
                "حالة المشروع", "صحة المشروع",
                "نزّل أداة", "استيراد أداة", "أداة من github", "أعتمد التنزيل",
            ],
            phase=7,
        )

    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"👨‍💻 {title}\n{body}", "action": "coder_report", "payload": {}}

    # -------------------------------------------------------------- قدرات
    def _find_py_file(self, text: str) -> Optional[Path]:
        m = re.search(r"[A-Za-z]:[\\/][^\s،]+\.py", text)
        if m:
            p = Path(m.group(0).strip('"'))
            if p.exists():
                return p
        for fname in re.findall(r"[\w/\\]+\.py", text):
            cand = Path(fname)
            if cand.is_absolute() and cand.exists():
                return cand
            cand2 = ROOT / fname
            if cand2.exists():
                return cand2
        return None

    def _compile_check(self) -> Dict[str, Any]:
        files = _safe_py_files(ROOT, 60)
        errs: List[Dict[str, Any]] = []
        checked = 0
        for p in files:
            try:
                compile(p.read_text(encoding="utf-8"), str(p), "exec")
                checked += 1
            except SyntaxError as exc:
                errs.append({"file": str(p), "line": getattr(exc, "lineno", "?"), "msg": exc.msg})
        body = [f"• فحص {_fmt(checked)} ملف بايثون في النطاقات الآمنة — {_fmt(len(errs))} خطأ صياغة."]
        if errs:
            body.append("  الأخطاء (أقصى 10):")
            lines = "\n  ".join(
                f"«{Path(e['file']).name}»: سطر {e['line']} — {e['msg'][:70]}" for e in errs[:CAP])
            body.append(lines + (f"\n  … و {len(errs) - CAP} أخرى" if len(errs) > CAP else ""))
        else:
            body.append("  كل الملفات سالمة صياغيًا ✅")
        body.append("🔒 الصياغة فحص فقط — أي تعديل كود يتم من المنسق في DSH بعد موافقتك.")
        return self._reply("فحص صياغة بايثون", "\n".join(body))

    def _grep(self, term: str) -> Dict[str, Any]:
        term = term.strip()
        if not term or term.lower() in ("ابحث في الكود", "بحث", "grep", "في الكود", "عن"):
            return self._reply(
                "بحث في الكود", "ابعت النص اللي تدور عليه: «ابحث في الكود عن record_client_payment».")
        files = _safe_py_files(ROOT, 100000)
        hits: List[Dict[str, Any]] = []
        pat = re.compile(re.escape(term), re.IGNORECASE)
        for p in files:
            try:
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if pat.search(line):
                        hits.append({"file": str(p), "line": i, "text": line.strip()[:90]})
                        if len(hits) >= CAP:
                            break
            except Exception:
                continue
            if len(hits) >= CAP:
                break
        if not hits:
            return self._reply(
                "بحث في الكود",
                f"«{term}» ما اتلقتش في الملفات الآمنة ({_fmt(len(files))} ملف مفحوص).")
        body = [f"• «{term}» — {_fmt(len(hits))} نتيجة (أقصى {CAP}):"]
        body.append("  " + "\n  ".join(
            f"«{Path(h['file']).name}»:سطر {h['line']} — {h['text']}" for h in hits))
        body.append("🔒 البحث قراءة فقط — أي تعديل من المنسق بعد موافقتك.")
        return self._reply("بحث في الكود", "\n".join(body))

    def _error_watch(self) -> Dict[str, Any]:
        try:
            import json
            if not LEDGER.exists():
                return self._reply("رصد الأخطاء", "سجل الخبرة غير موجود بعد (لا أخطاء مسجلة).")
            data = json.loads(LEDGER.read_text(encoding="utf-8"))
            errs = [e for e in data.get("entries", []) if e.get("error")]
            if not errs:
                return self._reply("رصد الأخطاء", "✅ لا أخطاء مسجلة في سجل الخبرة (clean).")
            by_agent: Dict[str, int] = {}
            for e in errs:
                aid = e.get("agent_id") or "غير موجَّه"
                by_agent[aid] = by_agent.get(aid, 0) + 1
            body = [f"• أخطاء مسجلة في experience_ledger: {_fmt(len(errs))}"]
            body.append("• بالوكيل: " + "، ".join(f"{k} ({v})" for k, v in by_agent.items()))
            body.append("• آخر الأخطاء (5):")
            body.append("  " + "\n  ".join(
                f"{(e.get('timestamp') or '')[:16]} | {e.get('agent_id') or '?'} | "
                f"{(e.get('error') or '')[:70]}" for e in errs[-5:]))
            body.append("💡 التصحيح يتم عبر المنسق في DSH بموافقتك — رصد فقط هنا.")
            return self._reply("رصد أخطاء الوكلاء", "\n".join(body))
        except Exception as exc:
            return self._reply("رصد الأخطاء", f"❌ فشل قراءة السجل ({type(exc).__name__}: {exc}).")

    def _git_status(self) -> Dict[str, Any]:
        try:
            r = subprocess.run(
                ["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, timeout=15, check=False,
            )
            is_repo = r.stdout.strip() == "true"
        except Exception:
            is_repo = False
        if not is_repo:
            return self._reply(
                "Git/GitHub",
                "المشروع (G:\\ai\\Elnagar POS) مش مستودع Git لسه — .gitignore موجود أصلًا. "
                "لو عايزه مستودع قولي «هيئ Git» وبيكون بأمرك (git init + أول commit بموافقتك).")
        try:
            branch = subprocess.run(["git", "-C", str(ROOT), "branch", "--show-current"],
                                    capture_output=True, text=True, timeout=15).stdout.strip()
            status = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                                    capture_output=True, text=True, timeout=15).stdout
            last = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--oneline"],
                                  capture_output=True, text=True, timeout=15).stdout.strip()
            changed = [l for l in status.splitlines() if l.strip()][:CAP]
            body = [
                f"• الفرع: {branch or '(detached)'}",
                f"• آخر commit: {last or '(لا commits)'}",
                f"• ملفات متغيرة: {_fmt(len([l for l in status.splitlines() if l.strip()]))}",
            ]
            if changed:
                body.append("  مثال: " + "، ".join(l[:60] for l in changed[:5]))
            body.append("🔒 git status/log قراءة فقط — أي commit/push يتم بموافقتك عبر الكودر في DSH.")
            return self._reply("Git/GitHub", "\n".join(body))
        except Exception as exc:
            return self._reply("Git/GitHub", f"❌ فشل قراءة git ({type(exc).__name__}: {exc}).")

    def _project_health(self) -> Dict[str, Any]:
        files = _safe_py_files(ROOT, 60)
        total_lines = 0
        sizes: List[Dict[str, Any]] = []
        for p in files:
            try:
                n = sum(1 for _ in p.read_text(encoding="utf-8").splitlines())
            except Exception:
                n = 0
            total_lines += n
            sizes.append({"file": str(p), "lines": n})
        sizes.sort(key=lambda s: -s["lines"])
        body = [
            f"• ملفات بايثون في النطاقات الآمنة: {_fmt(len(files))} — إجمالي ~{_fmt(total_lines)} سطرًا.",
            "• الأكبر حجمًا: " + "، ".join(
                f"«{Path(s['file']).name}» ({_fmt(s['lines'])})" for s in sizes[:5]),
            "• المستبعدون من الفحص (أمانًا): .venv، Backups، _quarantine، _ARCHIVE، tools/github…",
        ]
        return self._reply("صحة المشروع", "\n".join(body))

    def _github_ingest(self, t: str, text: str) -> Dict[str, Any]:
        """استيراد أداة مفتوحة المصدر من GitHub إلى مسار معزول + توليد wrapper (بموافقة المالك)."""
        m = re.search(r"https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?\b", text)
        if not m:
            return self._reply(
                "استيراد من GitHub",
                "لتنزيل أداة مفتوحة المصدر أرسل الرابط: «نزّل أداة https://github.com/owner/repo».\n"
                "الملاحظة: التنزيل يتم دائمًا في مسار معزول (orchestrator\\tools\\github\\repo) ولا يلمس "
                "كود الإنتاج، وبموافقتك الصريحة (<أعتمد التنزيل> في نفس رسالتك).")
        owner_repo = m.group(1)
        repo_name = owner_repo.split("/")[-1].strip()
        if "أعتمد" not in t and "اعتمد" not in t and "اكيد" not in t and "أكيد" not in t and "نعم" not in t:
            return self._reply(
                "استيراد من GitHub",
                f"خطة الاستيراد — أداة «{repo_name}»:\n"
                f"  1. git clone --depth 1 https://github.com/{owner_repo} → "
                f"{ROOT}\\tools\\github\\{repo_name}\n"
                "  2. توليد wrapper تلقائيًا (يسجّلها كمهارة فرعية تفهمها مروة ويمكن استدعاؤها).\n"
                "  3. لا تغيير على أي ملف إنتاجي — المسار معزول تمامًا.\n"
                "🔒 لتأكيد التنفيذ أرسل نفس الرقم مع كلمة التأكيد: «نزّل "
                f"https://github.com/{owner_repo} + أعتمد».",
            )
        # التأكيد متوفر → نفذ
        dest = ROOT / "tools" / "github" / repo_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and (dest / ".git").exists():
            return self._reply(
                "استيراد من GitHub",
                f"الأداة «{repo_name}» موجودة عندي أصلًا في {dest}. لو عايز تحديث المحتوى: "
                f"«حدّث أداة {repo_name}» (git pull بأمرك).")
        try:
            url = f"https://github.com/{owner_repo}.git"
            r = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(dest)],
                capture_output=True, text=True, timeout=180, check=False,
            )
            if r.returncode != 0:
                return self._reply(
                    "استيراد من GitHub",
                    f"❌ فشل الاستنساخ (git exit {r.returncode}): {(r.stderr or r.stdout)[-160:]} — "
                    "ما افترضشت نجاح. تحقق من وجود المستودع.")
            # توليد wrapper يسجّلها كمهارة فرعية
            wrap_path = dest.parent / f"{repo_name}.md"
            wrap = (
                f"# أداة خارجية: {repo_name}\n"
                f"- المصدر: https://github.com/{owner_repo}\n"
                f"- الاستنساخ: {dest} (بأمر المالك {datetime.now().isoformat()})\n"
                f"- الاستخدام: استدعاء عبر system_worker/coder — شغّلها كأمر منفصل بلا كتابة على الإنتاج.\n"
                f"- المسار معزول (tools\\github\\) ولا يُفحص ضمن البحث الآمن افتراضيًا.\n"
            )
            try:
                wrap_path.write_text(wrap, encoding="utf-8")
            except Exception:
                wrap_path = None
            body = [
                f"• ✅ اسُتنسخت «{repo_name}» في المسار المعزول:\n  {dest}",
                f"• wrapper: {wrap_path if wrap_path else '(تعذر كتابة الملف — المسار معزول فحسب)'}",
                "• سُجّلت كمهارة فرعية تفهمها مروة؛ للاستدعاء منها اكتب: ",
                f"    «استخدم أداة {repo_name}»",
                "⚠️ حذر الأمان: كود الأداة الخارجية يُعامل كبيانات غير موثوقة ولا يتنفذ ذاتيًا على الإنتاج.",
            ]
            return self._reply("استيراد من GitHub", "\n".join(body))
        except FileNotFoundError:
            return self._reply(
                "استيراد من GitHub",
                "❌ أداة git غير متوفرة على الجهاز (git ليس في PATH) — لتثبيتها بأمرك.",
            )
        except Exception as exc:
            return self._reply(
                "استيراد من GitHub",
                f"❌ فشل الاستيراد ({type(exc).__name__}: {exc}) — ما افترضشت نجاحًا.",
            )

    # -------------------------------------------------------------- التوجيه
    def handle(self, text, ctx=None):
        t = (text or "").lower()
        try:
            if any(k in t for k in ("فحص بايثون", "راجع الكود", "صياغة", "compile", "الكود كلو", "الكود كله")):
                return self._compile_check()
            if "ابحث في الكود" in t or ("بحث" in t and "خطأ" not in t):
                term = re.sub(r"(ابحث في الكود عن|ابحث عن|دور على|ابحث)", "", text, flags=re.IGNORECASE).strip()
                return self._grep(term)
            if any(k in t for k in ("رصد الأخطاء", "أخطاء الوكلاء", "أخطاء الوكيل")):
                return self._error_watch()
            if any(k in t for k in ("نزّل أداة", "استيراد أداة", "أداة من github", "أعتمد التنزيل",
                                    "نزل أداة", "سحب أداة", "لتنزيل أداة", "github.com")):
                return self._github_ingest(t, text)
            if any(k in t for k in ("git", "github", "مستودع", "repo", "فرع", "branch",
                                    "commit", "كوميت", "merge", "مرج", "pull", "push")):
                return self._git_status()
            if any(k in t for k in ("حالة المشروع", "صحة المشروع", "ملفات المشروع", "عد الملفات")):
                return self._project_health()
            if any(k in t for k in ("عدل الكود", "صلح الكود", "عدل ملف", "صلح ملف", "عدّل الكود", "صحح الكود")):
                return self._reply(
                    "تعديل الكود",
                    "🔒 تعديل الكود لا يُنفذ ذاتيًا أبدًا: حدد الملف/السطر والمشكلة، "
                    "وأنا أكتب لك الاقتراح بالضبط، والتطبيق يتم من المنسق في DSH بعد موافقتك الصريحة.")
            if any(k in t for k in ("خطأ", "error", "استثناء", "exception", "traceback",
                                    "تصحيح", "اصلاح", "fix")):
                return self._error_watch()
            return self._reply(
                "الكودر",
                "قدراتي: «فحص بايثون» (صياغة كل الملفات الآمنة) / «ابحث في الكود عن …» / "
                "«رصد الأخطاء» (من experience_ledger) / «Git» (حالة المستودع) / «حالة المشروع».\n"
                "أي تعديل كود = بموافقتك عبر DSH.",
            )
        except Exception as exc:
            return self._reply("الكودر", f"❌ فشل العملية ({type(exc).__name__}: {exc}) — ما افترضشت نتيجة.")
