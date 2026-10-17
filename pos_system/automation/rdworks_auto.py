# -*- coding: utf-8 -*-
"""
RDWorks Auto — Sasa RPA Prototype (Phase 1)
===========================================
النموذج الأولي لأتمتة برنامج RDWorks على كمبيوتر الورشة (WORKSHOP_PC).

القدرات الحالية (Phase 1):
    check    : يتحقق من المكتبات ومسار RDWorks — بدون فتح البرنامج.
    launch   : يفتح RDWorks وينتظر ظهور الشاشة الرئيسية.
    status   : هل RDWorks مفتوح الآن؟ يعرض نوافذه.

المرحلة القادمة (Phase 2 — لم تُنفَّذ بعد بأمر صريح):
    استيراد ملفات الليزر (.rd/.dxf) والضغط على زر Start بنفسه.

ترتيب اكتشاف المسار (بصدق — لا مسارات مخترعة):
    1) orchestrator/agents/system_apps.json (المفتاح "rdworks")
    2) مسارات مرشحة معروفة (C:\\RDWorksV8\\RDWorksV8.exe ...)
    3) فحص اختصارات Desktop/Start Menu عبر PowerShell
    إن لم يُوجد شيء → تقرير صريح وخروج برمز 1.

أكواد الخروج: 0 نجاح | 1 المسار غير موجود | 2 فشل الفتح | 3 مهلة انتظار الشاشة | 4 مكتبات ناقصة

تشغيل:
    python pos_system\\automation\\rdworks_auto.py check
    python pos_system\\automation\\rdworks_auto.py launch --wait 60
    python pos_system\\automation\\rdworks_auto.py status
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# إخراج UTF-8 على كونسول ويندوز (عشان الرسائل العربية)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]  # G:\ai\Naggar Print POS Agent
APPS_JSON = REPO_ROOT / "orchestrator" / "agents" / "system_apps.json"

# العنوان الحقيقي المكتشف لنافذة RDWorks الرئيسية على جهاز الورشة: «V8.00.32-[Blank]»
# أي: رقم إصدار V8.x.x ثم اسم الملف المفتوح بين قوسين — ولا يحتوي كلمة RDWorks أصلاً!
# لذلك نطابق النمطين معاً: كلمة rdworks (لو ظهرت) أو نمط Vإصدار-[ملف].
WINDOW_TITLE_RE = re.compile(r"(rdworks|^v\d+\.\d+\.\d+\s*-\s*\[)", re.IGNORECASE)
POLL_INTERVAL = 1.0       # ثانية بين كل محاولة رصد
STABLE_CONFIRM = 3.0      # ثوانٍ إعادة التأكد أن النافذة ثابتة (لتجنب شاشة الـ Splash)

CANDIDATE_PATHS = [
    r"C:\RDWorksV8\RDWorksV8.exe",
    r"C:\newpr\RDWorksV8.exe",
    r"C:\Program Files (x86)\RDWorksV8\RDWorksV8.exe",
    r"C:\Program Files\RDWorksV8\RDWorksV8.exe",
    r"D:\RDWorksV8\RDWorksV8.exe",
]

PS_SHORTCUT_SCAN = r"""
$sh = New-Object -ComObject WScript.Shell
$dirs = @(
  ($env:USERPROFILE + '\Desktop'),
  ($env:PUBLIC + '\Desktop'),
  ($env:APPDATA + '\Microsoft\Windows\Start Menu'),
  ($env:ProgramData + '\Microsoft\Windows\Start Menu')
)
Get-ChildItem $dirs -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
  $t = $sh.CreateShortcut($_.FullName).TargetPath
  if ($_.Name -match 'RDWorks' -or $t -match 'RDWorks') {
    Write-Output ($_.FullName + '|' + $t)
  }
}
"""


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_apps() -> dict:
    """يقرأ system_apps.json المشترك مع system_worker.py — بصمت لو ناقص."""
    try:
        return json.loads(APPS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rdworks_windows():
    """كل النوافذ المطابقة لعنوان RDWorks (كلمة rdworks أو نمط Vإصدار-[ملف])."""
    import pygetwindow as gw
    return [w for w in gw.getAllWindows() if WINDOW_TITLE_RE.search(w.title or "")]


def find_rdworks_exe() -> str | None:
    """يكتشف مسار RDWorks: system_apps.json ← مرشح معروف ← فحص الاختصارات."""
    # 1) الإعدادات المشتركة
    stored = str(load_apps().get("rdworks") or "").strip()
    if stored and Path(stored).is_file():
        log(f"مصدر المسار: system_apps.json → {stored}")
        return stored

    # 2) المسارات المرشحة المعروفة
    for cand in CANDIDATE_PATHS:
        if Path(cand).is_file():
            log(f"مصدر المسار: مرشح معروف → {cand}")
            return cand

    # 3) فحص الاختصارات
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_SHORTCUT_SCAN],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except Exception as exc:
        log(f"⚠️ فشل فحص الاختصارات: {exc}")
        out = ""
    for line in out.splitlines():
        target = line.split("|", 1)[-1].strip()
        if target and Path(target).is_file():
            log(f"مصدر المسار: اختصار → {target}")
            return target

    return None


def cmd_check() -> int:
    log("وضع: check — التحقق من المكتبات والمسار (بدون فتح البرنامج).")
    try:
        import pywinauto  # noqa: F401
        import pyautogui  # noqa: F401
        import mouseinfo  # noqa: F401
        import pygetwindow  # noqa: F401
        log(f"✅ المكتبات جاهزة: pywinauto {pywinauto.__version__} | pyautogui {pyautogui.__version__}")
    except Exception as exc:
        log(f"❌ مكتبات ناقصة: {exc}")
        return 4

    exe = find_rdworks_exe()
    if not exe:
        log("❌ مسار RDWorks غير موجود — قولي إيه مرة واحدة: «خزن مسار rdworks: ...»")
        return 1
    log(f"✅ RDWorks موجود: {exe}")

    wins = rdworks_windows()
    log(f"نوافذ RDWorks مفتوحة الآن: {len(wins)}")
    return 0


def cmd_status() -> int:
    wins = rdworks_windows()
    if not wins:
        log("RDWorks غير مفتوح حالياً.")
        return 1
    for w in wins:
        log(f"نافذة: «{w.title}» | left={w.left} top={w.top} size={w.width}x{w.height}")
    return 0


def cmd_launch(wait: int) -> int:
    # مفتوح أصلاً؟ لا نفتح نسخة ثانية
    already = rdworks_windows()
    if already:
        log("RDWorks مفتوح بالفعل — لن أفتح نسخة ثانية.")
        for w in already:
            log(f"نافذة: «{w.title}»")
        return 0

    exe = find_rdworks_exe()
    if not exe:
        log("❌ مسار RDWorks غير موجود.")
        return 1

    log(f"جاري الفتح: {exe}")
    try:
        subprocess.Popen([exe], cwd=str(Path(exe).parent))
    except Exception as exc:
        log(f"❌ فشل الفتح: {exc}")
        return 2

    log(f"في انتظار الشاشة الرئيسية (حد أقصى {wait} ثانية)…")
    deadline = time.time() + wait
    while time.time() < deadline:
        wins = rdworks_windows()
        if wins:
            # إعادة تأكيد: نستبعد شاشة البداية المؤقتة (Splash)
            time.sleep(STABLE_CONFIRM)
            stable = rdworks_windows()
            if stable:
                w = stable[0]
                log(f"✅ الشاشة الرئيسية ظهرت واستقرت: «{w.title}»")
                log(f"الموضع: left={w.left}, top={w.top}, المقاس: {w.width}x{w.height}")
                log("Phase 1 مكتملة — السكريبت جاهز للمرحلة 2 (استيراد الملفات + Start).")
                return 0
        time.sleep(POLL_INTERVAL)

    log("⏱ انتهت المهلة دون ظهور الشاشة الرئيسية.")
    return 3


def main() -> None:
    ap = argparse.ArgumentParser(description="RDWorks Automation Prototype — Sasa RPA Phase 1")
    ap.add_argument("mode", nargs="?", default="check", choices=["check", "launch", "status"],
                    help="check=تحقق فقط | launch=افتح وانتظر | status=حالة النوافذ")
    ap.add_argument("--wait", type=int, default=60, help="أقصى انتظار للشاشة الرئيسية بالثواني (الافتراضي 60)")
    args = ap.parse_args()

    if args.mode == "launch":
        sys.exit(cmd_launch(args.wait))
    if args.mode == "status":
        sys.exit(cmd_status())
    sys.exit(cmd_check())


if __name__ == "__main__":
    main()
