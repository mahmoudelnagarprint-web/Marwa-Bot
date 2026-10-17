#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
قالب CrewAI الرسمي لمعمل فيجن — «طاقم تحليل المشاريع» (Project Analysis Crew)
Vision-Lab | عقدة اللابتوب (LAPTOP_NODE) | أُنشئ: 2026-10-17
============================================================================
الغرض: نموذج جاهز (Boilerplate) يُستخدم فوراً عندما يُطلب من فيجن تحليل أي
مشروع جديد — انسخه أو استدعه مباشرة بمسار المشروع.

الاستخدام:
    python ai_templates/crewai_project_analyst_template.py <مسار-المشروع>

الطاقم (3 وكلاء متسلسلين):
    1) «مستكشف المشاريع»  — يمسح بنية المشروع ويتعرف على تقنياته وغرضه.
    2) «مراجع الكود»      — يقيّم الجودة والمخاطر وفرص التحسين.
    3) «كاتب التقرير»     — يصيغ تقريراً نهائياً منظماً بالعربية.

النموذج اللغوي (LLM): يُقرأ من متغيرات البيئة — لا مفاتيح داخل الكود أبداً:
    - الأولوية: DAHL_API_KEY / DAHL_API_URL / DAHL_MODEL   (بوابة اللابتوب)
    - البديل:   OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL
    وإن لم تكن مضبوطة، تُقرأ تلقائياً (وصامتة) من .env الخاصة بجذر المستودع.

ملاحظة: لقطة بنية المشروع تُجمع محلياً ببايثون قياسي وتُمرَّر في نص المهمة،
لذا يعمل القالب دون أي أدوات ملفات خارجية.
============================================================================
"""

import os
import re
import sys
from pathlib import Path

# --- إصلاح ترميز الطباعة العربية على ويندوز ---------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from crewai import Agent, Task, Crew, Process, LLM

# ---------------------------------------------------------------------------
# 1) إعدادات البيئة (قراءة صامتة — لا تُطبع القيم السرية إطلاقاً)
# ---------------------------------------------------------------------------

def quietly_load_repo_env() -> None:
    """تحميل DAHL_*/OPENAI_* من .env الخاصة بجذر المستودع إن لم تكن مضبوطة.
    القيم تُوضع في متغيرات البيئة فقط — لا تُطبع ولا تُسجَّل."""
    try:
        repo_env = Path(__file__).resolve().parents[2] / ".env"
        if not repo_env.exists():
            return
        for line in repo_env.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*\"?([^\"\r\n]+)\"?\s*$", line)
            if m:
                os.environ.setdefault(m.group(1), m.group(2).strip())
    except Exception:
        # الفشل هنا غير قاتل: قد تكون متغيرات البيئة مضبوطة من الخارج أصلاً
        pass


def build_llm() -> LLM:
    """بناء النموذج اللغوي من متغيرات البيئة (بدون أي أسرار في الكود)."""
    api_key = (
        os.environ.get("DAHL_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    base_url = (
        os.environ.get("DAHL_API_URL")
        or os.environ.get("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    ).strip().strip('"')
    model_name = (
        os.environ.get("DAHL_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "default-model"
    ).strip().strip('"')

    if not api_key:
        raise SystemExit(
            "لا يوجد مفتاح API في متغيرات البيئة (DAHL_API_KEY أو OPENAI_API_KEY) — "
            "لن يعمل الطاقم بدون مفتاح، ولن يُخزَّن أي مفتاح داخل هذا القالب."
        )
    return LLM(model=f"openai/{model_name}", base_url=base_url, api_key=api_key)


# ---------------------------------------------------------------------------
# 2) لقطة محلية من بنية المشروع (بايثون قياسي — لا أدوات خارجية)
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", ".idea",
    ".vscode", "dist", "build", ".pytest_cache", ".mypy_cache", "backup",
    "_sandbox_pos_writer", "pos_images", "debug_images",
}
TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json", ".yml",
    ".yaml", ".toml", ".ini", ".cfg", ".bat", ".ps1", ".html", ".css",
}


def snapshot_project(project_path: Path, max_files: int = 40, max_bytes: int = 110_000) -> str:
    """جمع شجرة المشروع + مقتطفات الملفات النصية الأساسية ضمن سقف محدود."""
    lines = [
        f"مسار المشروع: {project_path}",
        "",
        f"شجرة الملفات (حتى {max_files} ملفاً):",
    ]
    files: list = []
    for root, dirs, names in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            files.append(Path(root) / name)
    files = files[:max_files]
    for f in files:
        lines.append("  - " + str(f.relative_to(project_path)))

    lines.append("")
    lines.append("مقتطفات الملفات النصية (أول 30 سطراً لكل ملف):")
    budget = max_bytes
    for f in files:
        if f.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if budget <= 0:
            lines.append("  [تم بلوغ سقف اللقطة — بقية المقتطفات مُغفلة]")
            break
        chunk = "\n".join(text.splitlines()[:30])
        budget -= len(chunk.encode("utf-8", errors="ignore"))
        lines.append(f"\n----- {f.relative_to(project_path)} -----\n{chunk}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3) الطاقم: الوكلاء والمهام
# ---------------------------------------------------------------------------

def build_crew(snapshot: str, llm: LLM) -> Crew:
    scout = Agent(
        role="مستكشف المشاريع التقني",
        goal="فهم بنية المشروع وتحديد مكوناته ولغاته وأدواته وغرضه الوظيفي بدقة.",
        backstory=(
            "خبير تقني محنك في قراءة بنية المستودعات البرمجية، يميز التقنيات "
            "من هيكل الملفات، معروف بدقته وعدم تخمينه."
        ),
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    reviewer = Agent(
        role="مراجع الكود",
        goal="تقييم جودة الكود والمخاطر المحتملة وفرص التحسين بأولويات عملية.",
        backstory="مراجع كود صارم يركز على الأمان والأخطاء الشائعة وقابلية الصيانة.",
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )
    reporter = Agent(
        role="كاتب التقرير التنفيذي",
        goal="تحويل نتائج الفحص إلى تقرير عربي واضح قابل للتنفيذ فوراً.",
        backstory="كاتب تقني يجيد تبسيط المعقد دون فقدان الدقة.",
        llm=llm,
        allow_delegation=False,
        verbose=True,
    )

    t_scan = Task(
        description=(
            "فيما يلي لقطة كاملة من بنية المشروع (شجرة ملفات + مقتطفات). حلّلها وحدد: "
            "الغرض الوظيفي، اللغات والأطر المستخدمة، المكونات الأساسية، "
            "وأي مؤشرات بنائية لافتة.\n\n" + snapshot
        ),
        expected_output="ملخص تقني منظم بالعربية (عناوين ونقاط) يشرح بنية المشروع وغرضه وتقنياته.",
        agent=scout,
    )
    t_review = Task(
        description=(
            "بناءً على نتائج المستكشف: قيّم جودة الكود في نقاط واضحة: نقاط القوة، "
            "المخاطر (خصوصاً الأمنية مثل المفاتيح المكشوفة والمدخلات غير المعالجة)، "
            "الأخطاء الشائعة، وأهم 3 فرص تحسين مرتبة بالأولوية مع خطوات تنفيذية قصيرة."
        ),
        expected_output="تقييم جودة مرتب بالنقاط بالعربية مع أولويات وخطوات قابلة للتنفيذ.",
        agent=reviewer,
        context=[t_scan],
    )
    t_report = Task(
        description=(
            "اكتب التقرير النهائي بالعربية بهذا الهيكل: (1) ملخص تنفيذي من 5 أسطر، "
            "(2) بنية المشروع وتقنياته، (3) تقييم الجودة والمخاطر، "
            "(4) توصيات عملية مرقمة قابلة للتنفيذ مباشرة."
        ),
        expected_output="تقرير عربي نهائي منظم وجاهز للعرض على المالك.",
        agent=reporter,
        context=[t_scan, t_review],
    )

    return Crew(
        agents=[scout, reviewer, reporter],
        tasks=[t_scan, t_review, t_report],
        process=Process.sequential,
        verbose=True,
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("الاستخدام: python crewai_project_analyst_template.py <مسار-المشروع>")
        return 1
    project_path = Path(sys.argv[1]).resolve()
    if not project_path.is_dir():
        print(f"خطأ: المسار ليس مجلد مشروع صالحاً: {project_path}")
        return 1

    quietly_load_repo_env()
    llm = build_llm()
    print("أهلاً — قالب «طاقم تحليل المشاريع» من معمل فيجن (LAPTOP_NODE)")
    print(f"جاري تحليل: {project_path}")
    snapshot = snapshot_project(project_path)
    crew = build_crew(snapshot, llm)
    result = crew.kickoff()

    print("\n" + "=" * 68)
    print("تقرير طاقم تحليل المشاريع — Vision-Lab (LAPTOP_NODE)")
    print("=" * 68)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
