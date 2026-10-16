# -*- coding: utf-8 -*-
"""Marwa-Bot — Git auto-sync (pull + commit + push) — standing owner order 2026-10-16.

أمر المالك الدائم (2026-10-16): «دايمًا ارفع واسحب من جيت هب بدون الرجوع لي وبشكل دوري».
الغرض: مزامنة مستودع Marwa-Bot مع GitHub (كود + ذاكرة) تلقائيًا وبلا سؤال.

القواعد الآمنة:
- لا force-push ولا إعادة كتابة تاريخ أبدًا.
- عند تعارض rebase: يُلغى الـrebase بأمان ويُسجَّل، ولا يُرفع شيء.
- لا تُرفع أسرار ولا قواعد بيانات: فحص حاجز قبل الكوميت يلغي التجهيز لو ظهر
  أي ملف ممنوع (‎.env‎ / LAPTOP_SECRET_KIT.md / *.db / *.key ...) — إضافة إلى .gitignore.
- كل تشغيل يُسجَّل في logs/git_autosync.log، وقفل ملف واحد يمنع التشغيل المتزامن.

الاستخدام:
  python scripts/git_autosync.py                    # مرة واحدة
  python scripts/git_autosync.py --loop --interval 900
  python scripts/git_autosync.py --dry-run          # فحص بلا كتابة أو رفع
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "git_autosync.log"
LOCK_FILE = LOG_DIR / "git_autosync.lock"
LOCK_STALE_SECONDS = 1800

GIT = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"

FORBIDDEN_NAMES = {".env", "LAPTOP_SECRET_KIT.md"}
FORBIDDEN_SUFFIXES = (
    ".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3", ".dump",
    ".key", ".pem", ".p12", ".pickle", ".bak",
)

NODE_ID = os.environ.get("NODE_ID") or os.environ.get("COMPUTERNAME") or "WORKSHOP"


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{_stamp()}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def git(*args: str, timeout: int = 90) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [GIT, "-C", str(ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, env=env,
    )


def _tail(proc: subprocess.CompletedProcess, limit: int = 160) -> str:
    text = (proc.stderr or proc.stdout or "").strip().replace("\n", " | ")
    return text[-limit:]


# ----------------------------------------------------------------- lock
def _acquire_lock() -> bool:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            age = time.time() - LOCK_FILE.stat().st_mtime
            if age < LOCK_STALE_SECONDS:
                log(f"skip: another sync is running (lock age {int(age)}s)")
                return False
            log(f"stale lock ({int(age)}s) — removing and continuing")
            LOCK_FILE.unlink(missing_ok=True)
        except OSError:
            return False
    try:
        with LOCK_FILE.open("x", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {_stamp()}\n")
        return True
    except FileExistsError:
        log("skip: lock race lost")
        return False


def _release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


# ----------------------------------------------------------------- guard
def _staged_paths() -> List[str]:
    proc = git("diff", "--cached", "--name-only")
    return [p.strip() for p in (proc.stdout or "").splitlines() if p.strip()]


def _is_forbidden(path: str) -> bool:
    name = Path(path).name
    if name in FORBIDDEN_NAMES:
        return True
    return name.endswith(FORBIDDEN_SUFFIXES)


# ----------------------------------------------------------------- sync
def sync_once(dry_run: bool = False) -> int:
    if not (ROOT / ".git").exists():
        log("ERROR: not a git repository — abort")
        return 5
    if not Path(GIT).exists() and not shutil.which(GIT):
        log("ERROR: git executable not found — abort")
        return 5

    branch_proc = git("rev-parse", "--abbrev-ref", "HEAD")
    branch = (branch_proc.stdout or "").strip()
    if branch_proc.returncode != 0 or branch in ("", "HEAD"):
        log(f"skip: cannot resolve branch ({_tail(branch_proc)})")
        return 5
    remote = f"origin/{branch}"

    fetched = False
    fetch = git("fetch", "origin", "--prune", timeout=60)
    if fetch.returncode == 0:
        fetched = True
    else:
        log(f"offline/fetch failed (will still commit locally): {_tail(fetch)}")

    # --- pull (rebase, only when actually behind)
    if fetched:
        behind_proc = git("rev-list", "--count", f"HEAD..{remote}")
        try:
            behind = int((behind_proc.stdout or "0").strip() or "0")
        except ValueError:
            behind = 0
        if behind > 0:
            if dry_run:
                log(f"dry-run: {behind} commit(s) behind {remote} — would rebase")
            else:
                log(f"pull: {behind} commit(s) behind — rebase --autostash")
                pull = git("pull", "--rebase", "--autostash", "origin", branch, timeout=120)
                if pull.returncode != 0:
                    git("rebase", "--abort")
                    log(f"CONFLICT: rebase aborted, nothing pushed — {_tail(pull)}")
                    return 3
                log("pull: done")

    # --- stage everything (respects .gitignore)
    if dry_run:
        status = git("status", "--porcelain")
        changed = len([l for l in (status.stdout or "").splitlines() if l.strip()])
        log(f"dry-run: {changed} local change(s) — would stage/commit/push")
        return 0

    add = git("add", "-A")
    if add.returncode != 0:
        log(f"ERROR: git add failed — {_tail(add)}")
        return 4

    staged = _staged_paths()
    blocked = [p for p in staged if _is_forbidden(p)]
    if blocked:
        git("reset")
        log(f"ABORT: forbidden path(s) staged (secrets/data) — unstaged: {blocked[:5]}")
        return 4

    if staged:
        msg = f"auto-sync: {NODE_ID} @ {time.strftime('%Y-%m-%d %H:%M')}"
        commit = git("commit", "-m", msg)
        if commit.returncode != 0:
            log(f"ERROR: commit failed — {_tail(commit)}")
            return 4
        log(f"commit: {msg} ({len(staged)} file(s))")

    # --- push when ahead
    if fetched:
        ahead_proc = git("rev-list", "--count", f"{remote}..HEAD")
        try:
            ahead = int((ahead_proc.stdout or "0").strip() or "0")
        except ValueError:
            ahead = 1
    else:
        ahead = 1

    if ahead <= 0:
        log("up-to-date: nothing to push")
        return 0

    push = git("push", "origin", f"HEAD:{branch}", timeout=120)
    if push.returncode != 0:
        log(f"push FAILED (honest, will retry next cycle): {_tail(push)}")
        return 2

    log(f"push: OK ({ahead} commit(s) -> {remote})")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Marwa-Bot git auto-sync (pull/commit/push)")
    ap.add_argument("--loop", action="store_true", help="run forever")
    ap.add_argument("--interval", type=int, default=900, help="seconds between runs (default 900)")
    ap.add_argument("--dry-run", action="store_true", help="inspect only, no writes")
    args = ap.parse_args(argv)

    if args.loop:
        log(f"loop start: repo={ROOT} node={NODE_ID} interval={args.interval}s")
        while True:
            try:
                if _acquire_lock():
                    try:
                        code = sync_once(dry_run=False)
                        log(f"cycle result: {code}")
                    finally:
                        _release_lock()
            except Exception as exc:  # never die in loop mode
                log(f"cycle crashed (kept alive): {type(exc).__name__}: {exc}")
            time.sleep(max(60, args.interval))

    if args.dry_run:
        return sync_once(dry_run=True)

    if not _acquire_lock():
        return 0
    try:
        code = sync_once(dry_run=False)
    finally:
        _release_lock()
    log(f"result: {code}")
    return code


if __name__ == "__main__":
    sys.exit(main())