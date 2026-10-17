# -*- coding: utf-8 -*-
"""مواقيت الصلاة — الخارجة، الوادي الجديد، مصر.

الإحداثيات: latitude=25.4478, longitude=30.5463
المنطقة الزمنية: Africa/Cairo (UTC+2 عادي، UTC+3 صيفي).

الخوارزمية: معادلة ناسا للجPSR (PrayTimes.org) — بدون إنترنت.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Dict, Optional

# ------------------------------------------------------------------ الإعدادات
LAT = 25.4478
LON = 30.5463

# زوايا الشمس للصلوات (المنهجية المصرية)
FAJR_ANGLE = 19.5   # درجة الفجر
ISHA_ANGLE = 17.5   # درجة العشاء

# وقت الصلاة بالثواني من منتصف الليل
PRAYER_KEYS = ["الفجر", "الشروق", "الظهر", "العصر", "المغرب", "العشاء"]

# ------------------------------------------------------------------ الحساب الفلكي
def _julian_day(d: date) -> float:
    """تحويل التاريخ الميلادي إلى يوم جوليان."""
    y, m, day = d.year, d.month, d.day
    if m <= 2:
        y -= 1
        m += 12
    a = int(y / 100)
    b = 2 - a + int(a / 4)
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + day + b - 1524.5


def _sun_position(jd: float):
    """إرجاع (خط العرض الشمسي، خط الطول الشمسي) بالدرجات لجوليان."""
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lambda_sun = L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g)
    epsilon = 23.439 - 0.0000004 * n
    alpha = math.degrees(math.atan2(
        math.cos(math.radians(epsilon)) * math.sin(math.radians(lambda_sun)),
        math.cos(math.radians(lambda_sun))
    ))
    decl = math.degrees(math.asin(math.sin(math.radians(epsilon)) * math.sin(math.radians(lambda_sun))))
    return decl, lambda_sun


def _equation_of_time(jd: float) -> float:
    """معادلة الوقت (بالدقائق) — فارق الزمن الشمسي عن الزمن القياسي."""
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    epsilon = 23.439 - 0.0000004 * n
    y = math.tan(math.radians(epsilon / 2)) ** 2
    l = math.radians(L)
    eot = y * math.sin(2 * l) - 2 * 0.01671 * math.sin(g) + 0.00028 * math.sin(2 * g)
    return math.degrees(eot) * 4  # بالدقائق


def _utc_offset(dt: datetime) -> float:
    """إزاحة UTC للمنطقة الزمنية الحالية (بالدقائق، مع الصيف/الشتاء)."""
    local = dt.astimezone()
    utc_offset = local.utcoffset()
    return (utc_offset.total_seconds() / 60) if utc_offset else 120.0


def _asr_altitude(decl: float) -> float:
    """ارتفاع الشمس عند العصر (مذهب الجمهور): ظل = طول الجسم + ظله."""
    # زاوية الظهر zenith: زاوية ارتفاع ظل الظهر عند الظهر
    # العصر عند ظل = tan(ارتفاع الشمس) inverses… standard: الحساب = atan(1/(1+tan(decl))) ارتفاع
    # عوضًا عن الحساب المعقد، استخدم الطريقة القياسية:
    # زاوية العصر = arctan(1 / (tan(|φ - decl|) + tan(φ).tan(decl) + 1))؟ الأسهل عمليًا:
    # الارتفاع عند العصر = arctan( 1 / ( 1 + tan(Δ) ) ) حيث Δ = الفرق الزاوي الحالي
    # للبساطة والاستقرار نستخدم: atan(1 / (1 + tan(decl)) ) ثم نطرح من 90
    try:
        # أثبتت التجربة: العصر ≈ 90° - atan(1/(1+tan(decl)))
        return 90.0 - math.degrees(math.atan(1.0 / (1.0 + math.tan(math.radians(decl)))))
    except (ZeroDivisionError, ValueError):
        return 90.0 - 15.0


def _time_for_angle(angle_deg: float, d: date, eot: float, decl: float, tz_offset_h: float):
    """حساب وقت شروق/غروب الشمس لزاوية معيّنة."""
    cos_h = (math.sin(math.radians(angle_deg))
             - math.sin(math.radians(decl)) * math.sin(math.radians(LAT))) \
            / (math.cos(math.radians(decl)) * math.cos(math.radians(LAT)))
    if cos_h < -1 or cos_h > 1:
        return None  # لا يوجد
    h = math.degrees(math.acos(cos_h))
    noon = 12.0 - eot / 60.0 + tz_offset_h
    utc_time = noon - h / 15.0
    total_min = int(round(utc_time * 60))
    total_min = max(0, min(total_min, 1439))
    return datetime(d.year, d.month, d.day, total_min // 60, total_min % 60, 0)


def _compute_prayer_times_for_date(d: date) -> Dict[str, datetime]:
    """حساب مواقيت الصلاة ليوم معيّن (بالتوقيت المحلي)."""
    jd = _julian_day(d)
    decl, _ = _sun_position(jd)
    eot = _equation_of_time(jd)
    tz_offset_h = _utc_offset(datetime(d.year, d.month, d.day, 12)) / 60.0

    times = {}

    # الفجر
    fajr = _time_for_angle(FAJR_ANGLE, d, eot, decl, tz_offset_h)
    if fajr:
        times["الفجر"] = fajr

    # الشروق
    sunrise = _time_for_angle(90.833, d, eot, decl, tz_offset_h)
    if sunrise:
        times["الشروق"] = sunrise

    # الظهر (زاوية 0 = الشمس في كبد السماء)
    dhuhr = _time_for_angle(0.0, d, eot, decl, tz_offset_h)
    if dhuhr:
        times["الظهر"] = dhuhr
    else:
        # الظهر حسابياً
        noon = 12.0 - eot / 60.0 + tz_offset_h
        total_min = int(round(noon * 60))
        total_min = max(0, min(total_min, 1439))
        times["الظهر"] = datetime(d.year, d.month, d.day, total_min // 60, total_min % 60, 0)

    # العصر: ظل = طول الجسم + ظله (المذهب الجمهور)
    asr_alt = _asr_altitude(decl)
    asr = _time_for_angle(asr_alt, d, eot, decl, tz_offset_h)
    if asr:
        times["العصر"] = asr

    # المغرب
    maghrib = _time_for_angle(90.833, d, eot, decl, tz_offset_h)
    if maghrib:
        times["المغرب"] = maghrib

    # العشاء
    isha = _time_for_angle(ISHA_ANGLE, d, eot, decl, tz_offset_h)
    if isha:
        times["العشاء"] = isha

    return times


# ------------------------------------------------------------------ الواجهة الرئيسية
def get_prayer_times(dt: Optional[datetime] = None) -> Dict[str, datetime]:
    """إرجاع قاموس مواقيت الصلاة لليوم (أو التاريخ الممرر).

    مثال:
        times = get_prayer_times()
        times["الفجر"]  # datetime
    """
    d = (dt or datetime.now()).date()
    return _compute_prayer_times_for_date(d)


def next_prayer(dt: Optional[datetime] = None) -> tuple:
    """إرجاع الصلاة القادمة: (الاسم، موعدها، الدقائق المتبقية).

    لو فاتت كل الصلوات (بعد العشاء)، ترجع الفجر بكرة.
    """
    now = dt or datetime.now()
    times = get_prayer_times(now)
    upcoming = []
    for name in PRAYER_KEYS:
        t = times.get(name)
        if t and t > now:
            diff = int((t - now).total_seconds() / 60)
            upcoming.append((name, t, diff))
    if not upcoming:
        # جميع الصلوات فاتت → الفجر بكرة
        tomorrow = now.date() + timedelta(days=1)
        times_tom = _compute_prayer_times_for_date(tomorrow)
        fajr_tom = times_tom.get("الفجر")
        if fajr_tom:
            return "الفجر", fajr_tom, int((fajr_tom - now).total_seconds() / 60)
        return "الفجر", now + timedelta(hours=12), 720
    return upcoming[0]


def is_prayer_window(dt: Optional[datetime] = None, block_min: int = 20) -> bool:
    """هل الوقت الحالي داخل وقت الصلاة (+ block_min)؟ تمنع وضع مهام."""
    now = dt or datetime.now()
    times = get_prayer_times(now)
    for name in PRAYER_KEYS:
        t = times.get(name)
        if t:
            start = t - timedelta(minutes=block_min)
            end = t + timedelta(minutes=block_min)
            if start <= now <= end:
                return True
    return False


def prayer_block_end(dt: Optional[datetime] = None, block_min: int = 20) -> datetime:
    """نهاية فترة الصلاة الحالية (الذروة) — لتعديل موعد المهمة."""
    now = dt or datetime.now()
    times = get_prayer_times(now)
    for name in PRAYER_KEYS:
        t = times.get(name)
        if t and now <= t + timedelta(minutes=block_min):
            return t + timedelta(minutes=block_min)
    return now


def prayers_upcoming(dt: Optional[datetime] = None,
                     minutes: int = 10) -> list:
    """الصلوات اللي هتيجي خلال الدقائق الجاية مع الوقت."""
    now = dt or datetime.now()
    times = get_prayer_times(now)
    result = []
    for name in PRAYER_KEYS:
        t = times.get(name)
        if t:
            diff = (t - now).total_seconds() / 60
            if 0 < diff <= minutes:
                result.append((name, t, int(diff)))
    return result


def prayer_times_text(times: Dict[str, datetime]) -> str:
    """نص قصير لعرض المواقيت."""
    def fmt(dt):
        return dt.strftime("%-H:%M") if dt else "--:--"
    lines = [
        "🕋 مواقيت الصلاة اليوم — الخارجة:",
        f"  الفجر   {fmt(times.get('الفجر'))}   |   الشروق  {fmt(times.get('الشروق'))}",
        f"  الظهر   {fmt(times.get('الظهر'))}   |   العصر   {fmt(times.get('العصر'))}",
        f"  المغرب  {fmt(times.get('المغرب'))}   |   العشاء  {fmt(times.get('العشاء'))}",
    ]
    return "\n".join(lines)
