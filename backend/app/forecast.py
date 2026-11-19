"""Прогноз генерації СЕС на 1–3 (до 7) днів для Полтави — реальна погода Open-Meteo.

Джерело: https://api.open-meteo.com/v1/forecast (безкоштовно, без ключа), погодинно:
  global_tilted_irradiance (GTI, Вт/м², площина панелі: нахил 35°, південь — як у PVGIS),
  cloud_cover (%), temperature_2m (°C); добова sunshine_duration (с).
Радіація в Open-Meteo — середнє за ПОПЕРЕДНЮ годину (мітка 10:00 = 09:00–10:00).

Модель (усе «на папері»):
  T_cell = T_air + GTI × (NOCT − 20) / 800                 — NOCT = 45 °C → +3,1 °C на кожні 100 Вт/м²
  k_temp = 1 − 0,004 × (T_cell − 25), обмежено [0,75; 1,10] — −0,4 %/°C (c-Si); узимку холод дає приріст
  кВт·год на 1 кВт піку за годину = GTI / 1000 × PR × k_temp, PR = 0,80 (втрати системи, інвертор, кути)

Калібрування з PVGIS (data/pvgis_poltava.json, ті ж нахил/азимут, втрати 14 %): ефективний PR PVGIS
= E_m / H(i)_m змінюється від 0,76 (липень) до 0,89 (січень) — і це саме температурний ефект. Тому
коефіцієнт −0,4 %/°C застосовано симетрично (а не лише вище 25 °C): PR 0,80 × k_temp дає ≈ 0,75 улітку
і ≈ 0,86–0,88 узимку, тобто в межах ±3 % від PVGIS. Річний ефективний PR PVGIS = 0,796.

Кеш: data/forecast_cache.json, 1 година. Мережа недоступна → останній кеш із stale: true; кешу немає
(або бракує днів) → середній день PVGIS для цього місяця (source: «PVGIS (середнє)»).
"""

from __future__ import annotations

import calendar
import json
import math
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import solar

try:
    from zoneinfo import ZoneInfo

    KYIV = ZoneInfo("Europe/Kyiv")
except Exception:  # немає tzdata — спрощення UTC+2
    KYIV = timezone(timedelta(hours=2))

CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "forecast_cache.json"

LOCATION = {"name": "Полтава", "lat": solar.PVGIS_LAT, "lon": solar.PVGIS_LON}
TILT, AZIMUTH = solar.PVGIS_ANGLE, solar.PVGIS_ASPECT  # 35°, південь (Open-Meteo: 0 = південь, як у PVGIS)

# --- Модель ---
PR = 0.80  # performance ratio при 25 °C комірки
TEMP_COEF = -0.004  # −0,4 % потужності на 1 °C комірки (c-Si)
T_REF = 25.0
NOCT = 45.0  # °C, нагрів комірки над повітрям: (NOCT − 20) / 800 К на 1 Вт/м²
K_TEMP_MIN, K_TEMP_MAX = 0.75, 1.10

# --- Погода / сонце ---
SUNNY_CLOUD_MAX = 30  # середня денна хмарність < 30 % → «сонячно»
CLOUDY_CLOUD_MIN = 70  # ≥ 70 % → «похмуро», між — «мінлива хмарність»
SUN_GTI_MIN = 120  # Вт/м² — поріг «сонячної години» (WMO: 120 Вт/м² прямої радіації), якщо немає sunshine_duration

# --- Кеш / мережа ---
TTL_S = 3600
FETCH_DAYS = 7  # тягнемо тиждень: якщо мережа зникне, кешу вистачить надовше
MAX_DAYS = 7
TIMEOUT_S = 6
RETRY_AFTER_FAIL_S = 120  # після збою мережі не пробуємо знову щозапиту

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
    "latitude": LOCATION["lat"], "longitude": LOCATION["lon"],
    "hourly": "global_tilted_irradiance,cloud_cover,temperature_2m",
    "daily": "sunshine_duration",
    "tilt": TILT, "azimuth": AZIMUTH,
    "timezone": "Europe/Kyiv", "forecast_days": FETCH_DAYS,
})

SRC_LIVE = "Open-Meteo"
SRC_PVGIS = "PVGIS (середнє)"
LABELS = {0: "сьогодні", 1: "завтра", 2: "післязавтра"}
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "нд"]

_lock = threading.Lock()
_last_fail = 0.0
_mem: dict | None = None  # останній прочитаний/записаний кеш


def now() -> datetime:
    return datetime.now(KYIV)


# ---------------------------------------------------------------- модель
def cell_temp(gti: float, t_air: float) -> float:
    return t_air + gti * (NOCT - 20) / 800


def k_temp(gti: float, t_air: float) -> float:
    k = 1 + TEMP_COEF * (cell_temp(gti, t_air) - T_REF)
    return min(K_TEMP_MAX, max(K_TEMP_MIN, k))


def gen_kwh_per_kwp(gti: float, t_air: float | None) -> float:
    """кВт·год на 1 кВт піку за годину із середнім GTI (Вт/м²)."""
    if gti <= 0:
        return 0.0
    k = k_temp(gti, T_REF if t_air is None else t_air)
    return gti / 1000 * PR * k


def pvgis_avg_day(d: date) -> float:
    """Середня добова генерація 1 кВт піку за PVGIS: E_m місяця ÷ днів у місяці."""
    return solar.pvgis_monthly()[d.month - 1] / calendar.monthrange(d.year, d.month)[1]


def pvgis_effective_pr(month: int) -> float:
    d = json.loads(solar.PVGIS_FILE.read_text(encoding="utf-8"))
    r = next(x for x in d["outputs"]["monthly"]["fixed"] if x["month"] == month)
    return r["E_m"] / r["H(i)_m"]


def weather_label(cloud_day: float | None, ratio: float | None) -> str:
    if cloud_day is None:  # немає хмарності (запасний PVGIS) — за відношенням до норми
        r = 1.0 if ratio is None else ratio
        return "сонячно" if r >= 1.3 else "похмуро" if r < 0.5 else "мінлива хмарність"
    if cloud_day < SUNNY_CLOUD_MAX:
        return "сонячно"
    return "похмуро" if cloud_day >= CLOUDY_CLOUD_MIN else "мінлива хмарність"


def day_label(d: date, today: date) -> str:
    off = (d - today).days
    return LABELS.get(off) or f"{WEEKDAYS[d.weekday()]}, {d:%d.%m}"


# ---------------------------------------------------------------- збирання днів
def _day(d: date, today: date, hourly: list[dict], sun_hours: float | None, source: str) -> dict:
    total = sum(h["gen_kwh_per_kwp"] for h in hourly)
    norm = pvgis_avg_day(d)
    ratio = total / norm if norm else None
    light = [h for h in hourly if h["gti_wm2"] > 0 and h["cloud_pct"] is not None]
    cloud = sum(h["cloud_pct"] for h in light) / len(light) if light else None
    if sun_hours is None:
        sun_hours = sum(1 for h in hourly if h["gti_wm2"] >= SUN_GTI_MIN)
    peak = max(hourly, key=lambda h: h["gen_kwh_per_kwp"]) if hourly else None
    return {
        "date": d.isoformat(),
        "label": day_label(d, today),
        "source": source,
        "hourly": hourly,
        "gen_kwh_per_kwp_day": round(total, 2),
        "pvgis_avg_kwh_per_kwp_day": round(norm, 2),
        "ratio_to_normal": round(ratio, 2) if ratio is not None else None,
        "weather": weather_label(cloud, ratio),
        "cloud_pct_day": round(cloud) if cloud is not None else None,
        "sun_hours": round(sun_hours, 1),
        "peak_hour": peak["hour"] if peak and peak["gen_kwh_per_kwp"] > 0 else None,
    }


def days_from_open_meteo(raw: dict, today: date) -> list[dict]:
    h = raw["hourly"]
    gti_key = "global_tilted_irradiance" if "global_tilted_irradiance" in h else "shortwave_radiation"
    by_day: dict[date, list[dict]] = {}
    for i, ts in enumerate(h["time"]):
        t = datetime.fromisoformat(ts)
        gti = h[gti_key][i]
        temp = h.get("temperature_2m", [None] * len(h["time"]))[i]
        cloud = h.get("cloud_cover", [None] * len(h["time"]))[i]
        gti = max(0.0, float(gti or 0.0))
        by_day.setdefault(t.date(), []).append({
            "hour": t.hour,
            "gti_wm2": round(gti, 1),
            "cloud_pct": None if cloud is None else round(float(cloud)),
            "temp_c": None if temp is None else round(float(temp), 1),
            "gen_kwh_per_kwp": round(gen_kwh_per_kwp(gti, temp), 4),
        })
    sun = {}
    daily = raw.get("daily") or {}
    for ds, sec in zip(daily.get("time", []), daily.get("sunshine_duration", [])):
        if sec is not None:
            sun[date.fromisoformat(ds)] = sec / 3600
    return [_day(d, today, rows, sun.get(d), SRC_LIVE) for d, rows in sorted(by_day.items()) if d >= today]


def _daylight(d: date) -> tuple[float, float]:
    """Схід і захід (сонячний час ≈ місцевий + поправка), год — для форми запасного профілю."""
    decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + d.timetuple().tm_yday) / 365)
    lat = math.radians(LOCATION["lat"])
    half = math.degrees(math.acos(max(-1.0, min(1.0, -math.tan(lat) * math.tan(decl))))) / 15
    # сонячний полудень у Полтаві: 12:00 − (34,55° − 30°)/15 год за київським стандартним часом ≈ 11:42
    noon = 12 - (LOCATION["lon"] - 30) / 15 + (1 if d.month in range(4, 11) else 0)  # грубо: літній час
    return noon - half, noon + half


def pvgis_fallback_day(d: date, today: date) -> dict:
    """Середній день PVGIS, розкладений по годинах синусоїдою між сходом і заходом."""
    e_day = pvgis_avg_day(d)
    rise, sset = _daylight(d)
    w = []
    for hr in range(24):  # як в Open-Meteo: мітка години = кінець інтервалу
        a, b = max(hr - 1, rise), min(hr, sset)
        if b <= a:
            w.append(0.0)
            continue
        f = lambda x: -math.cos(math.pi * (x - rise) / (sset - rise))  # ∫ sin
        w.append(f(b) - f(a))
    s = sum(w) or 1
    hourly = []
    for hr, wi in enumerate(w):
        gen = e_day * wi / s
        hourly.append({"hour": hr, "gti_wm2": round(gen / PR * 1000, 1), "cloud_pct": None, "temp_c": None,
                       "gen_kwh_per_kwp": round(gen, 4)})
    return _day(d, today, hourly, None, SRC_PVGIS)


# ---------------------------------------------------------------- мережа і кеш
def fetch_open_meteo() -> dict:
    req = urllib.request.Request(OPEN_METEO_URL, headers={"User-Agent": "energo-forecast/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        raw = json.loads(r.read().decode("utf-8"))
    if "hourly" not in raw or "time" not in raw["hourly"]:
        raise ValueError(f"Неочікувана відповідь Open-Meteo: {str(raw)[:200]}")
    return raw


def load_cache() -> dict | None:
    global _mem
    if _mem is not None and _mem.get("_path") == str(CACHE_FILE):
        return _mem
    try:
        c = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        c["_path"] = str(CACHE_FILE)
        _mem = c
        return c
    except (OSError, ValueError):
        return None


def save_cache(raw: dict, fetched_at: datetime) -> dict:
    global _mem
    c = {"fetched_at": fetched_at.isoformat(timespec="seconds"), "url": OPEN_METEO_URL,
         "note": "Кеш відповіді Open-Meteo (1 год); при збої мережі віддається зі stale: true", "raw": raw}
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE_FILE)
    c["_path"] = str(CACHE_FILE)
    _mem = c
    return c


def _age_s(c: dict, t: datetime) -> float:
    try:
        return (t - datetime.fromisoformat(c["fetched_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return float("inf")


def get_forecast(days: int = 3, force: bool = False) -> dict:
    global _last_fail
    days = max(1, min(MAX_DAYS, int(days)))
    t = now()
    today = t.date()
    stale, error = False, None
    cache = load_cache()
    if force or cache is None or _age_s(cache, t) >= TTL_S:
        with _lock:
            cache = load_cache()  # інший потік міг уже оновити
            if force or cache is None or _age_s(cache, t) >= TTL_S:
                if not force and time.monotonic() - _last_fail < RETRY_AFTER_FAIL_S and _last_fail:
                    error = "мережа недоступна (повтор пізніше)"
                else:
                    try:
                        cache = save_cache(fetch_open_meteo(), t)
                    except Exception as e:  # мережа, таймаут, поганий JSON, диск
                        _last_fail = time.monotonic()
                        error = f"{type(e).__name__}: {e}"[:300]
                stale = error is not None and cache is not None

    out_days: list[dict] = []
    if cache is not None:
        try:
            out_days = days_from_open_meteo(cache["raw"], today)[:days]
        except Exception as e:  # пошкоджений кеш
            error = error or f"кеш пошкоджено: {e}"
            out_days, cache, stale = [], None, False
    have = {d["date"] for d in out_days}
    for i in range(days):  # бракує днів (немає кешу або він застарів) — середнє PVGIS
        d = today + timedelta(days=i)
        if d.isoformat() not in have:
            out_days.append(pvgis_fallback_day(d, today))
    out_days.sort(key=lambda x: x["date"])

    live = any(d["source"] == SRC_LIVE for d in out_days)
    m = today.month
    return {
        "source": SRC_LIVE if live else SRC_PVGIS,
        "stale": bool(stale and live),
        "fetched_at": cache["fetched_at"] if live else t.isoformat(timespec="seconds"),
        "location": dict(LOCATION),
        "days": out_days,
        "error": error,
        "model": {
            "formula": "кВт·год/кВт = GTI/1000 × PR × (1 − 0,004 × (T_комірки − 25)); "
                       "T_комірки = T_повітря + GTI × (NOCT − 20)/800",
            "pr": PR, "temp_coef_per_c": TEMP_COEF, "noct_c": NOCT, "tilt_deg": TILT, "azimuth_deg": AZIMUTH,
            "pvgis_effective_pr_month": round(pvgis_effective_pr(m), 3),
            "hour_note": "Радіація — середнє за попередню годину (hour=10 → 09:00–10:00).",
        },
    }
