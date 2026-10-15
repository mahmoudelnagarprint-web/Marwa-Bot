import sqlite3, zipfile, json, sys
from datetime import datetime
from pathlib import Path

SRC_DB = Path(r"G:\ai\Elnagar POS\pos_data.db")
WORKSPACE = Path(r"G:\ai\Naggar Print POS Agent")
BACKUP_DIR = Path(r"G:\ai\Naggar Print POS Agent\backup")
KEEP = 8
STATUS = WORKSPACE / "memory" / "backup_status.json"
LOG = WORKSPACE / "scripts" / "backup.log"


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def open_src():
    try:
        return sqlite3.connect(f"file:{SRC_DB.as_posix()}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error as e:
        log(f"ro open failed ({e}); retrying normal open (backup only reads)")
        return sqlite3.connect(str(SRC_DB), timeout=30)


def prune(prefix, suffix):
    files = sorted(BACKUP_DIR.glob(f"{prefix}*{suffix}"))
    for old in files[:-KEEP]:
        old.unlink()
        log(f"pruned {old.name}")


def main():
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    status = {"time": datetime.now().isoformat(timespec="seconds"), "ok": False}
    try:
        if not SRC_DB.exists():
            raise FileNotFoundError(str(SRC_DB))
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        tmp = BACKUP_DIR / f"pos_data_{stamp}.db.tmp"
        final = BACKUP_DIR / f"pos_data_{stamp}.db"
        src = open_src()
        dst = sqlite3.connect(str(tmp))
        src.backup(dst)
        check = dst.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {t: dst.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("clients", "orders", "transactions")}
        src.close()
        dst.close()
        if check != "ok":
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"integrity_check failed: {check}")
        tmp.replace(final)

        zpath = BACKUP_DIR / f"agent_workspace_{stamp}.zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            backup_root = BACKUP_DIR.resolve()
            for p in WORKSPACE.rglob("*"):
                if not p.is_file():
                    continue
                rel = p.relative_to(WORKSPACE)
                parts = set(rel.parts)
                if (p.name == "backup.log"
                        or ".venv" in parts or "__pycache__" in parts
                        or p.resolve().is_relative_to(backup_root)):
                    continue
                z.write(p, rel)

        for p in (final, zpath):
            if not p.exists() or p.stat().st_size == 0:
                raise RuntimeError(f"missing or empty: {p}")

        prune("pos_data_", ".db")
        prune("agent_workspace_", ".zip")
        status.update(ok=True, db_file=final.name, db_bytes=final.stat().st_size,
                      zip_file=zpath.name, row_counts=counts)
        log(f"OK {final.name} ({final.stat().st_size} bytes) rows={counts}")
    except Exception as e:
        status["error"] = str(e)
        log(f"FAILED: {e}")
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.exit(0 if status["ok"] else 1)


if __name__ == "__main__":
    main()
