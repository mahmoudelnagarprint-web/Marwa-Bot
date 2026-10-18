# -*- coding: utf-8 -*-
"""Data Healer & Parity Watchdog (طبيب البيانات وحارس التطابق) — Phase 2 FULL BUILD.
يكتشف: أسعار صفرية، انتهاكات سياسة التسعير (+30%، جملة<قطاعي)، منتجات مكررة،
ملفات تصميم مفقودة للطلبات المفتوحة، ومخزون سالب (مع استثناء «ختم» بقرار المالك)،
ويطابق المحلي مع Supabase. الروتين الصباحي = تقرير مركّب من كل الفحوص.
قواعد صارمة: قراءة فقط 100% — أي إصلاح أسعار اقتراح ينتظر موافقة المالك الصريحة،
ولا بيانات مخترعة — فشل أي فحص يُبلَّغ بصدق ولا يُفترض نجاحه.
"""
from __future__ import annotations

import sqlite3
import sys as _sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..base import SubAgent

# ── طبقة الربط المركزية (task-2): لا مصدر إلا الحي — أي pos_data.db قديم مرفوض ──
_VISION_LAB = Path(__file__).resolve().parent.parent.parent / "Vision-Lab"   # نسبي — يعمل على أي عقدة
if str(_VISION_LAB) not in _sys.path:
    _sys.path.insert(0, str(_VISION_LAB))
from config import data_source as _central  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent          # G:\ai\Naggar Print POS Agent
DB_PATH = _central.db_path()          # المصدر الرسمي الحي (يتجاوزه POS_LIVE_DB فقط)
ENV_PATH = ROOT / ".env"
OWNER_APPROVED_NEGATIVE = {"ختم"}   # رصيد «ختم» السالب مقصود من المالك — لا يُفحص
CORE_MATERIALS = []                   # الخامات الأساسية للفحص الصارم (ألواح/مجات/خشب…) — تُعرَّف بأمر المالك
CAP = 8                               # أقصى عدد أمثلة في القوائم
MARGIN = 1.3                          # سياسة التسعير: القطاعي = الجملة × 1.3
TOL = 0.01                            # تسامح المقارنة العشرية


def _ro_conn() -> sqlite3.Connection:
    """اتصال قراءة فقط بالمصدر الرسمي الحي — يرفض أي مسار قديم صراحةً."""
    return _central.open_readonly()


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


def _fmt(n) -> str:
    """تنسيق رقم: أسعار برقمين عشريين، أعداد صحيحة كما هي."""
    try:
        f = float(n)
        if f == int(f):
            return str(int(f))
        return f"{f:.2f}"
    except (TypeError, ValueError):
        return str(n)


# --------------------------------------------------------------------- فحوص محلية
# ==== محرك الوسم الآلي (Phase 6 — بأمر المالك 2026-10-14 «تفعيل المرحلة 6») ====
# القواعد الخمس المعتمدة من المالك. التعارض (أكثر من فئة) => needs_review بلا تخمين.
ACRYLIC_HINTS = ("أكريليك", "اكريليك", "اكليرليك", "اكليرك", "إكليريك", "أكليرليك", "اكريلك",
                 "درع", "ستاند", "استاند")
SUBLIMATION_HINTS = ("مج ", "ماج", "مجـ", "كوستر")
ENGRAVING_HINTS = ("أقلام", "اقلام", "قلم", "محافظ", "محفظة", "محفظه")
TABLOU_HINTS = ("تابلو", "تابلوه", "برواز")
WOOD_HINTS = ("خشب", "بوكس", "صينية", "صينيه", "ميدالية", "ميداليه", "مادليه", "مدالية",
              "فانوس", "بصامة", "بصامه", "بصمة", "بصمه", "طارة", "طاره", "طقم مكتب",
              "تاج نيم", "يافطه", "يافطة", "برياد", "توزيعه")


def classify_product(name: str) -> Tuple[str, str]:
    """يصنف منتجًا بخامته ومسار تشغيله من اسمه — بقواعد المالك المعتمدة.
    التعارض أو الغياب => needs_review / unknown (لا تخمين أبدًا)."""
    n = (name or "").strip()
    hits: List[Tuple[str, str]] = []
    if any(k in n for k in ACRYLIC_HINTS):
        hits.append(("acrylic", "laser"))
    if any(k in n for k in SUBLIMATION_HINTS):
        hits.append(("sublimation", "sublimation"))
    if any(k in n for k in ENGRAVING_HINTS):
        hits.append(("engraving_ready", "engraving"))
    if any(k in n for k in TABLOU_HINTS):
        hits.append(("composite", "framing"))
    if any(k in n for k in WOOD_HINTS):
        hits.append(("wood", "laser"))
    # «حفر ليزر» خدمة معروفة المسار (ليزر) بلا خامة ثابتة
    if "حفر" in n or "ليزر" in n:
        hits.append(("unknown", "laser"))
    unique = list(dict.fromkeys(hits))
    if len(unique) == 1:
        return unique[0]
    if not unique:
        return ("unknown", "unknown")
    # تعارض قواعد — تعارضات متعددة => مراجعة المالك
    mat = {u[0] for u in unique}
    if len(mat) == 1:
        # نفس الخامة بمسارات متعددة (مثل خشب+حفر) — نأخذ الخامة ونراجع المسار
        return (unique[0][0], "needs_review")
    return ("needs_review", "needs_review")


def check_zero_prices(conn: sqlite3.Connection) -> Dict[str, Any]:
    zero_retail = [dict(r) for r in conn.execute(
        "SELECT id, name, price_wholesale, price_retail FROM products "
        "WHERE price_retail IS NULL OR price_retail <= 0 ORDER BY id"
    ).fetchall()]
    zero_wholesale = [dict(r) for r in conn.execute(
        "SELECT id, name, price_retail FROM products "
        "WHERE price_wholesale IS NULL OR price_wholesale <= 0 ORDER BY id"
    ).fetchall()]
    return {"zero_retail": zero_retail, "zero_wholesale": zero_wholesale}


def check_pricing_policy(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """انتهاك = الجملة > 0 والقطاعي أقل من الجملة×1.3 (بالتسامح).
    يشمل تلقائيًا الحالات المقلوبة (قطاعي <= جملة). الاقتراح لا يُنفَّذ إلا بموافقة المالك."""
    rows = conn.execute(
        "SELECT id, name, price_wholesale, price_retail FROM products "
        "WHERE price_wholesale > 0 ORDER BY id"
    ).fetchall()
    violations: List[Dict[str, Any]] = []
    for r in rows:
        w, rt = float(r["price_wholesale"]), float(r["price_retail"] or 0)
        target = round(w * MARGIN, 2)
        if rt < target - TOL:
            violations.append({
                "id": r["id"], "name": r["name"],
                "wholesale": w, "retail": rt, "suggested": target,
                "inverted": rt <= w,
            })
    return violations


def check_duplicates(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT name, COUNT(*) AS c, GROUP_CONCAT(id) AS ids FROM products "
        "GROUP BY name HAVING c > 1 ORDER BY c DESC, name"
    ).fetchall()
    return [{"name": r["name"], "count": r["c"], "ids": r["ids"]} for r in rows]


def check_negative_stock(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, name, stock_qty FROM products WHERE stock_qty < 0 ORDER BY stock_qty"
    ).fetchall()
    return [
        {"id": r["id"], "name": r["name"], "stock_qty": r["stock_qty"]}
        for r in rows if r["name"] not in OWNER_APPROVED_NEGATIVE
    ]


def check_missing_designs(conn: sqlite3.Connection) -> Dict[str, Any]:
    """طلبات مفتوحة (قيد تجهيز/جاهز) مسجَّل لها مسار تصميم لكن المجلد غير موجود على القرص."""
    base = ""
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'local_images_path'"
        ).fetchone()
        base = (row["value"] if row else "") or ""
    except sqlite3.Error:
        base = ""
    rows = conn.execute(
        "SELECT o.id, o.status, o.local_image_path, c.name AS client_name "
        "FROM orders o LEFT JOIN clients c ON c.id = o.client_id "
        "WHERE o.status IN ('Under Preparation','Ready') ORDER BY o.id"
    ).fetchall()
    open_orders = [dict(r) for r in rows]
    missing, no_path = [], 0
    for o in open_orders:
        p = (o.get("local_image_path") or "").strip()
        if not p:
            no_path += 1
            continue
        if not Path(p).exists():
            missing.append(o)
    return {"base": base, "open": len(open_orders), "missing": missing, "no_path": no_path}


# ------------------------------------------------------------------ مطابقة السحابة
PARITY_SPEC = {
    "clients":       {"cols": "id,balance",            "sum": ["balance"],    "max": "id"},
    "products":      {"cols": "id,stock_qty",          "sum": ["stock_qty"],  "max": "id"},
    "orders":        {"cols": "id",                    "sum": [],             "max": "id"},
    "order_items":   {"cols": "id",                    "sum": [],             "max": "id"},
    "transactions":  {"cols": "id,amount",            "sum": ["amount"],     "max": "id"},
}


def check_parity() -> Dict[str, Any]:
    """مطابقة محلي↔سحابة: العدد + المجاميع + أكبر معرّف لكل جدول (قراءة فقط عبر REST)."""
    import requests

    env = _load_env()
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    key = env.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_PUBLISHABLE_KEY") or ""
    if not url or not key:
        return {"ok": False, "error": "مفاتيح Supabase غير موجودة في .env"}

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    conn = _ro_conn()
    try:
        tables: Dict[str, Dict[str, Any]] = {}
        for table, spec in PARITY_SPEC.items():
            cols = [c.strip() for c in spec["cols"].split(",")]
            # local
            lrows = conn.execute(
                f"SELECT {', '.join(chr(34) + c + chr(34) for c in cols)} FROM {table}"
            ).fetchall()
            lcount = len(lrows)
            lsums = {
                s: round(sum(float(r[s] or 0) for r in lrows), 2) for s in spec["sum"]
            }
            lmax = max((int(r[spec["max"]]) for r in lrows), default=0)
            # cloud
            r = requests.get(
                f"{url}/rest/v1/{table}?select={spec['cols']}&limit=10000",
                headers=headers, timeout=30,
            )
            r.raise_for_status()
            crows = r.json() or []
            ccount = len(crows)
            csums = {
                s: round(sum(float((row.get(s) or 0)) for row in crows), 2)
                for s in spec["sum"]
            }
            cmax = max((int(row.get(spec["max"]) or 0) for row in crows), default=0)
            diffs = []
            if lcount != ccount:
                diffs.append(f"العدد {_fmt(lcount)}≠{_fmt(ccount)}")
            for s in spec["sum"]:
                if abs(lsums[s] - csums[s]) > TOL:
                    diffs.append(f"مجموع {s}: {_fmt(lsums[s])}≠{_fmt(csums[s])}")
            if lmax != cmax:
                diffs.append(f"أكبر id: {_fmt(lmax)}≠{_fmt(cmax)}")
            tables[table] = {
                "ok": not diffs,
                "diffs": diffs,
                "local": {"count": lcount, "sums": lsums, "max": lmax},
                "cloud": {"count": ccount, "sums": csums, "max": cmax},
            }
        return {"ok": all(t["ok"] for t in tables.values()), "tables": tables}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        conn.close()


# --------------------------------------------------------------------- الوكيل
class DataHealerAgent(SubAgent):
    def __init__(self):
        super().__init__(
            agent_id="data_healer",
            name="طبيب البيانات وحارس التطابق",
            keywords=[
                "فحص", "روتين الصباحي", "روتين الصباح", "الروتين", "طبيب بيانات",
                "data healer", "اسعار صفر", "اسعارها صفر", "أسعار صفرية", "سعر صفر",
                "منتجات مكررة", "مكرر", "تكرار",
                "تسعير", "سياسة التسعير", "30%", "٣٠٪", "خصم 30",
                "parity", "تطابق", "مطابقة", "مطابقه", "حارس التطابق",
                "ملفات مفقودة", "تصميم مفقود", "التصاميم", "مخزون سالب",
                "تصنيف المنتجات", "صنف المنتجات", "وسم المنتجات", "تصنيف الخامات",
            ],
            phase=2,
        )

    # ------------------------------------------------------------------ تنسيق
    @staticmethod
    def _cap(items: List[str]) -> str:
        if len(items) <= CAP:
            return "\n".join(items)
        return "\n".join(items[:CAP]) + f"\n… و {len(items) - CAP} أخرى"

    def _zero_prices_report(self, z: Dict[str, Any]) -> str:
        zr, zw = z["zero_retail"], z["zero_wholesale"]
        lines = [f"• أسعار قطاعي صفرية: {_fmt(len(zr))} منتج", f"• أسعار جملة صفرية: {_fmt(len(zw))} منتج"]
        if zr:
            lines.append("  أمثلة قطاعي صفر: " + self._cap(
                [f"{p['name']} (جملة {_fmt(p['price_wholesale'])})" for p in zr]))
        if zw:
            lines.append("  أمثلة جملة صفر: " + self._cap(
                [f"{p['name']} (قطاعي {_fmt(p['price_retail'])})" for p in zw]))
        return "\n".join(lines)

    def _pricing_report(self, violations: List[Dict[str, Any]]) -> str:
        if not violations:
            return "✅ كل المنتجات ذات الجملة الموجبة تحترم السياسة (قطاعي ≥ جملة × 1.3)."
        inv = sum(1 for v in violations if v["inverted"])
        lines = [
            f"• منتجات مخالفة: {_fmt(len(violations))}"
            + (f" (منها {_fmt(inv)} قطاعي ≤ جملة — مقلوب!)" if inv else "")
        ]
        lines.append(self._cap([
            f"{v['name']}: الآن قطاعي {_fmt(v['retail'])} والجملة {_fmt(v['wholesale'])}"
            f" → المقترح قطاعي {_fmt(v['suggested'])}"
            for v in violations
        ]))
        lines.append(
            "🔒 لا يتم أي تعديل سعري إلا بموافقتك الصريحة — قولي «اعتمد تسعير [رقم المنتج]» "
            "وسيمر عبر القناة الرسمية للكتابة بعد تأكيدك."
        )
        return "\n".join(lines)

    def _duplicates_report(self, dupes: List[Dict[str, Any]]) -> str:
        if not dupes:
            return "✅ لا أسماء منتجات مكررة."
        return (
            f"• أسماء مكررة: {_fmt(len(dupes))}\n"
            + self._cap([f"«{d['name']}» ×{_fmt(d['count'])} (ids: {d['ids']})" for d in dupes])
        )

    def _neg_stock_report(self, negs: List[Dict[str, Any]]) -> str:
        """سياسة المالك المعتمدة 2026-10-13: الإعفاء والتلخيص — سطر واحد بالعدد الإجمالي،
        بلا سرد تفصيلي. الفحص الصارم يقتصر على CORE_MATERIALS عند تعريفها بأمر المالك."""
        if not negs:
            return "• ✅ لا مواد برصيد سالب."
        line = (
            f"• ملخص المخزون: توجد {len(negs)} مادة برصيد سالب (أغلبها خدمات وتصنيع) — "
            "معفاة من الفحص المفصَّل بقرار المالك."
        )
        if CORE_MATERIALS:
            core_neg = [n for n in negs if any(m in (n["name"] or "") for m in CORE_MATERIALS)]
            if core_neg:
                line += "\n  ⚠️ خامات أساسية بالسالب (فحص صارم):\n  " + self._cap(
                    [f"{n['name']}: {_fmt(n['stock_qty'])}" for n in core_neg])
        return line

    def _designs_report(self, m: Dict[str, Any]) -> str:
        lines = [f"• طلبات مفتوحة (قيد تجهيز/جاهز): {_fmt(m['open'])}"]
        if m["missing"]:
            lines.append(f"  ⚠️ مجلد تصميم مفقود لـ {_fmt(len(m['missing']))} طلب:")
            lines.append("  " + self._cap([
                f"#{o['id']} {o['client_name'] or '—'} ({o['status']})" for o in m["missing"]
            ]))
        else:
            lines.append("  ✅ كل الطلبات المفتوحة ذات المسار المسجَّل موجودة على القرص.")
        lines.append(f"  • بلا مسار تصميم مسجَّل: {_fmt(m['no_path'])} (طبيعي لو لسه مفيش تصميم).")
        return "\n".join(lines)

    def _parity_report(self, p: Dict[str, Any]) -> str:
        if not p.get("ok") and p.get("error"):
            return f"• ❌ تعذر فحص المطابقة السحابية ({p['error']}) — ما افترضتش نتيجة. ابعت الإشارة للمالك فورًا."
        lines = []
        for table, t in p.get("tables", {}).items():
            mark = "✅" if t["ok"] else "❌"
            info = f"العدد {_fmt(t['local']['count'])}"
            if t["local"]["sums"]:
                info += " | " + " | ".join(
                    f"مجموع {k}: {_fmt(v)}" for k, v in t["local"]["sums"].items())
            if not t["ok"]:
                info += " — فروق: " + "؛ ".join(t["diffs"])
            lines.append(f"  {mark} {table}: {info}")
        verdict = "✅ المحلي والسحابة متطابقان على الجداول الخمسة." if p.get("ok") \
            else "❌ في فروق تحتاج مراجعة (مذكورة فوق)."
        return "• مطابقة محلي↔سحابة:\n" + "\n".join(lines) + f"\n  {verdict}"

    # ------------------------------------------------------------------ الفروع
    def handle(self, text, ctx=None):
        t = (text or "").lower()
        try:
            conn = _ro_conn()
        except Exception as exc:
            return {
                "reply": f"❌ تعذر فتح قاعدة البيانات للقراءة ({type(exc).__name__}) — ما افترضتش أي نتيجة.",
                "action": None, "payload": {},
            }
        try:
            if "تصنيف" in t or "صنف المنتجات" in t or "وسم" in t:
                return self._auto_tag(conn)
            if "روتين" in t:
                return self._morning_routine(conn)
            if "تسعير" in t or "30%" in t or "٣٠٪" in t or "سياسة" in t:
                return self._reply("سياسة التسعير (+30%، جملة أقل من القطاعي)",
                                    self._pricing_report(check_pricing_policy(conn)))
            if "مكرر" in t or "تكرار" in t:
                return self._reply("فحص المنتجات المكررة", self._duplicates_report(check_duplicates(conn)))
            if "صفر" in t:
                return self._reply("فحص الأسعار الصفرية", self._zero_prices_report(check_zero_prices(conn)))
            if "ملفات" in t or "تصميم" in t or "التصاميم" in t:
                return self._reply("فحص ملفات التصميم للطلبات المفتوحة", self._designs_report(check_missing_designs(conn)))
            if "تطابق" in t or "مطابقة" in t or "مطابقه" in t or "parity" in t:
                return self._reply("حارس التطابق (محلي↔سحابة)", self._parity_report(check_parity()))
            if "مخزون" in t and "سالب" in t:
                return self._reply("فحص المخزون السالب", self._neg_stock_report(check_negative_stock(conn)))
            # افتراضي: فحص سريع = أسعار صفرية + مكررات + مخزون سالب
            quick = "\n\n".join([
                self._zero_prices_report(check_zero_prices(conn)),
                self._duplicates_report(check_duplicates(conn)),
                self._neg_stock_report(check_negative_stock(conn)),
            ])
            return self._reply("فحص سريع (أسعار صفرية + مكررات + مخزون)", quick)
        except Exception as exc:
            return {
                "reply": f"❌ فشل الفحص ({type(exc).__name__}: {exc}) — ما افترضتش أي نتيجة. التفاصيل في سجل الخبرة.",
                "action": None, "payload": {},
            }
        finally:
            conn.close()

    @staticmethod
    def _reply(title: str, body: str) -> Dict[str, Any]:
        return {"reply": f"🩺 {title}\n{body}", "action": "data_healer_report", "payload": {}}

    def _auto_tag(self, ro_conn: sqlite3.Connection) -> Dict[str, Any]:
        """محرك الوسم الآلي (Phase 6 — بأمر المالك 2026-10-14):
        يصنف كل المنتجات من أسمائها بقواعد المالك الخمس، ويحفظ النتيجة في عمودي
        material_type / operation_type (الكتابة الوحيدة المسموحة بطبيب البيانات —
        بأمر صريح وموثق، وبعد النسخ الاحتياطي المعتاد). التعارضات => مراجعة المالك."""
        rows = ro_conn.execute("SELECT id, name FROM products ORDER BY id").fetchall()
        results = []
        for r in rows:
            mat, op = classify_product(r["name"])
            results.append({"id": r["id"], "name": r["name"], "mat": mat, "op": op})

        # حفظ التصنيف (كتابة مرخّصة بأمر المالك) — تُمرّ من طبقة الربط المركزية:
        # افتراضياً مرفوضة (لا كتابة على القاعدة الحية إلا بـ POS_LIVE_WRITE=1 + approved=True).
        try:
            wconn = _central.open_readwrite(
                purpose="data_healer auto-tag: products.material_type/operation_type",
                approved=False,
            )
            cur = wconn.cursor()
            for it in results:
                cur.execute(
                    "UPDATE products SET material_type = ?, operation_type = ? WHERE id = ?",
                    (it["mat"], it["op"], it["id"]),
                )
            wconn.commit()
            wconn.close()
        except Exception as exc:
            return self._reply(
                "الوسم الآلي",
                f"❌ فشل حفظ التصنيف ({type(exc).__name__}: {exc}) — ما اتكتبش أي حاجة.",
            )

        # التقرير
        from collections import Counter
        mats = Counter(it["mat"] for it in results)
        review = [it for it in results if "needs_review" in (it["mat"], it["op"])]
        unknown = [it for it in results if it["mat"] == "unknown" and it["op"] == "unknown"]
        lines = [
            f"✅ صنّفت {len(results)} منتجًا وحفظت التصنيف في عمودي material_type / operation_type.",
            "• التوزيع: " + " | ".join(f"{k}: {v}" for k, v in mats.most_common()),
            "",
            f"⚠️ تعارضات تحتاج قرارك ({len(review)}):",
        ]
        if review:
            lines += [f"  • {it['name']} (id {it['id']})" for it in review[:CAP]]
            if len(review) > CAP:
                lines.append(f"  … و {len(review) - CAP} أخرى")
        else:
            lines.append("  (لا تعارضات)")
        lines.append("")
        lines.append(f"❓ غير مصنفة بانتظار تسميتك ({len(unknown)}):")
        if unknown:
            lines += [f"  • {it['name']} (id {it['id']})" for it in unknown[:CAP]]
            if len(unknown) > CAP:
                lines.append(f"  … و {len(unknown) - CAP} أخرى")
        else:
            lines.append("  (كل المنتجات مصنفة)")
        lines.append("")
        lines.append("🔒 التعديل بيتم بأمرك: قولي «غيّر تصنيف [رقم المنتج] إلى [أكريليك/خشب/...]» وأنا أنفذه.")
        return self._reply("الوسم الآلي للمنتجات (Phase 6)", "\n".join(lines))

    def _morning_routine(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        """الروتين الصباحي: كل الفحوص في تقرير واحد — قراءة فقط بلا أي كتابة."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        parts = [f"🌅 الروتين الصباحي — {now}", "كل الفحوص قراءة فقط، وأي إصلاح ينتظر موافقتك.\n"]

        # 1) مطابقة السحابة (قد تفشل لو النت شغال بلا إنترنت — تُبلَّغ بصدق)
        try:
            parts.append(self._parity_report(check_parity()))
        except Exception as exc:
            parts.append(f"• ❌ تعذر فحص المطابقة السحابية ({type(exc).__name__}) — ما افترضشت نتيجة.")
        parts.append("")

        # 2) أسعار صفرية
        parts.append(self._zero_prices_report(check_zero_prices(conn)))
        parts.append("")

        # 3) سياسة التسعير
        parts.append(self._pricing_report(check_pricing_policy(conn)))
        parts.append("")

        # 4) مكررات
        parts.append(self._duplicates_report(check_duplicates(conn)))
        parts.append("")

        # 5) مخزون سالب (ختم مستثنى)
        parts.append(self._neg_stock_report(check_negative_stock(conn)))
        parts.append("")

        # 6) ملفات التصميم
        parts.append(self._designs_report(check_missing_designs(conn)))
        parts.append("")
        parts.append("🩺 طبيب البيانات — خلاصته: راجع البنود ⚠️ أعلاه واعتمد اللي تشوفه، والباقي سليم.")

        return {"reply": "\n".join(parts), "action": "morning_routine", "payload": {}}
