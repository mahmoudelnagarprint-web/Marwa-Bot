# -*- coding: utf-8 -*-
"""
MarwaBot Daily Report — «تقفيلة اليوم» (بأمر المالك 2026-10-19)
=============================================================
مهمة مجدولة: MarwaBot_DailyReport (يومياً 21:30 بتوقيت القاهرة) + تشغيل يدوي.

الوظيفة: جمع أرقام اليوم من مرآة اللابتوب (قراءة فقط) + نشاط كتب الوكلاء في Git،
وتوليد تقرير يومي موحد يُكتب في:
  1) MARWA_HOME_STATE.md — تحت المرساة «سجل التقفيلات اليومية»
  2) تطبيق الـ Notebook — عبر الواجهة الرسمية store.add_note (نفس ما يستخدمه الجسر)

النشر عبر Git يترك لمهمة MarwaBot_GitSync القائمة (أمر المالك الدائم) — لا force، لا أسرار، لا كتابة على أي قاعدة أعمال.
"""
import datetime as _dt
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"G:\Marwa-Bot")
sys.path.insert(0, str(ROOT))
from notebook import store  # noqa: E402  (المسار الرسمي لتدوين الملاحظات)

DB = ROOT / "pos_data.db"
HOME = ROOT / "MARWA_HOME_STATE.md"
ANCHOR = "## 📅 سجل التقفيلات اليومية (توليد آلي — MarwaBot_DailyReport)"
GIT = r"C:\Program Files\Git\cmd\git.exe"
BOOKS = ("FARES_CFO_STATE.md", "KOKO_MARKETING_STATE.md", "SALMA_CRM_STATE.md",
         "BIBO_MANUFACTURING_STATE.md", "RASED_SENTINEL_STATE.md")

today = _dt.date.today().isoformat()
stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def q(cur, sql, params=()):
    return cur.execute(sql, params).fetchone()


conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
cur = conn.cursor()

acct_start = q(cur, "SELECT value FROM settings WHERE key='accounting_start_date'")
acct_start = (acct_start[0] if acct_start else "2026-10-01")
shift_open = q(cur, "SELECT opened_at FROM daily_shifts WHERE status='open' ORDER BY id DESC LIMIT 1")
shift_open = str(shift_open[0])[:10] if shift_open and shift_open[0] else "1970-01-01"

inc_shift = q(cur, "SELECT ROUND(COALESCE(SUM(amount),0),2) FROM transactions WHERE type='Income' AND date>=?", (shift_open,))[0]
exp_shift = q(cur, "SELECT ROUND(COALESCE(SUM(amount),0),2) FROM transactions WHERE type='Expense' AND date>=?", (shift_open,))[0]
cash = round(float(inc_shift) - float(exp_shift), 2)
inc_oct = q(cur, "SELECT ROUND(COALESCE(SUM(amount),0),2) FROM transactions WHERE type='Income' AND date>=?", (acct_start,))[0]
exp_oct = q(cur, "SELECT ROUND(COALESCE(SUM(amount),0),2) FROM transactions WHERE type='Expense' AND date>=?", (acct_start,))[0]
recv, recv_n = q(cur, "SELECT ROUND(COALESCE(SUM(balance),0),2), COUNT(*) FROM clients WHERE balance>0")
open_n, open_v = q(cur, "SELECT COUNT(*), ROUND(COALESCE(SUM(total_amount),0),2) FROM orders WHERE status!='Delivered'")
tx_n, tx_max = q(cur, "SELECT COUNT(*), COALESCE(MAX(date),'') FROM transactions")
low = cur.execute("SELECT name, stock_qty FROM products WHERE stock_qty<=0 ORDER BY stock_qty LIMIT 5").fetchall()
conn.close()

try:
    log = subprocess.run([GIT, "-C", str(ROOT), "log", "--since=1 day ago", "--format=%h %s",
                          "--", *BOOKS], capture_output=True, text=True, encoding="utf-8", errors="replace")
    commits = [l for l in (log.stdout or "").splitlines() if l.strip()]
except Exception:
    commits = []

lines = []
lines.append("### 📅 تقفيلة %s (ولّدت %s — MarwaBot_DailyReport)" % (today, stamp))
lines.append("| البند | القيمة (ج) |")
lines.append("|---|---:|")
lines.append("| الخزنة (دخل الوردية %s − المصروف) | **%s** |" % (shift_open, f"{cash:,.2f}"))
lines.append("| دخل الوردية / المصروف | %s / %s |" % (f"{float(inc_shift):,.2f}", f"{float(exp_shift):,.2f}"))
lines.append("| دخل أكتوبر (من %s) / مصروف أكتوبر | %s / %s |" % (acct_start, f"{float(inc_oct):,.2f}", f"{float(exp_oct):,.2f}"))
lines.append("| الآجل المستحق (عدد العملاء) | **%s** (%s عميل) |" % (f"{float(recv):,.2f}", recv_n))
lines.append("| طلبات قيد التجهيز (عدد/قيمة) | %s / %s |" % (open_n, f"{float(open_v):,.2f}"))
lines.append("| آخر حركة بالنظام | %s (إجمالي %s حركة) |" % (str(tx_max)[:16], tx_n))
lines.append("| إنذارات مخزون (رصيد ≤0) | %s |" % (" • ".join("%s (%s)" % (n, s) for n, s in low) or "لا يوجد"))
lines.append("| كوميتات كتب الوكلاء (آخر 24 ساعة) | %s |" % (len(commits) or "صفر"))
lines.append("")
block = "\n".join(lines)

home_text = HOME.read_text(encoding="utf-8")
if ANCHOR in home_text:
    idx = home_text.index(ANCHOR) + len(ANCHOR)
    home_text = home_text[:idx] + "\n\n" + block + home_text[idx:]
else:
    home_text = home_text.rstrip() + "\n\n" + ANCHOR + "\n\n" + block
HOME.write_text(home_text, encoding="utf-8")
print("[home] daily section written ->", HOME.name)

nid = store.add_note({
    "kind": "note",
    "title": "📅 تقفيلة اليوم %s (توليد آلي)" % today,
    "body": block,
    "category": "المالية",
    "priority": "normal",
    "status": "open",
    "source": "daily_report",
    "tags": "daily-report",
    "meta": "{}",
})
print("[notebook] note id=%s" % nid)
print("[done] MarwaBot_DailyReport complete")
