#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ماسح الجرد الخام (task-2) — يُنتج ملف الأدلة الكامل لجدول الجرد.

يمشي على جذرَي المنظومة ويطبع كل سطر يطابق نمط مصادر البيانات:
    pos_data | jdbc:sqlite | sqlite3.connect | sqlite:// | localhost:5432 | layan_erp

يُخرج ملف ``config/inventory_raw.txt`` (+ ملخص بعدّادات) ويستثني:
    .venv / .git / node_modules / build / __pycache__ / dist / .gradle / tools (JDK)

الاستخدام:  python tools\\inventory_scan.py
"""

from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

VISION_LAB = Path(__file__).resolve().parent.parent
CONFIG_DIR = VISION_LAB / "config"
OUT_FILE = CONFIG_DIR / "inventory_raw.txt"

ROOTS = [
    Path(r"G:\ai\Naggar Print POS Agent"),
    Path(r"G:\ai\Elnagar POS"),
]

EXCLUDE_DIRS = {".venv", ".git", "node_modules", "build", "__pycache__", "dist",
                ".gradle", "java-1.8.0-openjdk-1.8.0.392-1.b08.redhat.windows.x86_64",
                "tools", "target", ".mvn", "venv", ".aider.tags.cache.v4"}
EXCLUDE_NAMES = {"inventory_raw.txt"}

PATTERN = re.compile(r"pos_data|jdbc:sqlite|sqlite3\.connect|sqlite://|localhost:5432|layan_erp")
EXTS = {".py", ".md", ".json", ".txt", ".sql", ".yml", ".yaml", ".properties", ".dart",
        ".gs", ".env", ".example", ".ps1", ".bat", ".cfg", ".toml", ".js", ".ts"}


def _setup_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def scan() -> int:
    hits: list[tuple[str, int, str]] = []
    per_file: Counter = Counter()
    skipped_roots: list[str] = []

    for root in ROOTS:
        if not root.exists():
            skipped_roots.append(str(root))
            continue
        # os.walk مع تجاهل أخطاء المسارات الطويلة/المحذوفة (bundleLibRuntimeToDirDebug...)
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if name in EXCLUDE_NAMES or path.suffix.lower() not in EXTS:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if PATTERN.search(line):
                        hits.append((str(path), i, line.strip()[:400]))
                        per_file[str(path)] += 1

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# جرد خام لمصادر البيانات — task-2 (مُولَّد آلياً بواسطة tools/inventory_scan.py)",
        f"# عدد السطور المطابقة: {len(hits)} | عدد الملفات: {len(per_file)}",
        "# file | line | النص",
        "",
    ]
    lines += [f"{f} | {n} | {t}" for f, n, t in hits]
    lines += ["", "# ── ملخص بعدد المطابقات لكل ملف ──"]
    lines += [f"{n:>4}  {f}" for f, n in per_file.most_common()]
    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"المطابقات   : {len(hits)}")
    print(f"الملفات     : {len(per_file)}")
    print(f"ملف الأدلة  : {OUT_FILE}")
    if skipped_roots:
        print(f"جذور غير موجودة (تُخطى): {skipped_roots}")
    return 0


if __name__ == "__main__":
    _setup_utf8()
    raise SystemExit(scan())