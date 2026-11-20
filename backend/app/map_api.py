"""Публічна карта всіх будівель: GET /api/map.

БЕЗПЕКА (правило треку): «Не публікуйте на публічних картах інформацію про те, які заклади мають
генератори чи автономне живлення». Тому тут ЛИШЕ категорія, споживання, ПОТЕНЦІАЛ нової СЕС
(рекомендація з solar.py) і якість даних. Жодних полів про наявні СЕС, акумулятори, генератори,
автономність, індекс енергонезалежності чи резервне живлення — не додавати (є тест-перелік полів).
"""

from __future__ import annotations

import hashlib
import math

from fastapi import APIRouter

from . import solar
from .geocode import PRECISIONS
from .solar_api import BASE_YEAR, _exclusion

router = APIRouter(tags=["Карта"])

JITTER_MIN_M, JITTER_MAX_M = 40.0, 150.0  # зсув точок «населений пункт», щоб не накладались
M_PER_DEG_LAT = 111_320.0

POINT_FIELDS = ("id", "name", "address", "category_short", "lat", "lon", "precision", "approximate",
                "elec_kwh_2025", "elec_kwh_m2", "solar_potential_kw", "solar_payback_years",
                "defects_count", "data_ok")

NOTE = ("Публічна карта: категорія будівлі, споживання електроенергії за 2025 рік, ПОТЕНЦІАЛ нової СЕС "
        "(рекомендація для покрівлі, а не наявна станція) і якість даних. За правилом треку тут свідомо НЕМАЄ "
        "інформації про наявні СЕС, акумулятори, генератори, автономність чи резервне живлення закладів. "
        "Координати: з UMUNI, а якщо їх немає — геокодування адреси (OpenStreetMap Nominatim). Точність "
        "«вулиця» — точка на вулиці без номера будинку; «населений пункт» — центр села/міста зі зсувом до "
        "150 м (approximate=true), щоб точки не накладались. data_ok=false — у даних є дефекти, крім "
        "відсутніх координат.")

_store = None


def set_store(store) -> None:
    global _store
    _store = store


def _get_store():
    if _store is not None:
        return _store
    from .main import store  # лінивий імпорт, щоб не було циклу з main.py

    return store


def hidden_on_map(b) -> bool:
    """Котельні не публікуються на мапах (ТЗ): у таблицях лишаються, координат не віддаємо."""
    return "котельн" in (getattr(b, "name", "") or "").lower()


def jitter(bid: int, lat: float, lon: float) -> tuple[float, float]:
    """Детермінований зсув 40–150 м за id (той самий при кожному запиті)."""
    h = hashlib.sha256(str(bid).encode()).digest()
    angle = int.from_bytes(h[:2], "big") / 65535 * 2 * math.pi
    r = JITTER_MIN_M + h[2] / 255 * (JITTER_MAX_M - JITTER_MIN_M)
    dlat = r * math.cos(angle) / M_PER_DEG_LAT
    dlon = r * math.sin(angle) / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lon + dlon, 6)


def _is_coord_gap(d: dict) -> bool:
    return d.get("поле") == "координати" and str(d.get("правило", "")).startswith("Координати відсутні")


def _solar(b) -> tuple[float | None, float | None]:
    """Рекомендована потужність НОВОЇ СЕС і окупність (тариф/вартість — типові з solar.py)."""
    if _exclusion(b):
        return None, None
    r = solar.estimate(b.years[BASE_YEAR].elec_kwh, b.heated_area, b.floors, b.category_short)
    if r.kw_recommended < solar.MIN_KW:
        return None, None
    return round(r.kw_recommended, 1), (round(r.payback_years, 1) if r.payback_years is not None else None)


def point(b) -> dict:
    yd = b.years.get(BASE_YEAR)
    lat, lon, approx = b.lat, b.lon, False
    if b.geo_precision == "населений пункт":
        lat, lon = jitter(b.id, lat, lon)
        approx = True
    kw, payback = _solar(b)
    return {
        "id": b.id, "name": b.name, "address": b.address, "category_short": b.category_short,
        "lat": lat, "lon": lon, "precision": b.geo_precision, "approximate": approx,
        "elec_kwh_2025": round(yd.elec_kwh) if yd and yd.elec_kwh is not None else None,
        "elec_kwh_m2": round(yd.elec_kwh_m2, 1) if yd and yd.elec_kwh_m2 is not None else None,
        "solar_potential_kw": kw, "solar_payback_years": payback,
        "defects_count": len(b.defects),
        "data_ok": not any(not _is_coord_gap(d) for d in b.defects),
    }


def build_map(store) -> dict:
    points, missing = [], []
    by_precision = {p: 0 for p in PRECISIONS}
    for b in store.buildings:
        prec = b.geo_precision if b.lat is not None else "немає"
        by_precision[prec] = by_precision.get(prec, 0) + 1
        if b.lat is None or b.lon is None or hidden_on_map(b):
            missing.append({"id": b.id, "name": b.name, "address": b.address, "category_short": b.category_short})
            continue
        points.append(point(b))
    bounds = None
    if points:
        lats, lons = [p["lat"] for p in points], [p["lon"] for p in points]
        bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
    return {"points": points, "bounds": bounds,
            "counts": {"total": len(store.buildings), "on_map": len(points), "by_precision": by_precision},
            "not_on_map": missing, "note": NOTE}


@router.get("/api/map")
def map_points():
    return build_map(_get_store())
