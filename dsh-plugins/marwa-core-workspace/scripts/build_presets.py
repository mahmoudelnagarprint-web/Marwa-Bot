# -*- coding: utf-8 -*-
"""مولد Agent Presets الرسمية — يقرأ دساتير الوكلاء الفعلية وينتج رقعة DSH ثابتة.

المخرجات:
  cordis.patch.yml        ← صف غرفة العمليات + 10 صفوف preset-<id> (تُفعَّل فوراً عند التثبيت)
  presets.generated.yml   ← نسخة احتياطية من صفوف الـPresets وحدها (للمراجعة)
  presets.summary.json    ← ملخص ما وُلد (أسماء/أحجام/توقيعات)

المطابقة مصدرها واحد: نفس جداول PRESET_SPECS في index.js (دساتير orchestrator/squad + ميثاق مروة
+ مسارات Notebook v2 وVision-Lab) — أي تحديث في الدساتير يُعاد التوليد ثم يُعاد التثبيت.
"""
import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = Path(os.environ.get("MARWA_REPO_ROOT") or r"G:\Marwa-Bot")
PLUGIN = Path(__file__).resolve().parent.parent

IS_WIN = os.name == "nt"

# ------------------------------------------------------------------ التعريفات (مطابقة index.js)
SPECS = [
    dict(id="marwa", name="مروة — المنسق العام", order=1,
         prompt="AGENT.md",
         refs=["RULES.md", "STATUS.md", "MARWA_CORE.md", "memory/"],
         tools=[("@deepseek-ai/dsh-tool-web", {})]),
    dict(id="notebook", name="أفكاري — الذاكرة الثانية (Notebook v2)", order=2,
         prompt="Vision-Lab/projects/notebook-v2/NB2_CHAT_BOOTSTRAP_PROMPT.md",
         refs=["Vision-Lab/projects/notebook-v2/", "notebook/"],
         tools=[]),
    dict(id="rased", name="راصد — المراقب الذاتي", order=3,
         prompt="orchestrator/squad/rased/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["memory/experience_ledger.json"],
         tools=[]),
    dict(id="hakim", name="حكيم — طبيب البيانات", order=4,
         prompt="orchestrator/squad/hakim/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["tools/export_products_excel.py", "tools/import_products_excel.py", "pos_data.db"],
         tools=[]),
    dict(id="fares", name="فارس — المدير المالي", order=5,
         prompt="orchestrator/squad/fares/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["FARES_CFO_STATE.md"],
         tools=[]),
    dict(id="salma", name="سلمى — علاقات العملاء", order=6,
         prompt="orchestrator/squad/salma/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["SALMA_CRM_STATE.md"],
         tools=[]),
    dict(id="koko", name="كوكو — التسويق والعروض", order=7,
         prompt="orchestrator/squad/koko/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["KOKO_MARKETING_STATE.md", "exports/products_catalog_master.xlsx"],
         tools=[("@deepseek-ai/dsh-tool-web", {"fetch": True, "searchTimeoutMs": 60000})]),
    dict(id="bibo", name="بيبو — التصنيع والليزر", order=8,
         prompt="orchestrator/squad/bibo/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["BIBO_MANUFACTURING_STATE.md"],
         tools=[]),
    dict(id="sasa", name="مصطفى (صاصا) — التحكم بالكمبيوتر", order=9,
         prompt="orchestrator/squad/sasa/CHAT_BOOTSTRAP_PROMPT.md",
         refs=["agents/SASA/SASA_LAPTOP_STATE.md", "agents/SASA/scripts/laptop_health.ps1",
               "orchestrator/agents/system_apps.json"],
         tools=[("@deepseek-ai/dsh-tool-pwsh", {}, IS_WIN is False),
                ("@deepseek-ai/dsh-tool-bash", {}, IS_WIN),
                ("@deepseek-ai/dsh-tool-fs", {})]),
    dict(id="vision", name="فيجن — الكودر والتطوير", order=10,
         prompt="Vision-Lab/SQUAD_BOOTSTRAP_PROMPT.md",
         refs=["Vision-Lab/", "Vision-Lab/AGENT.md", "Vision-Lab/RULES.md", "memory/experience_ledger.json"],
         tools=[("@deepseek-ai/dsh-tool-bash", {}, IS_WIN),
                ("@deepseek-ai/dsh-tool-pwsh", {}, IS_WIN is False),
                ("@deepseek-ai/dsh-tool-fs", {}),
                ("@deepseek-ai/dsh-tool-fs-search", {})]),
]


def read_text(p):
    try:
        return (ROOT / p).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def compose_prefix(spec):
    parts = []
    base = read_text(spec["prompt"])
    parts.append(base if base else ("أنت %s — وكيل متخصص في منظومة النجار برنت تحت إدارة مروة. "
                                    "اقرأ مراجعك وأجب بصدق، ولا تختلق أرقاماً أبداً." % spec["name"]))
    if spec["refs"]:
        parts.append("🗂️ مراجعك الرسمية (من داخل مستودع G:\\Marwa-Bot):\n" +
                     "\n".join("• " + r for r in spec["refs"]))
    return "\n\n".join(parts)[:14000]


def yaml_block(text, indent):
    pad = " " * indent
    lines = text.split("\n")
    if len(lines) == 1:
        return pad + lines[0]
    out = [pad + "|-"]
    for ln in lines:
        out.append(pad + (ln if ln else ""))
    return "\n".join(out)


def preset_yaml(spec, prefix):
    p = []
    p.append("- insert:")
    p.append("    - id: preset-%s" % spec["id"])
    p.append("      name: '@deepseek-ai/dsh-agent-preset'")
    p.append("      config:")
    p.append("        id: %s" % spec["id"])
    p.append("        name: %s" % spec["name"])
    p.append("        description: 'Preset تلقائي من دساتير منظومة مروة — %s'" % spec["name"])
    p.append("        order: %d" % spec["order"])
    p.append("        plugins:")
    p.append("          - id: persona")
    p.append("            name: '@deepseek-ai/dsh-persona'")
    p.append("            config:")
    p.append("              prefix: " + yaml_block(prefix, 16).strip())
    for name, cfg, *rest in spec["tools"]:
        disabled = rest[0] if rest else None
        p.append("          - name: '%s'" % name)
        if cfg:
            p.append("            config:")
            for k, v in cfg.items():
                if isinstance(v, bool):
                    p.append("              %s: %s" % (k, "true" if v else "false"))
                else:
                    p.append("              %s: %s" % (k, v))
        if disabled:
            p.append("            disabled: true")
    return "\n".join(p)


def main():
    static_presets = "--static-presets" in sys.argv[1:]
    workspace_row = (
        "- insert:\n"
        "    - id: marwa-core-workspace\n"
        "      name: '@local/marwa-core-workspace'\n"
        "      config:\n"
        "        repoRoot: 'G:\\Marwa-Bot'\n"
        "        routePath: '/api/marwa-core'\n"
        "        idleShutdownMs: 300000\n"
        "        nb2Url: 'http://127.0.0.1:8110'\n"
    )
    blocks = [workspace_row]
    summary = []
    for spec in SPECS:
        prefix = compose_prefix(spec)
        if static_presets:
            blocks.append(preset_yaml(spec, prefix))
        summary.append({"id": spec["id"], "name": spec["name"], "order": spec["order"],
                        "prompt": spec["prompt"], "prefixChars": len(prefix)})
    patch = "\n".join(blocks) + "\n"
    (PLUGIN / "cordis.patch.yml").write_text(patch, encoding="utf-8")
    (PLUGIN / "presets.generated.yml").write_text("\n".join(blocks[1:]) + "\n", encoding="utf-8")
    (PLUGIN / "presets.summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("generated cordis.patch.yml (static rows: %s) with %d preset defs" % (static_presets, len(summary)))
    for s in summary:
        print("  preset-%s | %s | prefix=%d chars" % (s["id"], s["name"], s["prefixChars"]))


if __name__ == "__main__":
    main()
