# -*- coding: utf-8 -*-
"""مواقيت الصلاة — منقولة كما هي من notebook/prayer.py (v1) بلا إنترنت.

الخارجة، الوادي الجديد، مصر — إحداثيات 25.4478 / 30.5463، منهجية مصرية.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

LAT = 25.4478
LON = 30.5463
FAJR_ANGLE = 19.5
ISHA_ANGLE = 17.5
PRAYER_KEYS = ["الفجر", "الشروق", "الظهر", "العصر", "المغرب", "العشاء"]


def _julian_day(d: date) -> float:
    y, m, day = d.year, d.month, d.day
    if m <= 2:
        y -= 1
        m += 12
    a = int(y / 100)
    b = 2 - a + int(a / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def _sun_position(jd: float) -> float:
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lambda_sun = L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)
    epsilon = 23.439 - 0.0000004 * n
    return math.degrees(math.asin(math.sin(math.radians(epsilon)) * math.sin(math.radians(lambda_sun))))


def _equation_of_time(jd: float) -> float:
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    epsilon = 23.439 - 0.0000004 * n
    y = math.tan(math.radians(epsilon / 2)) ** 2
    eot = y * math.sin(2 * math.radians(L)) - 2 * 0.01671 * math.sin(g) + 0.00028 * math.sin(2 * g)
    return math.degrees(eot) * 4


def _utc_offset(dt: datetime) -> float:
    local = dt.astimezone()
    off = local.utcoffset()
    return (off.total_seconds() / 60) if off else 120.0


def _time_for_angle(angle_deg: float, d: date, eot: float, decl: float, tz_h: float) -> Optional[datetime]:
    cos_h = ((math.sin(math.radians(angle_deg))
              - math.sin(math.radians(decl)) * math.sin(math.radians(LAT)))
             / (math.cos(math.radians(decl)) * math.cos(math.radians(LAT))))
    if cos_h < -1 or cos_h > 1:
        return None
    h = math.degrees(math.acos(cos_h))
    noon = 12.0 - eot / 60.0 + tz_h
    total = int(round((noon - h / 15.0) * 60))
    total = max(0, min(total, 1439))
    return datetime(d.year, d.month, d.day, total // 60, total % 60, 0)


def _for_date(d: date) -> Dict[str, datetime]:
    jd = _julian_day(d)
    decl = _sun_position(jd)
    eot = _equation_of_time(jd)
    tz = _utc_offset(datetime(d.year, d.month, d.day, 12)) / 60.0
    times: Dict[str, datetime] = {}
    fajr = _time_for_angle(FAJR_ANGLE, d, eot, decl, tz)
    if fajr:
        times["الفجر"] = fajr
    sunrise = _time_for_angle(90.833, d, eot, decl, tz)
    if sunrise:
        times["الشروق"] = sunrise
    dhuhr = _time_for_angle(0.0, d, eot, decl, tz)
    if dhuhr:
        times["الظهر"] = dhuhr
    asr_alt = 90.0 - math.degrees(math.atan(1.0 / (1.0 + math.tan(math.radians(abs(decl))))))
    asr = _time_for_angle(asr_alt, d, eot, decl, tz)
    if asr:
        times["العصر"] = asr
    maghrib = _time_for_angle(90.833, d, eot, decl, tz)
    if maghrib:
        times["المغرب"] = maghrib
    isha = _time_for_angle(ISHA_ANGLE, d, eot, decl, tz)
    if isha:
        times["العشاء"] = isha
    return times


def get_prayer_times(dt: Optional[datetime] = None) -> Dict[str, datetime]:
    return _for_date((dt or datetime.now()).date())


def next_prayer(dt: Optional[datetime] = None) -> Tuple[str, datetime, int]:
    now = dt or datetime.now()
    times = get_prayer_times(now)
    for name in PRAYER_KEYS:
        t = times.get(name)
        if t and t > now:
            return name, t, int((t - now).total_seconds() / 60)
    tomorrow = _for_date(now.date() + timedelta(days=1))
    fajr = tomorrow.get("الفجر") or now + timedelta(hours=12)
    return "الفجر", fajr, int((fajr - now).total_seconds() / 60)


def prayer_line() -> str:
    name, t, mins = next_prayer()
    return f"🕋 الصلاة القادمة: {name} بعد {mins} دقيقة ({t:%H:%M})"
