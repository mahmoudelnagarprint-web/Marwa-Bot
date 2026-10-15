# -*- coding: utf-8 -*-
"""Steering Bar (شريط التوجيه الطافي) — واجهة التحكم اللحظي للمالك أثناء تشغيل الوكلاء.
خفيفة ثابتة أعلى الشاشة (Always-on-Top):
- **خلاصة حية (Live Action Feed):** آخر ما ينفذه الوكيل حاليًا.
- **خانة توجيه سريع (Quick Input):** تكتب تعليمة/تصحيح وترسله للوكيل دون إلغاء المهمة.
- **Kill-Switch / Failsafe:** مفتاح Esc يوقف التنفيذ فورًا ويعيد التحكم اليدوي، أو سحب زاوية حمراء بالماوس.
- **زر Pause/Resume:** تجميد مؤقت واستئناف خطوة بخطوة (Step).
التصميم: لا إحداثيات مطلقة — كل العمليات عبر أحداث Tkinter، ولا يتدخل في كود الإنتاج.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import tkinter as tk
from tkinter import ttk

# مسارات ملفات الحالة (يقرأها/يكتبها system_worker والمرسلون)
STATE_FILE = Path(__file__).resolve().parent / "steering_state.json"
CONTROL_FILE = Path(__file__).resolve().parent / "steering_control.json"
FEED_POLL_MS = 400


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class SteeringBar:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.paused = False
        self.killed = False
        self._last_feed = ""

        # إعدادات النافذة
        self.root.title("مروة — شريط التوجيه")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)   # بلا إطار نظامي (فل عائم)
        self.root.geometry("+0+0")
        w = self.root.winfo_screenwidth()
        self.root.geometry(f"{w}x48+0+0")

        # خلفية داكنة بأناقة
        self.frame = tk.Frame(self.root, bg="#1e2430")
        self.frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # Live Action Feed (المؤشر الحالي)
        self.feed_label = tk.Label(
            self.frame,
            text="⏳ …",
            font=("Segoe UI", 11),
            anchor="w",
            bg="#1e2430",
            fg="#aad6ff",
            wraplength=w - 470,
            justify="left",
        )
        self.feed_label.pack(side=tk.LEFT, padx=(8, 8))

        # خانة التوجيه السريع (Quick Guide) + زر إرسال
        self.guide_var = tk.StringVar()
        self.guide_entry = tk.Entry(
            self.frame,
            textvariable=self.guide_var,
            font=("Segoe UI", 10),
            bg="#0f141c",
            fg="#e8f0ff",
            insertbackground="#aad6ff",
            relief=tk.FLAT, width=34,
        )
        self.guide_entry.pack(side=tk.LEFT, padx=4)
        self.guide_entry.bind("<Return>", self._send_guide)
        tk.Button(
            self.frame, text="إرسال", command=self._send_guide,
            bg="#2a6fdb", fg="white", activebackground="#2a6fdb",
            relief=tk.FLAT, padx=8,
        ).pack(side=tk.LEFT, padx=2)

        # Pause / Resume + Step
        self.pause_btn = tk.Button(
            self.frame, text="⏸ تجميد", command=self._toggle_pause,
            bg="#555c68", fg="white", activebackground="#555c68",
            relief=tk.FLAT, padx=6,
        )
        self.pause_btn.pack(side=tk.LEFT, padx=2)
        tk.Button(
            self.frame, text="▶ خطوة", command=self._step,
            bg="#555c68", fg="white", activebackground="#555c68",
            relief=tk.FLAT, padx=6,
        ).pack(side=tk.LEFT, padx=2)

        # Kill-Switch zone (يسار الشاشة، قابلة للسحب من الماوس)
        self.kill_zone = tk.Label(
            self.frame, text="🛑", font=("Segoe UI", 14),
            bg="#a1262e", fg="white", width=2, cursor="hand2",
        )
        self.kill_zone.pack(side=tk.RIGHT, padx=(4, 8))
        self.kill_zone.bind("<Button-1>", self._kill)

        # Esc يوقف التنفيذ فورًا
        self.root.bind("<Escape>", self._kill)

        self._feed_timer()
        self._last_control_state = _read_json(CONTROL_FILE, {})
        self._poll_control()

    # ---------------------------------------------------------- LIVE FEED
    def set_feed(self, text: str) -> None:
        """يعرض آخر ما ينفذه الوكيل (يُستدعى من system/ui عبر STATE_FILE)."""
        if text != self._last_feed:
            self._last_feed = text
            self.feed_label.config(text=f"⚙️ {text[:120]}")

    def _feed_timer(self) -> None:
        state = _read_json(STATE_FILE, {})
        feed = state.get("current_action") or "في انتظار أمر…"
        self.set_feed(feed)
        self.root.after(FEED_POLL_MS, self._feed_timer)

    # ---------------------------------------------------------- CONTROL
    def _write_control(self, **kwargs) -> None:
        data = _read_json(CONTROL_FILE, {})
        data.update(kwargs)
        data["timestamp"] = _now()
        _write_json(CONTROL_FILE, data)

    def _poll_control(self) -> None:
        state = _read_json(CONTROL_FILE, {})
        # عكس اتجاه كلمة 'paused' — الشريط يبين حقيقة الوكلاء
        if state.get("paused") and not self.paused:
            self.paused_locked = True
            self.pause_btn.config(text="⏸ تجميد", bg="#555c68")
        self.root.after(FEED_POLL_MS, self._poll_control)

    def _send_guide(self, event=None) -> None:
        text = self.guide_var.get().strip()
        if text:
            self._write_control(guide=text)
            self.guide_var.set("")
            # يعرض في الخلاصة ما أرسله
            self.set_feed(f"📨 توجيهك: {text[:80]}")
            print(f"[steering] GUIDE: {text}", flush=True)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.pause_btn.config(text="▶ استئناف" if self.paused else "⏸ تجميد")
        self._write_control(paused=self.paused, step=False)
        self.set_feed("⏸ مجمَّد" if self.paused else "▶ مستأنف")

    def _step(self) -> None:
        self._write_control(step=True)
        self.set_feed("▶ خطوة واحدة")

    def _kill(self, event=None) -> None:
        """Kill-Switch/Failsafe: يوقف التنفيذ فورًا ويعيد التحكم اليدوي."""
        self.killed = True
        try:
            self._write_control(kill=True)
            self.set_feed("🛑 أُوقِف يدويًا — تحكم المالك")
            self.root.after(500, self.root.destroy)
        finally:
            print("[steering] KILL", flush=True)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    root = tk.Tk()
    bar = SteeringBar(root)
    # مثال على إرسال توجيه سريع من سطر أوامر لاختبار:
    if len(sys.argv) > 1 and sys.argv[1] == "--test-guide":
        bar.set_feed("اختبار الشريط — انتظر 3 ثوان…")
        root.after(3000, root.destroy)
    bar.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
