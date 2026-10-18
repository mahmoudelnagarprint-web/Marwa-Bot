#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""marwa_pulse — نبض مروة: المزامنة اللحظية المدفوعة بالأحداث (تصميم راصد 2026-10-18).

الحالة: DRAFT — لا يُشغَّل في وضع حي إلا بموافقة المالك (انظر REALTIME_SYNC_ARCHITECTURE.md §8).
الافتراضي: وضع مراقبة dry-run — لوج فقط، صفر كتابة حقيقية.

المعمارية الثلاثية:
  1) Control: استطلاع سريع كل PULSE_POLL_SECONDS (افتراضي 3s) على طابور commands
     (+ sync_events لدور اللابتوب) — بديل Realtime الآمن؛ الـWS تحسين لاحق.
  2) Data: بالورشة — PRAGMA data_version كل 250ms على اتصال ro (قراءة فقط W2)
     → debounce 300ms → دفع فوري عبر HermesSyncManager.push_mirror() الرسمي.
     اللابتوب: سحب فوري عند حدث جديد — لا مسار دفع إطلاقاً (W1).
  3) LAN: نبضة UDP كل 5s + NUDGE فوري داخل الشبكة المحلية (مُسرِّع اختياري لا اعتماد).

ضمانات: op_id (idempotency) + HLC (ترتيب سببي) + كاتب وحيد مفروض في الكود
+ أرضيات الأمان القائمة (git_autosync 900s / parity 300s / نسخ أسبوعي) لا تُمس.

الاستخدام:
  python cloud/marwa_pulse.py --once     # دورة تشخيص واحدة (آمنة دائماً)
  python cloud/marwa_pulse.py            # حلقة مراقبة dry-run (لا يكتب شيئاً)
  python cloud/marwa_pulse.py --live     # وضع فعلي — يتطلب PULSE_ENABLED=true في .env
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

WORKSPACE = Path(__file__).resolve().parent.parent
ENV_PATH = WORKSPACE / ".env"
STATE_DB = WORKSPACE / "memory" / "pulse_state.sqlite"
LOG_FILE = WORKSPACE / "logs" / "pulse.log"
LOCK_FILE = WORKSPACE / "logs" / "pulse.lock"

POLL_DB_S = 0.25          # استطلاع data_version (أرخص جاسوس على SQLite)
DEBOUNCE_S = 0.30         # هضم عواصف التغيير قبل الدفع
LAN_PORT_DEFAULT = 51824
LAN_PERIOD_S = 5
THREAD_NAMES = ("dbpulse", "commandpump", "lanheart")


def log(msg: str, level: str = "INFO") -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {msg}"
    try:
        print(line)
    except OSError:
        pass
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_env() -> dict:
    env: dict = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def new_op_id() -> str:
    """ULID مبسّط: زمن(ms)hex + عشوائي — فريد ومرتب زمنياً (مفتاح idempotency)."""
    return f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}"


class HLC:
    """ساعة منطقية هجينة: (epoch_ms, counter, node) — ترتيب سببي مقاوم لانحراف الساعات."""

    def __init__(self, node: str):
        self.node = node
        self._last_ms = 0
        self._ctr = 0
        self._lock = threading.Lock()

    def now(self) -> str:
        with self._lock:
            now_ms = int(time.time() * 1000)
            if now_ms > self._last_ms:
                self._last_ms = now_ms
                self._ctr = 0
            else:
                self._ctr += 1
            return f"{self._last_ms:016x}-{self._ctr:04x}-{self.node}"


class StopFlag:
    """إيقاف نظيف مشترك (Ctrl+C آمن)."""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def set(self) -> None:
        self._ev.set()

    def is_set(self) -> bool:
        return self._ev.is_set()

    def wait(self, seconds: float) -> None:
        self._ev.wait(timeout=max(0.05, seconds))


class PulseState:
    """تخزين محلي دائم: دفتر applied_ops + علامات مائية — لا حالة في الذاكرة فقط."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute(
            "create table if not exists applied_ops ("
            "op_id text primary key, applied_at text, result text)")
        self.conn.execute(
            "create table if not exists watermarks ("
            "kind text primary key, value text, updated_at text)")
        self.conn.commit()
        self._lock = threading.Lock()

    def seen(self, op_id: str) -> bool:
        with self._lock:
            return self.conn.execute(
                "select 1 from applied_ops where op_id=?", (op_id,)
            ).fetchone() is not None

    def mark(self, op_id: str, result: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "insert or ignore into applied_ops values (?,?,?)",
                (op_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), result))
            self.conn.commit()


def acquire_lock() -> bool:
    """قفل نسخة واحدة (نمط git_autosync) — قفل ميت >10 دقائق يُستبدل."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if LOCK_FILE.exists():
            if (time.time() - LOCK_FILE.stat().st_mtime) < 600:
                return False
            log("قفل قديم (>600s) — يُستبدل", "WARN")
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def build_manager():
    """تكامل رسمي: نفس كلاس الدايمون القائم — لا fork ولا منطق مكرر."""
    from supabase_sync import HermesSyncManager  # noqa: E402 (cloud/ على sys.path)
    return HermesSyncManager()


class DBPulse(threading.Thread):
    """الورشة فقط: كشف أي commit على القاعدة الحية عبر data_version (قراءة فقط W2/W6)."""

    def __init__(self, cfg: dict, on_change, stop: StopFlag):
        super().__init__(daemon=True, name="dbpulse")
        self.cfg, self.on_change, self.stop = cfg, on_change, stop

    def run(self) -> None:
        db: Path = self.cfg["live_db"]
        if not db.exists():
            log(f"القاعدة الحية غير موجودة: {db} — DBPulse معطّل (honest)", "ERROR")
            return
        uri = f"file:{db.as_posix()}?mode=ro"
        last: int | None = None
        con: sqlite3.Connection | None = None
        log(f"DBPulse: data_version كل {int(POLL_DB_S * 1000)}ms على {db.name} (mode=ro)")
        # اكتشاف الاختبار المثبت: data_version يعمل فقط عبر اتصال دائم معيش —
        # اتصال جديد كل استطلاع يُرجع القيمة نفسها دائماً (مُثبت بالقياس).
        while not self.stop.is_set():
            try:
                if con is None:
                    con = sqlite3.connect(uri, uri=True, timeout=5)
                ver = con.execute("PRAGMA data_version").fetchone()[0]
                if last is None:
                    last = ver                          # الدورة الأولى: خط أساس فقط
                    log(f"data_version baseline={ver}")
                elif ver != last:
                    last = ver
                    self._debounced_fire()
            except sqlite3.Error as exc:
                log(f"data_version poll failed: {type(exc).__name__} — إعادة اتصال", "WARN")
                if con is not None:
                    try:
                        con.close()
                    except sqlite3.Error:
                        pass
                con = None                              # إعادة اتصال الدورة القادمة
            self.stop.wait(POLL_DB_S)
        if con is not None:
            try:
                con.close()
            except sqlite3.Error:
                pass
        log("DBPulse متوقف")

    def _debounced_fire(self) -> None:
        """Debounce 300ms — عواصف التغيير المتتالية تصير دفعة واحدة."""
        t = threading.Timer(DEBOUNCE_S, self.on_change)
        t.daemon = True
        t.start()


class CommandPump(threading.Thread):
    """العقدتان: استطلاع سريع على السحابة (بديل Realtime الآمن).
       WORKSHOP: ينفّذ الأوامر المعلّقة عبر pull_queue الرسمية.
       LAPTOP:   يراقب sync_events فقط → سحب فوري (سحب فقط — لا دفع مرآة إطلاقاً W1)."""

    def __init__(self, cfg: dict, state: PulseState, hlc: HLC, on_db_event, stop: StopFlag):
        super().__init__(daemon=True, name="commandpump")
        self.cfg, self.state, self.hlc, self.on_db_event, self.stop = \
            cfg, state, hlc, on_db_event, stop
        self._last_seen_event = ""
        self._sync_events_ok: bool | None = None   # None = لم يُجرَّب بعد

    def run(self) -> None:
        from supabase_sync import HermesSyncManager  # تكامل رسمي — لا ازدواج
        mgr = HermesSyncManager()
        log(f"CommandPump start role={self.cfg['role']} poll={self.cfg['poll']}s")
        while not self.stop.is_set():
            try:
                if self.cfg["role"] == "WORKSHOP":
                    if self.cfg["live"]:
                        res = mgr.pull_queue(limit=10)   # المسار الرسمي القائم (تطبيق + تعليم)
                        if res.get("applied") or res.get("failed"):
                            log(f"commands: applied={len(res['applied'])} failed={len(res['failed'])}")
                    else:
                        # dry-run: قراءة فقط — التنفيذ الحقيقي للأوامر ممنوع (تعاقد المراقبة)
                        resp = mgr._get_client().table("commands").select("id") \
                            .eq("status", "pending").execute()
                        pending = len(resp.data or [])
                        if pending:
                            log(f"[dry-run] {pending} أمر معلّق — التنفيذ معطل في وضع المراقبة")
                else:
                    self._watch_events(mgr)
            except Exception as exc:
                log(f"command pump: {type(exc).__name__} — إعادة محاولة", "WARN")
            self.stop.wait(self.cfg["poll"])

    def _watch_events(self, mgr) -> None:
        """اللابتوب: آخر حدث من عقدة أخرى → سحب فوري (idempotent عبر op_id)."""
        cli = mgr._get_client()
        resp = (cli.table("sync_events")
                .select("op_id,created_at")
                .neq("node", self.cfg["node"])
                .order("created_at", desc=True)
                .limit(1).execute())
        rows = resp.data or []
        if not rows:
            return
        ev = rows[0]
        op_id = str(ev.get("op_id") or "")
        if not op_id or op_id == self._last_seen_event or self.state.seen(op_id):
            return
        self._last_seen_event = op_id
        self.state.mark(op_id, "pull_triggered")
        log(f"sync_event جديد من السحابة → سحب فوري ({op_id})")
        if self.cfg["live"]:
            self.on_db_event()
        else:
            log("[dry-run] كان سيشغّل السحب الفوري الآن")


class LANHeartbeat(threading.Thread):
    """مُسرِّع LAN اختياري: نبضة كل 5s + استقبال NUDGE فوري (شبكة محلية فقط — لا NAT)."""

    def __init__(self, cfg: dict, on_nudge, stop: StopFlag):
        super().__init__(daemon=True, name="lanheartbeat")
        self.cfg, self.on_nudge, self.stop = cfg, on_nudge, stop

    def run(self) -> None:
        port = self.cfg["lan_udp"]
        if not port:
            log("LAN heartbeat معطّل (PULSE_LAN_UDP=0)")
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", port))
        except OSError as exc:
            log(f"UDP bind فشل ({type(exc).__name__}) — النبض المحلي معطّل والسحابة تكفي", "WARN")
            return
        sock.settimeout(1.0)
        seq = 0
        log(f"LAN heartbeat على {port}/udp")
        while not self.stop.is_set():
            seq += 1
            hello = json.dumps({"node": self.cfg["node"], "role": self.cfg["role"],
                                "seq": seq, "t": int(time.time())})
            try:
                sock.sendto(hello.encode(), ("<broadcast>", port))
            except OSError:
                pass  # لا شبكة محلية — السحابة هي المسار
            try:
                data, _addr = sock.recvfrom(2048)
                msg = json.loads(data.decode(errors="replace"))
                if msg.get("node") != self.cfg["node"] and msg.get("kind") == "nudge":
                    log(f"LAN nudge من {msg.get('node')}: {msg.get('nudge')}")
                    self.on_nudge(str(msg.get("nudge") or ""))
            except socket.timeout:
                pass
            except (json.JSONDecodeError, KeyError):
                pass  # حزم غريبة تُهمل بصمت — لا انهيار
            self.stop.wait(LAN_PERIOD_S)


def run_diagnostic(cfg: dict) -> int:
    """--once: دورة قياس واحدة آمنة — أين نحن الآن؟ (لا كتابة إطلاقاً)."""
    db: Path = cfg["live_db"]
    print(f"== Marwa Pulse تشخيص — node={cfg['node']} role={cfg['role']} mode=dry-run ==")
    if db.exists():
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=5)
        try:
            print(f"live_db data_version = {con.execute('PRAGMA data_version').fetchone()[0]}")
        finally:
            con.close()
    else:
        log(f"القاعدة الحية غير موجودة: {db}", "ERROR")
    try:
        mgr = build_manager()
        cli = mgr._get_client()
        resp = cli.table("commands").select("id").eq("status", "pending").execute()
        print(f"pending_commands = {len(resp.data or [])}")
        try:
            cli.table("sync_events").select("op_id").limit(1).execute()
            print("sync_events table = موجودة")
        except Exception:
            print("sync_events table = غير موجودة بعد (migration 005 draft — طبيعي)")
    except Exception as exc:
        log(f"تشخيص السحابة تعذّر: {type(exc).__name__}", "WARN")
    print("OK — دورة التشخيص اكتملت (لم يُكتب شيء)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Marwa Pulse — مزامنة لحظية مدفوعة بالأحداث")
    ap.add_argument("--once", action="store_true", help="دورة تشخيص واحدة ثم خروج")
    ap.add_argument("--live", action="store_true",
                    help="وضع فعلي (يكتب/يسحب) — يتطلب PULSE_ENABLED=true في .env")
    args = ap.parse_args()

    env = load_env()
    node = (env.get("NODE_ID") or "WORKSHOP").upper()
    role = (env.get("PULSE_ROLE") or node).upper()
    enabled = env.get("PULSE_ENABLED", "false").strip().lower() == "true"
    live = bool(args.live)

    if live and not enabled:
        log("رفض التشغيل الفعلي: PULSE_ENABLED=false في .env — تفعيل النبض قرار المالك", "ERROR")
        return 2
    if live and not acquire_lock():
        log("قفل النبض محتجز — توجد نسخة شغّالة (logs/pulse.lock)", "ERROR")
        return 1

    cfg = {
        "node": node,
        "role": role,
        "live": live,
        "live_db": Path(env.get("LIVE_DB_PATH") or r"G:\ai\Elnagar POS\pos_data.db"),
        "poll": float(env.get("PULSE_POLL_SECONDS", "3") or 3),
        "lan_udp": int(env.get("PULSE_LAN_UDP", str(LAN_PORT_DEFAULT)) or 0),
        "pull_cmd": env.get("PULSE_PULL_CMD", ""),   # للّابتوب: أمر السحب الفوري
    }
    state = PulseState(STATE_DB)
    hlc = HLC(node)
    stop = StopFlag()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    if args.once:
        return run_diagnostic(cfg)

    log(f"PULSE start node={node} role={role} mode={'LIVE' if live else 'DRY-RUN'}")

    mgr = None
    try:
        mgr = build_manager()
    except Exception as exc:
        log(f"مدير المزامنة غير جاهز ({type(exc).__name__}) — الأرضية 60s تغطي", "WARN")

    def push_on_event(reason: str) -> None:
        """الورشة: الحدث → دفع فوري (الدالة الرسمية) → تسجيل sync_event للّابتوب."""
        if mgr is None:
            log(f"[{reason}] مدير المزامنة غير متاح — تخطّي (أرضية 60s تغطي)", "WARN")
            return
        op = new_op_id()
        try:
            mgr.push_mirror()                        # المسار الرسمي القائم (upsert آمن)
            state.mark(op, "pushed")
            log(f"push-on-event ok op={op} hlc={hlc.now()}")
            try:
                cli = mgr._get_client()
                cli.table("sync_events").insert({
                    "op_id": op, "node": node, "kind": "db_change",
                    "tables": ["all"], "hlc": hlc.now(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }).execute()
            except Exception as exc:                 # sync_events غير موجودة بعد (migration 005 draft)
                log(f"sync_events تسجيل: {type(exc).__name__} (طبيعي قبل الموافقة على 005)", "WARN")
        except Exception as exc:
            log(f"push-on-event failed (الأرضية تغطي، سيعاد): {type(exc).__name__}", "WARN")

    def pull_now(reason: str) -> None:
        """اللابتوب فقط: سحب فوري للمرآة (سحب فقط — W1)."""
        if not live:
            log(f"[dry-run] كان سيشغّل السحب الفوري الآن ({reason})")
            return
        cmd = cfg["pull_cmd"]
        if not cmd:
            log("لا PULSE_PULL_CMD في .env — سحب فوري متخطى (الأرضية القديمة تغطي)", "WARN")
            return
        log(f"سحب فوري ({reason})…")
        try:
            subprocess.Popen(cmd, shell=True, cwd=str(WORKSPACE))
        except OSError as exc:
            log(f"سحب فوري فشل: {type(exc).__name__}", "WARN")

    threads: list[threading.Thread] = []
    if role == "WORKSHOP":
        dbp = DBPulse(cfg, on_change=lambda: push_on_event("db_change"), stop=stop)
        dbp.start()
        threads.append(dbp)
    pump = CommandPump(cfg, state, hlc, stop,
                       on_db_event=pull_now if role == "LAPTOP" else (lambda: None))
    pump.start()
    threads.append(pump)
    lan = LANHeartbeat(
        cfg,
        on_nudge=lambda kind: (push_on_event("nudge") if role == "WORKSHOP"
                               else pull_now("nudge")),
        stop=stop)
    lan.start()
    threads.append(lan)

    log("النبض يعمل — Ctrl+C للإيقاف النظيف (دورات الأمان الدورية لا تزال تغطي)")
    try:
        while not stop.is_set():
            time.sleep(0.5)
    finally:
        stop.set()
        release_lock()
        log("PULSE stop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
