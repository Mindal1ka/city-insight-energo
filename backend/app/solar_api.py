"""API екрана 4 «Де ставити нові СЕС»: /api/solar, /api/solar/{id}.

Підключення в main.py (ДО маршруту SPA «/{path:path}»): app.include_router(router)
Store береться через set_store() або ліниво з app.main (щоб не було циклічного імпорту).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from . import solar
from .analytics import ELEC_KWH_M2_MAX, MIN_AREA_M2

router = APIRouter(prefix="/api/solar", tags=["СЕС"])

BASE_YEAR = 2025  # рік фактичного споживання електроенергії для оцінки
_store = None


def set_store(store) -> None:
    global _store
    _store = store


def _get_store():
    if _store is not None:
        return _store
    from .main import store  # лінивий імпорт усередині обробника

    return store


def _exclusion(b) -> str | None:
    """Причина, чому будівлю не оцінюємо (не відкидаємо мовчки)."""
    if b.heated_area is None or b.heated_area <= MIN_AREA_M2:
        return "Немає коректної опалюваної площі — не можна оцінити площу даху"
    yd = b.years.get(BASE_YEAR)
    if not yd or not yd.elec_kwh or yd.elec_kwh <= 0:
        return f"Немає даних про споживання електроенергії за {BASE_YEAR} рік"
    if yd.elec_kwh / b.heated_area > ELEC_KWH_M2_MAX:
        return (f"Ймовірна помилка даних: питоме споживання електроенергії "
                f"{yd.elec_kwh / b.heated_area:.0f} кВт·год/м² > {ELEC_KWH_M2_MAX:.0f}")
    return None


def _compute(tariff: float, capex: float, fixed: float):
    """Усі будівлі: (items з рангом, excluded, results за id)."""
    items, excluded, results = [], [], {}
    for b in _get_store().buildings:
        reason = _exclusion(b)
        r = None
        if not reason:
            r = solar.estimate(b.years[BASE_YEAR].elec_kwh, b.heated_area, b.floors, b.category_short,
                               tariff=tariff, capex_per_kw=capex, capex_fixed=fixed)
            if r.kw_recommended < solar.MIN_KW:
                reason = (f"Замале денне споживання: станція під власне споживання менша за "
                          f"{solar.MIN_KW:g} кВт ({r.kw_recommended:.1f} кВт)")
        if reason:
            excluded.append({"id": b.id, "name": b.name, "category_short": b.category_short, "reason": reason})
            continue
        results[b.id] = (b, r)
        items.append(solar.item_dict(b.id, b.name, b.category_short, r))
    # рейтинг серед УСІХ будівель: коротша окупність вище; за однакової — більша річна економія
    items.sort(key=lambda it: (it["payback_years"] if it["payback_years"] is not None else 1e9,
                               -it["savings_uah_year"]))
    for i, it in enumerate(items, 1):
        it["rank"] = i
    return items, excluded, results


def _params(tariff: float, capex: float, fixed: float) -> dict:
    return {"tariff_uah_kwh": tariff, "capex_uah_per_kw": capex, "capex_fixed_uah": fixed,
            "kwp_per_m2_roof": round(solar.KWP_PER_M2_ROOF, 4),
            "roof_usable_share": solar.ROOF_USABLE_SHARE, "m2_per_kwp": solar.M2_PER_KWP,
            "daytime_share": solar.DAYTIME_SHARE, "max_self_share": solar.MAX_SELF_SHARE,
            "base_year": BASE_YEAR, "source_notes": solar.source_notes()}


def _check(tariff: float | None, capex: float | None, fixed: float | None) -> tuple[float, float, float]:
    t = solar.TARIFF_UAH_KWH if tariff is None else tariff
    c = solar.CAPEX_UAH_PER_KW if capex is None else capex
    f = solar.CAPEX_FIXED_UAH if fixed is None else fixed
    if t <= 0 or c <= 0 or f < 0:
        raise HTTPException(400, "Тариф і вартість монтажу мають бути додатними")
    return t, c, f


@router.get("")
def solar_list(category: str | None = None, tariff: float | None = Query(None), capex: float | None = Query(None),
               fixed: float | None = Query(None)):
    t, c, f = _check(tariff, capex, fixed)
    items, excluded, _ = _compute(t, c, f)
    if category:
        items = [it for it in items if it["category_short"] == category]
        excluded = [e for e in excluded if e["category_short"] == category]
    return {"params": _params(t, c, f), "items": items, "excluded": excluded}


@router.get("/{bid}")
def solar_one(bid: int, tariff: float | None = Query(None), capex: float | None = Query(None),
              fixed: float | None = Query(None)):
    t, c, f = _check(tariff, capex, fixed)
    items, excluded, results = _compute(t, c, f)
    if bid not in results:
        ex = next((e for e in excluded if e["id"] == bid), None)
        if ex:
            raise HTTPException(404, f"Будівлю не оцінено: {ex['reason']}")
        raise HTTPException(404, "Будівлю не знайдено")
    b, r = results[bid]
    item = next(it for it in items if it["id"] == bid)
    return {"item": item, "monthly": solar.monthly_rows(r),
            "assumptions": solar.assumptions_for(r, b.floors, t, c, f)}
