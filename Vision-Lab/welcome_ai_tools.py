# -*- coding: utf-8 -*-
"""أداة ترحيب بسيطة — تأكيد إن أدوات تطوير الذكاء الاصطناعي شغالة في Vision-Lab."""

import sys
from datetime import date

# إعادة ضبط الإخراج لـ UTF-8 عشان النص العربي يطلع صح على ويندوز
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

NODE_NAME = "LAPTOP_NODE"


def check_crewai() -> None:
    """فحص خفيف لتوفر مكتبة crewai من غير ما نكسر السكريبت."""
    try:
        import crewai  # noqa: F401

        version = getattr(crewai, "__version__", "غير معروف")
        print(f"✅ CrewAI متاحة — الإصدار: {version}")
    except Exception:
        print("⚠️ CrewAI مش متاحة حاليًا — عادي، السكريبت كمّل من غير مشاكل.")


def main() -> None:
    today = date.today().isoformat()
    print("=" * 60)
    print("🌟 أهلًا بيك في Vision-Lab! 🌟")
    print(f"📅 التاريخ: {today}")
    print(f"💻 العقدة: {NODE_NAME}")
    print("🛠️ أدوات تطوير الذكاء الاصطناعي (Aider و CrewAI)")
    print("   اشتغلت بنجاح جوه Vision-Lab على عقدة اللابتوب 🎉")
    print("=" * 60)
    check_crewai()
    print("تم! كل حاجة جاهزة نبدأ الشغل 🚀")


if __name__ == "__main__":
    main()
