# -*- coding: utf-8 -*-
"""النسخ الاحتياطي الأسبوعي — النجار برنت (مُصلح بعد النقل 2026-10-16 بإذن المالك).

إصلاح حرج: المسارات القديمة (G:\\ai\\...) مُشلت من القرص فكان السكربت بيفشل
منذ نقل المشروع إلى G:\\Marwa-Bot — آخر نسخة ناجحة كانت 2026-10-11.
القاعدة الجديدة: **كل المسارات نسبية لجذر المشروع** (تتحرك مع المستودع).

- pos_data.db  : نسخة موثقة عبر SQLite backup API + integrity_check (زي الأصل).
- notebook.db  : ضُمّت بأمر المالك 2026-10-16 — نفس الطريقة الموثقة + عدّ النوتس.
- الـzip       : لقطة الـWorkspace ما عدا القواعد الحية (لها نسخها الموثقة جنبها)
                 و.venv و__pycache__ واللوجات ومجلد backup نفسه.

المهمة المجدولة: الأحد 06:00 — scripts\\install_backup_task.ps1 (يعمل على أي عقدة).
"""
import sqlite3
import zipfile
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # جذر المشروع — يتحرك مع المستودع
# ── المصدر الرسمي الحي (منقذ 2026-10-18 — قرار المالك، ربط P1 العاجل) ──
# القاعدة الحية = حسب .env (LIVE_DB_PATH). إن غاب أو أشار لجذر المساحة (النسخة
# المتجمدة صفر الأرصدة) → رفض صريح، لا نسخة بلا قيمة أبداً.
_LIVE_ENV = "LIVE_DB_PATH"
_LIVE_DEFAULT = r"G:\ai\Elnagar POS\pos_data.db"


def _resolve_live_db() -> Path:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(_LIVE_ENV + "="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    # لا .env أو لا قيمة: الافتراضي الحي، مع تحذير
    print(f"[backup] {_LIVE_ENV} غير موجود في .env — استخدم الافتراضي {_LIVE_DEFAULT}")
    return Path(_LIVE_DEFAULT)


SRC_DB = _resolve_live_db()
if SRC_DB.resolve() == (ROOT / "pos_data.db").resolve():
    raise SystemExit(
        "⛔ مرفوض: LIVE_DB_PATH يشير لنسخة المساحة المتجمدة (ROOT/pos_data.db — أرصدة "
        "صفرية). صحّح .env إلى القاعدة الحية ثم أعد التشغيل."
    )
NOTEBOOK_DB = ROOT / "notebook" / "data" / "notebook.db"
WORKSPACE = ROOT
BACKUP_DIR = ROOT / "backup"
KEEP = 8
STATUS = ROOT / "memory" / "backup_status.json"
LOG = ROOT / "scripts" / "backup.log"


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def backup_db(src_path: Path, stamp: str, prefix: str, tables) -> tuple:
    """نسخة موثقة: SQLite backup API + integrity_check + عدّ صفوف الجداول."""
    if not src_path.exists():
        raise FileNotFoundError(str(src_path))
    tmp = BACKUP_DIR / f"{prefix}_{stamp}.db.tmp"
    final = BACKUP_DIR / f"{prefix}_{stamp}.db"
    src = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(str(tmp))
    src.backup(dst)
    check = dst.execute("PRAGMA integrity_check").fetchone()[0]
    counts = {}
    for t in tables:
        try:
            counts[t] = dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except sqlite3.Error:
            counts[t] = None
    src.close()
    dst.close()
    if check != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"integrity_check failed for {prefix}: {check}")
    tmp.replace(final)
    return final, counts


def prune(prefix, suffix):
    files = sorted(BACKUP_DIR.glob(f"{prefix}*{suffix}"))
    for old in files[:-KEEP]:
        old.unlink()
        log(f"pruned {old.name}")


def main():
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    status = {"time": datetime.now().isoformat(timespec="seconds"), "ok": False,
              "root": str(ROOT)}
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # 1) قاعدة البرنامج (المرجع)
        pos_final, pos_counts = backup_db(
            SRC_DB, stamp, "pos_data", ("clients", "orders", "transactions"))
        log(f"OK {pos_final.name} rows={pos_counts}")

        # 2) قاعدة النوتبوك (ضُمّت بأمر المالك 2026-10-16) — اختيارية لو مش موجودة بعد
        if NOTEBOOK_DB.exists():
            nb_final, nb_counts = backup_db(
                NOTEBOOK_DB, stamp, "notebook", ("notes", "categories"))
            log(f"OK {nb_final.name} rows={nb_counts}")
            status["notebook_file"] = nb_final.name
            status["notebook_bytes"] = nb_final.stat().st_size
            status["notebook_rows"] = nb_counts
        else:
            status["notebook_file"] = None
            log("notebook db not found — skipped (honest)")

        # 3) لقطة الـWorkspace (بلا قواعد حية — لها نسخها الموثقة)
        zpath = BACKUP_DIR / f"agent_workspace_{stamp}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            backup_root = BACKUP_DIR.resolve()
            for p in WORKSPACE.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(WORKSPACE)
                parts = set(rel.parts)
                is_notebook_data = (len(rel.parts) >= 2
                                    and rel.parts[0] == "notebook" and rel.parts[1] == "data")
                if (p.name == "backup.log"
                        or ".venv" in parts or "__pycache__" in parts
                        or p.name.endswith((".db", ".db-wal", ".db-shm", ".log", ".tmp"))
                        or is_notebook_data
                        or p.resolve().is_relative_to(backup_root)):
                    continue
                z.write(p, rel)

        # 4) تحقق وجود واتساق
        for p in (pos_final, zpath):
            if not p.exists() or p.stat().st_size == 0:
                raise RuntimeError(f"missing or empty: {p}")

        prune("pos_data_", ".db")
        prune("notebook_", ".db")
        prune("agent_workspace_", ".zip")
        status.update(ok=True, db_file=pos_final.name, db_bytes=pos_final.stat().st_size,
                      zip_file=zpath.name, row_counts=pos_counts)
        log(f"OK {pos_final.name} ({pos_final.stat().st_size} bytes) rows={pos_counts} + zip {zpath.name}")
    except Exception as e:
        status["error"] = str(e)
        log(f"FAILED: {e}")
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if status["ok"] else 1)


if __name__ == "__main__":
    main()