# -*- coding: utf-8 -*-
"""RASED — Daily AutoSync (بأمر المالك 2026-10-26)
====================================================
أمر المالك: «راصد اعمل لنفسك Automation tasks — كل يوم الساعة 6م أو كل يوم
أول ما يفتح الجهاز، تعمل أب‍ديت للبرنامج عن طريق سحب الملفات من جيت هب والقاعدة
السحابية ورفع معاك لوِجد، مع إعطاء تقرير بمزامنة النظامين (الورشة واللاب).»

يشغّل هذا السكربت المهام التالية بالترتيب:
  1) Git pull من GitHub (سحب آخر الكود من LAPTOP/زملاء) — rebase آمن.
  2) Git add/commit/push (رفع عمل هذا الجهاز WORKSHOP إن وُجد) — بالحواجز الآمنة.
  3) القاعدة السحابية: سحب الأوامر (pull_queue) ثم رفع المرآة (push_mirror).
  4) توليد تقرير مزامنة النظامين (الورشة + اللابتوب + السحابة) يُلحق في:
       - logs/rased_daily_autosync.log
       - RASED_SENTINEL_STATE.md تحت مرساة «رصد المزامنة اليومي»

الأمان (ميثاق راصد — لا تُكسر أبداً):
  - لا force-push، لا حذف، لا إعادة كتابة تاريخ.
  - قراءة القاعدة المحلية فقط بلا تغيير؛ الدفع للسحابة عبر مسار HermesSyncManager.
  - لا أسرار في اللوج؛ كل تشغيل مسجَّل + قفل ضد التشغيل المتزامن.

الجدولة (خارج هذا السكربت — Scheduled Task في Windows):
  RASED_DailyAutoSync — عند تسجيل الدخول (At logon) + يومياً 18:00.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

# إجبار stdout/stderr على UTF-8 (ويندوز كونسول cp1252 يكسر العربية)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
LOG_FILE = LOGS / "rased_daily_autosync.log"
LOCK_FILE = LOGS / "rased_daily_autosync.lock"
LOCK_STALE_SECONDS = 3600
STATE_BOOK = ROOT / "RASED_SENTINEL_STATE.md"
ANCHOR = "## 🔄 رصد المزامنة اليومي (توليد آلي — rased_daily_autosync)"
GIT = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
PY = sys.executable or "python"

FORBIDDEN_NAMES = {".env", "LAPTOP_SECRET_KIT.md"}
FORBIDDEN_SUFFIXES = (
    ".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3", ".dump",
    ".key", ".pem", ".p12", ".pickle", ".bak",
)


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _node_id() -> str:
    try:
        for raw in (ROOT / ".env").read_text(encoding="utf-8-sig", errors="replace").splitlines():
            line = raw.strip()
            if line.startswith("NODE_ID"):
                val = line.partition("=")[2].strip().strip('"').strip("'")
                if val:
                    return val
    except OSError:
        pass
    return os.environ.get("COMPUTERNAME") or "WORKSHOP"


NODE = _node_id()


def log(msg: str, level: str = "INFO") -> None:
    line = f"[{_stamp()}] [{level}] {msg}"
    print(line, flush=True)
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


# ----------------------------------------------------------------- lock
def acquire_lock() -> bool:
    LOGS.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                log("skip: تشغيل سابق ما زال جارٍ (قفل فعال) — اخرج")
                return False
            log(f"قفل قديم ({int(age)}s) — نزيله ونكمل")
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            return False
    try:
        with LOCK_FILE.open("x", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {_stamp()}\n")
        return True
    except FileExistsError:
        log("skip: سباق قفل خسرناه")
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ----------------------------------------------------------------- git helpers
def git(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return subprocess.run(
        [GIT, "-C", str(ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=env,
    )


def _tail(p: subprocess.CompletedProcess, limit: int = 180) -> str:
    return (p.stderr or p.stdout or "").strip().replace("\n", " | ")[-limit:]


def git_pull() -> str:
    """سحب الكود من GitHub مع rebase آمن. يرجع سطر خلاصة."""
    fetch = git("fetch", "origin", "--prune", timeout=60)
    if fetch.returncode != 0:
        return f"فشل fetch (غير متصل؟): {_tail(fetch)}"
    remote = "origin/main"
    behind = git("rev-list", "--count", f"HEAD..{remote}")
    try:
        n = int((behind.stdout or "0").strip() or "0")
    except ValueError:
        n = 0
    if n <= 0:
        return "لا جديد في GitHub (محدث)"
    pull = git("pull", "--rebase", "--autostash", "origin", "main", timeout=120)
    if pull.returncode != 0:
        git("rebase", "--abort")
        return f"تعارض rebase — مضبوط بدون رفع: {_tail(pull)}"
    return f"سحب {n} commit من GitHub ✓"


def git_push() -> str:
    """تجميع التغييرات المحلية + رفعها إن وُجدت (بالحواجز الآمنة)."""
    add = git("add", "-A")
    if add.returncode != 0:
        return f"فشل git add: {_tail(add)}"
    staged = [p.strip() for p in (git("diff", "--cached", "--name-only").stdout or "").splitlines() if p.strip()]
    blocked = [p for p in staged if Path(p).name in FORBIDDEN_NAMES or Path(p).name.endswith(FORBIDDEN_SUFFIXES)]
    if blocked:
        git("reset")
        return f"أُلغي (مسار محظور: {blocked[:5]})"
    if not staged:
        return "لا تغييرات محلية للرفع"
    msg = f"auto-sync: {NODE} @ {time.strftime('%Y-%m-%d %H:%M')}"
    commit = git("commit", "-m", msg)
    if commit.returncode != 0:
        return f"فشل commit: {_tail(commit)}"
    push = git("push", "origin", "HEAD:main", timeout=120)
    if push.returncode != 0:
        return f"رفع فشل (هيُعاد لاحقاً): {_tail(push)}"
    return f"رفع {len(staged)} ملف من {NODE} إلى GitHub ✓"


# ----------------------------------------------------------------- cloud sync
def cloud_sync() -> str:
    """سحب + رفع القاعدة السحابية عبر HermesSyncManager (push/pull-once)."""
    lines = []
    try:
        # سحب أوامر قادمة من السحابة (الجسر — لا يعارض قاعدة القراءة-only)
        pull = subprocess.run(
            [PY, str(ROOT / "cloud" / "supabase_sync.py"), "--pull-once"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        if pull.returncode != 0:
            lines.append(f"سحب السحابة فشل: {_tail(pull)}")
        else:
            try:
                data = json.loads(pull.stdout or "{}")
                lines.append(f"سحب السحابة ✓ (أوامر قادمة: {data.get('pending', '0')})")
            except Exception:
                lines.append("سحب السحابة ✓ (استجابة غير JSON)")
        # رفع مرآة الورشة للسحابة
        push = subprocess.run(
            [PY, str(ROOT / "cloud" / "supabase_sync.py"), "--push-once"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
        )
        if push.returncode != 0:
            lines.append(f"رفع السحابة فشل: {_tail(push)}")
        else:
            try:
                data = json.loads(push.stdout or "{}")
                lines.append(f"رفع السحابة ✓ (push_mirror: {data.get('status', data.get('pushed', '؟'))})")
            except Exception:
                lines.append("رفع السحابة ✓ (استجابة غير JSON)")
    except Exception as exc:
        lines.append(f"خطأ مزامنة السحابة: {type(exc).__name__}: {exc}")
    return " | ".join(lines)


# ----------------------------------------------------------------- sync report
def _git_behind_ahead() -> str:
    b = git("rev-list", "--count", "HEAD..origin/main")
    a = git("rev-list", "--count", "origin/main..HEAD")
    behind = (b.stdout or "0").strip()
    ahead = (a.stdout or "0").strip()
    return f"السحابة⇒محلي (متخلف {behind}) / محلي⇒السحابة (متقدم {ahead})"


def _laptop_activity() -> str:
    log = git("log", "--since=24 hours ago", "--format=%h %s", "--all", "--author=LAPTOP")
    rows = [r.strip() for r in (log.stdout or "").splitlines() if r.strip()]
    if not rows:
        return "لا نشاط لابتوب في آخر 24 ساعة"
    return f"نشاط لابتوب (آخر 24س): " + "; ".join(rows[:6])


def _workshop_activity() -> str:
    log = git("log", "--since=24 hours ago", "--format=%h %s", "--all", "--author=WORKSHOP")
    rows = [r.strip() for r in (log.stdout or "").splitlines() if r.strip()]
    if not rows:
        return "لا نشاط ورشة في آخر 24 ساعة"
    return f"نشاط ورشة (آخر 24س): " + "; ".join(rows[:6])


def build_report(sections: List[str]) -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    branch = (git("rev-parse", "--abbrev-ref", "HEAD").stdout or "main").strip()
    report = [
        ANCHOR,
        f"- تشغيل: {now} (عقدة {NODE})",
        f"- الفرع: {branch} — {_git_behind_ahead()}",
    ]
    report += [f"- {s.strip()}" for s in sections if s and s.strip()]
    report += ["---", ""]
    return "\n".join(report)


def append_state(report: str) -> None:
    """إلحاق التقرير في دفتر الحالة أسفل المرساة (لا نلمس سطوراً أخرى)."""
    try:
        existing = STATE_BOOK.read_text(encoding="utf-8") if STATE_BOOK.exists() else ""
        lines = existing.splitlines(keepends=True)
        # لو وُجدت المرساة سابقاً: نلحق بعدها مباشرة (أحدث تقرير فوق)
        idx = next((i for i, l in enumerate(lines) if l.strip().startswith(ANCHOR)), None)
        body = report + ["\n"] if not report.endswith("\n") else report
        if idx is None:
            # إلحاق في آخر الدفتر
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append("\n" + body)
        else:
            # بعد المرساة أزل أي أسطر تقارير قديمة حتى "---" ثم ضع الجديد
            end = idx + 1
            while end < len(lines) and not lines[end].strip().startswith("---"):
                end += 1
            lines[idx + 1:end] = [body]
        STATE_BOOK.write_text("".join(lines), encoding="utf-8")
        log("أُلحق تقرير المزامنة في RASED_SENTINEL_STATE.md ✓")
    except Exception as exc:
        log(f"فشل كتابة التقرير في الدفتر: {exc}", "ERROR")


# ----------------------------------------------------------------- main
def main() -> int:
    if not acquire_lock():
        return 0
    try:
        log(f"بدء المزامنة اليومية — العقدة {NODE}")
        sections = []
        sections.append(git_pull())
        sections.append(git_push())
        sections.append(cloud_sync())
        sections.append(_laptop_activity())
        sections.append(_workshop_activity())
        report = build_report(sections)
        append_state(report)
        log("اكتملت المزامنة اليومية ✓")
        return 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
