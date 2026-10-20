#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sasa_hardware_link.py — دايمون العتاد الحقيقي للورشة (2026-10-20)
رصد حي كل 3 ثوانٍ:
  1) Epson L1800 عبر win32print (خطأ/حالة/عدد مهام الطباعة الحقيقية)
  2) كاتر بلوتر أو ليزر عبر pyserial (فتح منفذ COM للفحص — عبر معرفات في .env أو افتراضي)
  ثم كتابة hardware_state.json (ملك صاصا — لا قاعدة بيانات) في workspaces/sasa_devices/active_workspaces/
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # workspaces/sasa_devices → .../Naggar Print POS Agent
ROOT = ROOT if ROOT.name == 'Naggar Print POS Agent' else Path('G:/ai/Naggar Print POS Agent')
WS = ROOT / 'workspaces' / 'sasa_devices'
STATE_DIR = WS / 'active_workspaces'
STATE_FILE = STATE_DIR / 'hardware_state.json'

# ملاحظة صاصا: المنافد الحقيقية — COM3 هو Prolific USB-to-Serial (مقص على الواضح للكاتر/الليزر)
DEFAULTS = {
    'epson_printer': 'EPSON L1800 Series',
    'cutter_com': os.environ.get('CUTTER_COM', 'COM3'),
    'laser_com': os.environ.get('LASER_COM', ''),  # ليزر متصل بمنفذ آخر — اكتشف يدوياً وحدّد LASER_COM
}

import win32print
from serial.tools import list_ports


def epson_stats(name: str) -> dict:
    """حالة طابعة Epson الحقيقية عبر واجهة الويندوز (Print Spooler)."""
    try:
        h = win32print.OpenPrinter(name)
        try:
            info = win32print.GetPrinter(h, 2)
            attrs = info.get('Attributes', 0)
            jobs = win32print.EnumJobs(h, 0, 99, 1)
            statuses, total_pages = [], 0
            for j in jobs:
                st = j.get('Status', 0)
                for bit, label in [
                    (0x00000400, 'printing'), (0x00000200, 'paused'), (0x00000010, 'error'),
                    (0x00000020, 'pending'), (0x00000800, 'deleting'), (0x00000040, 'offline'),
                ]:
                    if st & bit:
                        statuses.append(label)
                total_pages += int(j.get('TotalPages', 0) or 0)
            online = not (attrs & 0x400)  # WINSTATUS_OFFLINE bit 0x400 (PRINTER_ATTRIBUTE_WORK_OFFLINE=0x400)
            state = ('printing' if 'printing' in statuses or jobs else 'idle') if online else 'offline'
            return {
                'state': state, 'online': online, 'jobs': len(jobs),
                'statuses': statuses or (['ready'] if online else ['offline']),
                'total_pages_in_queue': total_pages,
            }
        finally:
            win32print.ClosePrinter(h)
    except Exception as exc:
        return {'state': 'error', 'online': False, 'jobs': 0, 'statuses': [], 'error': str(exc)[:120]}


def serial_alive(port: str) -> dict:
    """فحص منفذ COM فارغ للفتح (الكاتر/الليزر يظهرون على COM3)."""
    if not port:
        return {'state': 'unmapped', 'online': False, 'port': None}
    try:
        found = [p.device for p in list_ports.comports()]
        if port not in found:
            return {'state': 'offline', 'online': False, 'port': port, 'note': 'المنفذ غير موجود في النظام'}
        import serial
        try:
            s = serial.Serial(port, timeout=0.15)
            s.close()
            return {'state': 'idle', 'online': True, 'port': port, 'note': 'المنفذ متاح — ماكينة متصلة'}
        except serial.SerialException as exc:
            # منفذ موجود ولكن مشغول → ماكينة شغالة أو برنامج آخر فتحه
            return {'state': 'busy', 'online': True, 'port': port, 'note': str(exc)[:80]}
    except Exception as exc:
        return {'state': 'error', 'online': False, 'port': port, 'error': str(exc)[:120]}


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    interval = float(os.environ.get('HW_INTERVAL', '3'))
    while True:
        cutter = serial_alive(DEFAULTS['cutter_com'])
        laser = serial_alive(DEFAULTS['laser_com']) if DEFAULTS['laser_com'] else {'state': 'unmapped', 'online': False, 'note': 'حدّد LASER_COM في .env'}
        state = {
            'updated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'win32print + pyserial — عتاد حقيقي (cyberr-red-line: القراءة يفحص OS فقط، صفر كتابة في pos)',
            'epson': epson_stats(DEFAULTS['epson_printer']),
            'cutter': cutter,
            'laser': laser,
            'printers_seen': [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)],
        }
        tmp = STATE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, STATE_FILE)
        time.sleep(interval)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print('hardware link دايمون توقف')
