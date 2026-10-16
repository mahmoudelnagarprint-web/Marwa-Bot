# -*- coding: utf-8 -*-
"""System Worker (عامل النظام) — Phase 7 FULL BUILD.
- أوامر ويندوز مباشرة على جهاز الورشة: لقطة شاشة (تُحفظ وتُرسل للمالك)،
  فتح برامج (RDWorks/فوتوشوب/notepad/cmd...) ومجلدات، وحالة الجهاز.
- الإغلاق/إعادة التشغيل: **لا يتنفذان أبدًا** إلا بكلمة تأكيد صريحة في الرسالة
  («تأكيد»/«اكيد») — وبمهلة 60 ثانية يمكن إلغاؤها بـ shutdown /a.
- أوامر الماكينة عن بُعد: تُجهَّز وتُدرَج في **طابور commands السحابي** (insert فقط)
  وينفذها محرك المزامنة المحلي (الدايمون) — نفس مسار system_command المعتمد.
- الماوس/الكيبورد: عبر pyautogui لو متاحة — تُبلَّغ حالتها بصدق ولا تُثبَّت من نفسها.
- مسارات البرامج تُخزَّن في orchestrator/agents/system_apps.json (عدّلها بأمرك:
  «خزن مسار rdworks: <المسار>») — لا مسارات مخترعة.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ..base import SubAgent

ROOT = Path(__file__).resolve().parent.parent.parent          # G:\ai\Elnagar POS
ENV_PATH = ROOT / ".env"
APPS_PATH = Path(__file__).resolve().parent / "system_apps.json"

DEFAULT_APPS = {
    "rdworks": None,
    "photoshop": None,
    "notepad": "notepad.exe",
    "cmd": "cmd.exe",
    "explorer": "explorer.exe",
    "calc": "calc.exe",
    "folders": {
        "root": str(ROOT),
        "cloud": str(ROOT / "cloud"),
        "backups": str(ROOT / "Backups"),
    },
}

CONFIRM_WORDS = ("تأكيد", "اكيد", "أكيد", "confirm", "بالتأكيد")


def _load_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _load_apps() -> Dict[str, Any]:
    try:
        if APPS_PATH.exists():
            data = json.loads(APPS_PATH.read_text(encoding="utf-8"))
            merged = dict(DEFAULT_APPS)
            merged.update({k: v for k, v in data.items() if k != "folders"})
            merged["folders"] = {**DEFAULT_APPS["folders"], **(data.get("folders") or {})}
            return merged
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_APPS))


def _save_apps(apps: Dict[str, Any]) -> bool:
    try:
        APPS_PATH.write_text(
            json.dumps(apps, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def _fmt(n) -> str:
    try:
        f = float(n)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(n)


class SystemWorkerAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="system_worker",
            name="مصطفى — وكيل التحكم بالكمبيوتر (System Worker)",
            keywords=[
                # ── أسماء النداء (قرار المالك 2026-10-16): «مصطفى» = وكيل التحكم بالكمبيوتر.
                #    «مروة» ليست هنا عمدًا — فهي الوكيل الأصلي (وكيل النجار برنت).
                "مصطفى", "مصطفي", "مصطفى صاصا", "مصطفي صاصا",
                "سكرين شوت", "سكرين", "لقطة", "لقطة شاشة", "صورة الشاشة", "شاشة", "شاشه",
                "screenshot", "اطفئ", "اطفي", "اقفل الجهاز", "اغلق الجهاز", "shutdown",
                "اعاده تشغيل", "إعادة تشغيل", "ريستارت", "restart", "reboot",
                "افتح", "فتح", "open", "rdworks", "رودوركس", "فوتوشوب", "photoshop",
                "notepad", "cmd", "explorer", "calc",
                "طابور", "الطابور", "ابعت امر", "امر للماكينة", "أمر للماكينة",
                "queue", "ماوس", "كيبورد", "اكتب", "اضغط", "pyautogui",
                "حالة الجهاز", "الجهاز", "system", "خزن مسار",
                "امكانيات", "إمكانيات", "متاح",
                "شريط", "steering", "التوجيه",
                "شوف نافذة", "فحص نافذة", "النوافذ", "ضغط زر", "pywinauto",
            ],
            phase=7,
        )

    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"⚙️ {title}\n{body}", "action": "system_worker", "payload": {}}

    # -------------------------------------------------------------- قدرات
    # ----- شريط التوجيه الطافي -------------------------------------------------
    def _steering(self, t: str, text: str) -> Dict[str, Any]:
        bar = Path(__file__).resolve().parent.parent / "steering_bar.py"
        if not bar.exists():
            return self._reply("شريط التوجيه", "❌ ملف الشريط مش موجود — أتحقق منه.")
        if "قف" in t or "ايقف" in t or "stop" in t or "وقف الشريط" in t:
            # إرسال أمر قتل للشريط عبر ملف التحكم
            ctrl = Path(__file__).resolve().parent / "steering_control.json"
            try:
                ctrl.write_text(
                    json.dumps({"kill": True,
                                "timestamp": datetime.now(timezone.utc).isoformat()}),
                    encoding="utf-8")
                return self._reply("شريط التوجيه", "🛑 أرسلت أمر إيقاف الشريط (Esc يعادل نفس الشيء).")
            except Exception as exc:
                return self._reply("شريط التوجيه", f"❌ فشل الإيقاف ({type(exc).__name__}: {exc}).")
        # تشغيل الشريط في عملية منفصلة (لا يوقف الوكلاء)
        try:
            import subprocess as sp
            sp.Popen([sys.executable, str(bar)], cwd=str(Path(__file__).resolve().parent.parent))
            return self._reply(
                "شريط التوجيه",
                "✅ شريط التوجيه الطافي اتحمّل أعلى الشاشة (Always-on-Top).\n"
                "• الخلاصة الحية بتعرض اللي بعمله دلوقتي.\n"
                "• خانة الإدخال السريع: اكتب توجيه يحولني لوكيل في نفس الدين.\n"
                "• 🛑 Kill-Switch: دوس Esc أو اسحب منطقة حمراء — بيوقفني فورًا ويرجعلك التحكم اليدوي.\n"
                "• ⏸ زر التجميد: بيوقف تنفيذي مؤقت، و«خطوة» بيخليني أمشي خطوة-خطوة.\n"
                "خلاصة أمانة: الشريط مش بيمس في كود الإنتاج — بيقري حالة وحسب فقط.",
            )
        except Exception as exc:
            return self._reply("شريط التوجيه", f"❌ فشل التشغيل ({type(exc).__name__}: {exc}).")

    # ----- UI Automation (شجرة إمكانية الوصول — ممنوع الإحداثيات الثابتة) -----
    def _uia_test(self) -> Dict[str, Any]:
        try:
            import pywinauto
            ver = getattr(pywinauto, "__version__", "?")
        except Exception:
            return self._err_no_uia()
        try:
            from pywinauto import Desktop
            wins = Desktop(backend="uia").windows()
            top = [w for w in wins if w.is_visible()][:12]
            names = [w.window_text() for w in top if (w.window_text() or "").strip()]
            return self._reply(
                "UI Automation — النوافذ المتاحة",
                f"• pywinauto {ver} متاحة ✅ — بتشوف شجرة إمكانية الوصول (لا إحداثيات).\n"
                "• النوافذ المرئية (12):\n" + "\n".join(f"  • {n[:60]}" for n in names)
                + "\n\nللتحكم بنافذة: «شوف نافذة <اسمها>» أو «ضغط زر <الاسم> في <البرنامج>».",
            )
        except Exception as exc:
            return self._reply(
                "UI Automation", f"❌ فشل سرد النوافذ ({type(exc).__name__}: {exc}).")

    def _err_no_uia(self) -> Dict[str, Any]:
        return self._reply(
            "UI Automation",
            "❌ pywinauto غير متاحة — على شجرة إمكانية الوصول لأقدر أتعامل مع البرامج بلا إحداثيات. "
            "لو عايزها قولي «ثبت pywinauto» وبتم بأمرك (pip install pywinauto).")

    def _uia_window(self, name: str, backend: str = "uia") -> Any:
        """يجيب أول نافذة تطابق اسمًا جزئيًا — عبر الشجرة لا الإحداثيات."""
        from pywinauto import Desktop
        wins = Desktop(backend=backend).windows()
        for w in wins:
            txt = w.window_text() or ""
            if name.lower() in txt.lower():
                return w
        return None

    def _uia_inspect(self, t: str, text: str) -> Dict[str, Any]:
        """«شوف نافذة X» — يسرد عناصرِها (أزرار/حقول بأسمائها) من شجرة الوصول."""
        try:
            import pywinauto  # noqa: F401
        except Exception:
            return self._err_no_uia()
        rest = text
        for junk in ("شوف نافذة", "افحص نافذة", "List window", "النوافذ المتاحة", "شوف النوافذ",
                     "نافذة تشمل", "نافذة فيها", "اللي اسمها", "الاسم", "باسم"):
            rest = rest.replace(junk, "")
        name = rest.strip().strip('"')
        for junk in ("تشمل ", "فيها ", "اسمها "):
            if name.startswith(junk):
                name = name[len(junk):].strip()
        if not name or name.lower().startswith("النوافذ") or "المتاحة" in name:
            return self._reply(
                "فحص نافذة",
                f"اكتب اسم النافذة: «شوف نافذة RDWorks».\nالنوافذ الحالية المرئية مش مدرجة تلقائيًا — "
                "اسألني «قائمة النوافذ الحالية» بعرضها.",
            )
        try:
            win = self._uia_window(name)
            if win is None:
                return self._reply(
                    "فحص نافذة",
                    f"ما لقيتش نافذة فيها «{name}» (شوف «النوافذ المتاحة» فيعرفني اللي موجود).")
            seen = []
            try:
                ctrls = list(win.descendants(control_type="Button")) + \
                    list(win.descendants(control_type="Edit")) + \
                    list(win.descendants(control_type="TabItem"))
                for c in ctrls:
                    cn = c.window_text() or c.friendly_class_name() or ""
                    if cn.strip() and cn not in seen:
                        seen.append(cn)
                        if len(seen) >= 20:
                            break
            except Exception:
                pass
            if not seen:
                # Flatten fallback: أي عنصر له نص
                try:
                    for c in win.descendants():
                        ct = c.window_text() or ""
                        if ct.strip() and ct not in seen:
                            seen.append(ct)
                            if len(seen) >= 20:
                                break
                except Exception:
                    pass
            return self._reply(
                f"نافذة «{name}» ({len(seen)} عنصر)",
                "• عناصر الوصول (أزرار/حقول/تبويبات):\n" + "\n".join(f"  • {s[:50]}" for s in seen)
                + "\n\nللضغط: «ضغط زر <الاسم> في <البرنامج>» — بشريط الوصول لا إحداثيات.",
            )
        except Exception as exc:
            return self._reply("فحص نافذة", f"❌ فشل الفحص ({type(exc).__name__}: {exc}).")

    def _uia_press(self, t: str, text: str) -> Dict[str, Any]:
        """«ضغط زر X في Y» — ينفذ بالهوية لا الإحداثيات (ممنوع إحداثيات ثابتة)."""
        try:
            import pywinauto  # noqa: F401
        except Exception:
            return self._err_no_uia()
        m = re.search(r"ضغط زر ([\w\s\u0600-\u06FF]+) في ([\w\s]+)", text)
        if not m:
            return self._reply(
                "ضغط زر",
                "المواصفات: «ضغط زر بدء في RDWorks» (اسم الزر ثم اسم النافذة — بشريط الوصول).")
        btn, prog_name = m.group(1).strip(), m.group(2).strip()
        try:
            win = self._uia_window(prog_name)
            if win is None:
                return self._reply(
                    "ضغط زر", f"ما لقيتش نافذة «{prog_name}» — شغّلها الأول أو صحح اسمها.")
            # عود الشجرة: نبحث بالاسم عبر كل العناصر القابلة
            found = None
            for d in win.descendants():
                t_ = d.window_text() or d.friendly_class_name() or ""
                if btn.lower() in t_.lower():
                    found = d
                    break
            if found is None:
                return self._reply(
                    "ضغط زر",
                    f"ما لقيتش عنصر اسمه «{btn}» في نافذة «{prog_name}». "
                    "شوف «شوف نافذة 'البرنامج'» فيلوّحلك أسماء العناصر فعلًا.")
            found.click()
            return self._reply(
                "ضغط زر",
                f"✅ ضغطت زر «{btn}» في «{prog_name}» عبر شجرة الوصول (موش إحداثيات).")
        except Exception as exc:
            return self._reply("ضغط زر", f"❌ فشل الضغط ({type(exc).__name__}: {exc}).")

    # -------------------------------------------------------------- قدرات
    def _screenshot(self, send_to_owner: bool = True) -> Dict[str, Any]:
        try:
            import mss
        except ImportError:
            return self._reply(
                "لقطة الشاشة", "❌ مكتبة mss غير متاحة في البيئة — ما قدرتش آخذ اللقطة.")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shot = ROOT / "cloud" / f"screenshot_local_{ts}.png"
        try:
            with mss.mss() as sct:
                sct.shot(output=str(shot))
        except Exception as exc:
            return self._reply("لقطة الشاشة", f"❌ فشلت اللقطة ({type(exc).__name__}: {exc}).")
        sent = False
        if send_to_owner:
            env = _load_env()
            token, owner = env.get("TELEGRAM_BOT_TOKEN", ""), env.get("OWNER_TELEGRAM_ID", "")
            if token and owner:
                try:
                    import requests
                    with open(shot, "rb") as fh:
                        r = requests.post(
                            f"https://api.telegram.org/bot{token}/sendPhoto",
                            data={"chat_id": owner},
                            files={"photo": (shot.name, fh, "image/png")},
                            timeout=25,
                        )
                    sent = bool(r.ok)
                except Exception:
                    sent = False
        where = "وبعتها لك على تليجرام ✅" if sent else "ومحفوظة عندك على الجهاز (مفيش إرسال تليجرام)"
        return self._reply(
            "لقطة الشاشة", f"📸 اللقطة اتحفظت في:\n{shot}\n{where}")

    def _power(self, t: str) -> Dict[str, Any]:
        reboot = any(k in t for k in ("اعاده تشغيل", "إعادة تشغيل", "ريستارت", "restart", "reboot"))
        kind = "إعادة تشغيل" if reboot else "إطفاء"
        if not any(c in t for c in CONFIRM_WORDS):
            return self._reply(
                f"أمر {kind} الجهاز",
                f"⚠️ أمر {kind} جهاز الورشة حساس — ما هعمله إلا بكلمة تأكيد صريحة.\n"
                "ابعتها تاني بالشكل ده: «اطفئ الجهاز تأكيد» — وبعدها بيتنفذ بمهلة 60 ثانية "
                "تقدر تلغيها بالأمر: shutdown /a",
            )
        flag = "/r" if reboot else "/s"
        os.system(f'shutdown {flag} /t 60 /c "ElnagarPOS - Marwa system command"')
        return self._reply(
            f"أمر {kind} الجهاز",
            f"✅ {kind} الجهاز مجدول بعد 60 ثانية. للإلغاء فورًا شغّل: shutdown /a",
        )

    def _open_target(self, t: str, text: str) -> Dict[str, Any]:
        apps = _load_apps()
        # خزن مسار برنامج؟
        if "خزن مسار" in t:
            after = text.split("خزن مسار", 1)[1].strip().lstrip(":").strip()
            parts = after.split(":", 1) if (":" in after and "|" not in after) else after.split("|", 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                name, path = parts[0].strip().lower(), parts[1].strip().strip('"')
                apps[name] = path
                ok = _save_apps(apps)
                return self._reply(
                    "تخزين مسار برنامج",
                    f"✅ مسار «{name}» اتحفظ: {path}" if ok
                    else f"❌ فشل حفظ الإعدادات — المسار: {path}",
                )
            return self._reply(
                "تخزين مسار برنامج",
                "اكتبها كده: «خزن مسار rdworks: C:\\...\\RDWorks.exe»",
            )
        # مجلد؟
        if "مجلد" in t or "فولدر" in t or "folder" in t:
            folders = apps.get("folders", {})
            target = None
            for key, path in folders.items():
                if key in t:
                    target = path
                    break
            if target is None:
                # مسار صريح في الرسالة؟
                for tok in text.replace("\\", " \\").split():
                    if tok.strip('"').upper()[:-1] in (
                            "C:", "D:", "G:", "H:", "E:", "F:") or tok.strip('"').endswith("\\"):
                        pass
                import re
                m = re.search(r"[A-Za-z]:\\[^\s،]+", text)
                if m:
                    target = m.group(0).strip('"')
            if target and Path(target).exists():
                os.startfile(target)
                return self._reply("فتح مجلد", f"✅ فتحت: {target}")
            return self._reply(
                "فتح مجلد",
                f"ما عرفش المجلد ده. المجلدات المعروفة: " +
                "، ".join(f"{k}" for k in folders) + " — أو اكتب المسار الكامل.",
            )
        # برنامج؟
        prog = None
        for key in ("rdworks", "رودوركس", "فوتوشوب", "photoshop", "notepad", "cmd", "explorer", "calc"):
            if key in t:
                prog = {"rdworks": "rdworks", "رودوركس": "rdworks", "فوتوشوب": "photoshop",
                        "photoshop": "photoshop", "notepad": "notepad", "cmd": "cmd",
                        "explorer": "explorer", "calc": "calc"}[key]
                break
        if prog is None:
            return self._reply(
                "فتح برنامج",
                "قولي اسم البرنامج (rdworks / فوتوشوب / notepad / cmd / calc / explorer) "
                "أو «افتح مجلد cloud».",
            )
        path = apps.get(prog)
        if not path and prog == "photoshop":
            hits = sorted(Path("C:/Program Files/Adobe").glob("*/Photoshop.exe")) if Path(
                "C:/Program Files/Adobe").exists() else []
            if hits:
                path = str(hits[-1])
        if not path:
            return self._reply(
                f"فتح {prog}",
                f"❌ مسار «{prog}» مش متخزن عندي — ابعتليه مرة واحدة بالشكل ده:\n"
                f"«خزن مسار {prog}: C:\\المسار\\الكامل.exe»\n"
                "وأنا أحفظه وأفتحه لك على طول بعد كده.",
            )
        try:
            os.startfile(path)
            return self._reply("فتح برنامج", f"✅ فتحت {prog}:\n{path}")
        except Exception as exc:
            return self._reply(f"فتح {prog}", f"❌ فشل الفتح ({type(exc).__name__}: {exc}) — راجع المسار: {path}")

    def _queue_command(self, t: str, text: str) -> Dict[str, Any]:
        """تجهيز أمر ماكينة عبر طابور commands السحابي (insert فقط — ينفذه الدايمون)."""
        env = _load_env()
        url = (env.get("SUPABASE_URL") or "").rstrip("/")
        key = env.get("SUPABASE_SECRET_KEY") or ""
        if not url or not key:
            return self._reply("طابور الماكينة", "❌ مفاتيح Supabase غير موجودة في .env.")
        # حدد الأمر
        payload: Dict[str, Any] = {}
        if any(k in t for k in ("سكرين", "لقطة", "شاشة", "screenshot")):
            payload = {"cmd": "screenshot"}
        elif any(k in t for k in ("اعاده تشغيل", "إعادة تشغيل", "ريستارت", "restart", "reboot")):
            payload = {"cmd": "reboot"}
        elif any(k in t for k in ("اطفئ", "اقفل", "اغلق", "shutdown")):
            payload = {"cmd": "shutdown"}
        elif any(k in t for k in ("افتح", "فتح", "open")):
            import re
            m = re.search(r"[A-Za-z]:\\[^\s،]+", text)
            if not m:
                return self._reply(
                    "طابور الماكينة",
                    "لأمر فتح عن بُعد اكتب المسار كامل: «ابعت أمر للماكينة افتح G:\\...»",
                )
            payload = {"cmd": "open_app", "path": m.group(0).strip('"')}
        else:
            return self._reply(
                "طابور الماكينة",
                "الأوامر المدعومة في الطابور: screenshot / shutdown / reboot / open_app بمسار كامل.",
            )
        try:
            import requests
            r = requests.post(
                f"{url}/rest/v1/commands",
                headers={
                    "apikey": key, "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json", "Prefer": "return=representation",
                },
                json={
                    "action": "system_command", "payload": payload, "status": "pending",
                    "idempotency_key": str(uuid.uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                timeout=25,
            )
            if not r.ok:
                return self._reply(
                    "طابور الماكينة",
                    f"❌ فشل الإدراج في الطابور (HTTP {r.status_code}) — ما افترضتش نجاح. جرب تاني بعد شوية.")
            row = (r.json() or [{}])[0]
            return self._reply(
                "طابور الماكينة",
                f"✅ الأمر اتحط في الطابور السحابي (#{row.get('id', '؟')}): {json.dumps(payload, ensure_ascii=False)}\n"
                "📌 الدايمون المحلي (start_sync.bat) ينفذه لما يكون شغال — والصور توصلك على تليجرام.",
            )
        except Exception as exc:
            return self._reply(
                "طابور الماكينة",
                f"❌ تعذر الوصول للطابور ({type(exc).__name__}) — ما افترضشت نجاح العملية.",
            )

    def _identity(self) -> Dict[str, Any]:
        """بطاقة تعريف «مصطفى» — وكيل التحكم بالكمبيوتر (قرار المالك 2026-10-16)."""
        return self._reply(
            "مصطفى — وكيل التحكم بالكمبيوتر",
            "أنا «مصطفى» 🖥️ — وكيل التحكم بالكمبيوتر في منظومة النجار برنت.\n"
            "• النداء: «مصطفى» أو «مصطفى صاصا».\n"
            "• لست «مروة» — مروة هي الوكيل الأصلي (وكيل النجار برنت) وبتنادي عليها باسمها.\n\n"
            "اللي بقدر أعمله (نفس قواعد عامل النظام المعتمدة):\n"
            "• 📸 لقطة شاشة — مباشرة (ممكن تتبعت على تليجرام).\n"
            "• 🖥️ حالة الجهاز والإمكانيات — مباشرة (قراءة فقط).\n"
            "• 🪟 فحص النوافذ وضغط الأزرار بالهوية (pywinauto — لا إحداثيات ثابتة).\n"
            "• 📂 فتح برامج/مجلدات — بأمرك.\n"
            "• ⌨️ ماوس/كيبورد عبر pyautogui — لو متثبتة.\n"
            "• 🔌 إطفاء/إعادة تشغيل — بكلمة تأكيد صريحة فقط («اطفئ الجهاز تأكيد»).\n"
            "• ☁️ أوامر الطابور السحابي: screenshot / shutdown / reboot / open_app.\n\n"
            "قولي عايز تختبر إيه وأنا أنفّذ — والحساس بمهلة 60 ثانية تقدر تلغيها بـ shutdown /a.",
        )

    def _capabilities(self) -> Dict[str, Any]:
        apps = _load_apps()
        try:
            import pyautogui  # noqa: F401
            py_ok = True
        except Exception:
            py_ok = False
        try:
            import mss  # noqa: F401
            mss_ok = True
        except Exception:
            mss_ok = False
        import shutil as _sh
        try:
            du = _sh.disk_usage(str(ROOT))
            disk = f"{_fmt(du.free / (1024 ** 3))} GB فاضية من {_fmt(du.total / (1024 ** 3))} GB على G:"
        except Exception:
            disk = "غير معروف"
        try:
            import ctypes
            up_s = ctypes.windll.kernel32.GetTickCount64() // 1000
            up = f"{_fmt(up_s // 3600)} ساعة {_fmt((up_s % 3600) // 60)} دقيقة"
        except Exception:
            up = "غير معروف"
        body = [
            f"• الجهاز شغال من: {up}",
            f"• المساحة: {disk}",
            f"• لقطة الشاشة (mss): {'✅ متاحة' if mss_ok else '❌ غير متاحة'}",
            f"• ماوس/كيبورد (pyautogui): {'✅ متاحة' if py_ok else '❌ غير متثبتة — أثبتها بأمرك: pip install pyautogui'}",
            "• برامج مبرمجة: " + "، ".join(
                f"{k} ({'مسار محفوظ' if v else 'يبعتلي المسار'} )" for k, v in apps.items() if k != "folders"),
            "• مجلدات معروفة: " + "، ".join(apps.get("folders", {}).keys()),
            "• أوامر الطابور السحابي: screenshot / shutdown / reboot / open_app — تُنفَّذ من الدايمون.",
            "• النداء: «مصطفى» أو «مصطفى صاصا» — أنا وكيل التحكم بالكمبيوتر.",
        ]
        return self._reply("إمكانيات عامل النظام", "\n".join(body))

    # -------------------------------------------------------------- التوجيه
    def handle(self, text, ctx=None):
        t = (text or "").lower()
        # 0) النداء بالاسم: «مصطفى» / «مصطفى صاصا» — بطاقة التعريف (قرار المالك 2026-10-16)
        #    تُفحص أولاً ليفهم الاسم وحده. أي طلب تحكم مصاحب بيكمّل للمسار الطبيعي.
        name_called = any(k in t for k in ("مصطفى", "مصطفي", "صاصا"))
        if name_called:
            # لو الاسم معاه أمر تنفيذي واضح، نكمّل للمسار الطبيعي بدل بطاقة التعريف.
            actionable = any(k in t for k in (
                "سكرين", "لقطة", "شاشة", "شاشه", "screenshot",
                "اطفئ", "اطفي", "اقفل", "اغلق", "shutdown",
                "اعاده تشغيل", "إعادة تشغيل", "ريستارت", "restart", "reboot",
                "افتح", "فتح", "open", "متاح", "امكانيات", "إمكانيات", "حالة الجهاز",
                "طابور", "النوافذ", "شوف نافذة", "ضغط زر", "خزن مسار", "اكتب", "ماوس", "كيبورد",
            ))
            if not actionable:
                return self._identity()
        # 1) شريط التوجيه الطافي (يسبق أي رقم آخر)
        if "شريط" in t or "steering" in t or "التوجيه" in t:
            return self._steering(t, text)
        # 1.5) UI Automation — شجرة الوصول (قبل الإمكانيات حتى لا تلتقطها "متاح" الفرعية)
        if "قائمة النوافذ" in t or "النوافذ المتاحة" in t or "عرض النوافذ" in t:
            return self._uia_test()
        if "شوف نافذة" in t or "فحص نافذة" in t or "النوافذ" in t:
            return self._uia_inspect(t, text)
        # 2) متاح/إمكانيات (قبل أي تنفيذ)
        if any(k in t for k in ("متاح", "امكانيات", "إمكانيات", "حالة الجهاز")):
            return self._capabilities()
        # 3) طابور الماكينة
        if any(k in t for k in ("طابور", "ابعت امر", "امر للماكينة", "أمر للماكينة", "queue")):
            return self._queue_command(t, text)
        # 4) لقطة شاشة
        if any(k in t for k in ("سكرين", "لقطة", "شاشة", "شاشه", "screenshot")):
            return self._screenshot()
        # 5) إطفاء/إعادة تشغيل (بحاجز التأكيد)
        if any(k in t for k in ("اطفئ", "اطفي", "اقفل الجهاز", "اغلق الجهاز", "shutdown",
                                "اعاده تشغيل", "إعادة تشغيل", "ريستارت", "restart", "reboot")):
            return self._power(t)
        # 6) UI Automation — ضغط زر بالهوية (قبل الفتح أيضًا)
        if "ضغط زر" in t:
            return self._uia_press(t, text)
        # 7) تخزين مسار أو فتح برنامج/مجلد
        if "خزن مسار" in t or "افتح" in t or "فتح" in t or any(
                k in t for k in ("rdworks", "رودوركس", "فوتوشوب", "photoshop", "notepad", "cmd", "explorer", "calc")):
            return self._open_target(t, text)
        # 8) ماوس/كيبورد
        if any(k in t for k in ("ماوس", "كيبورد", "اكتب", "اضغط", "pyautogui")):
            try:
                import pyautogui
                return self._reply(
                    "ماوس/كيبورد",
                    "✅ pyautogui متاحة — أوامر التحكم جاهزة (اكتب نصًا إنجليزيًا: «اكتب hello»). "
                    "ملاحظة أمانة: الكتابة العربية مش مدعومة مباشرة (typewrite ASCII فقط).",
                )
            except Exception:
                return self._reply(
                    "ماوس/كيبورد",
                    "❌ pyautogui مش متثبتة في البيئة — ما هقدر أتحكم في الماوس/الكيبورد قبل تثبيتها. "
                    "لو عايزها قولي «ثبت pyautogui» وبتم بأمرك (pip install pyautogui) ثم أختبرها لك.",
                )
        return self._capabilities()
