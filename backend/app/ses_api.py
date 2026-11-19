"""API ефективності СЕС: GET /api/ses, GET /api/ses/{id}, PUT /api/ses/{id} (контракт — docs/PLAN_v3.md).

Доступ (перевіряється тут, на бекенді; правила — app/auth.py):
- повні дані об'єкта (акумулятори тощо) — can_see_sensitive (energy_manager, data_admin, своє управління, свій заклад);
- finance — СЕС, K, фінанси всіх об'єктів, але без акумуляторів (can_see_ses / can_see_finance);
- public та «чужі» об'єкти — без наявності СЕС, K і фінансів по конкретному об'єкту (null); зведені цифри лишаються.
"""

from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import efficiency as eff
from . import sites as sites_mod
from .auth import User, can_edit_ses, can_see_finance, can_see_sensitive, can_see_ses, current_user
from .sites import KYIV, city_of

router = APIRouter(tags=["Ефективність СЕС"])

FULL, SES, PUBLIC = "full", "ses", "public"
BATTERY_FIELDS = ("battery_count", "battery_module_kwh", "battery_kwh", "battery_kw")

_cache: dict[tuple, list[tuple]] = {}
_cache_lock = threading.Lock()
CACHE_MAX = 64


def _ctx():
    from .main import sites, store  # лінивий імпорт, щоб не було циклу з main.py

    return store, sites


def invalidate() -> None:
    with _cache_lock:
        _cache.clear()


def _day(day: str | None) -> date:
    if not day:
        return datetime.now(KYIV).date()
    try:
        return date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Невірна дата (формат РРРР-ММ-ДД)")


def _find(store, bid: int):
    for b in store.buildings:
        if b.id == bid:
            return b
    raise HTTPException(404, "Об'єкт не знайдено")


def _evaluations(store, sites, d: date, tariff: float, surplus_price: float) -> list[tuple]:
    """[(будівля, запис реєстру, оцінка)] для всіх об'єктів; кеш за (день, тариф, ціна надлишку)."""
    key = (d, tariff, surplus_price, id(sites.registry), len(store.buildings))
    with _cache_lock:
        hit = _cache.get(key)
    if hit is not None:
        return hit
    reg = sites.registry
    res = [(b, reg.get(b.id), eff.evaluate(b, reg.get(b.id), d, tariff, surplus_price)) for b in store.buildings]
    with _cache_lock:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[key] = res
    return res


def _dept(b) -> str:
    from .insight import department_of  # лінивий імпорт (insight імпортує цей модуль)

    return department_of(b)


def _eidx(store) -> dict:
    from .insight import efficiency_index

    return efficiency_index(store)


def access_level(user: User, b) -> str:
    if can_see_sensitive(user, b.category_short, b.id):
        return FULL
    if can_see_ses(user, b.category_short, b.id):
        return SES
    return PUBLIC


def _coords(b) -> tuple[float | None, float | None, bool]:
    if b.lat is None or b.lon is None:
        return None, None, False
    if b.geo_precision == "населений пункт":
        from .map_api import jitter  # той самий детермінований зсув, що й на публічній карті

        lat, lon = jitter(b.id, b.lat, b.lon)
        return lat, lon, True
    return b.lat, b.lon, False


# ---------------- GET /api/ses ----------------

@router.get("/api/ses")
def ses_list(period: Literal["day", "month", "year"] = "year", day: str | None = None,
             tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
             surplus_price: float = Query(eff.SURPLUS_PRICE_UAH_KWH, ge=0, le=100),
             user: User = Depends(current_user)):
    store, sites = _ctx()
    d = _day(day)
    evs = _evaluations(store, sites, d, tariff, surplus_price)

    cnt = {c: 0 for c in eff.CLASSES}
    gen_t = cons_ses = cons_all = capex = saved = grid_cost = 0.0
    # помісячно по громаді: генерація станцій, споживання об'єктів зі СЕС і всіх об'єктів (агрегат — публічний)
    mon = [{"month": m + 1, "gen_kwh": 0.0, "cons_kwh": 0.0, "cons_kwh_all": 0.0} for m in range(12)]
    items = []
    for b, ses, ev in evs:
        en, cls = ev["energy"][period], ev["k_class"][period]
        cnt[cls] += 1
        cons_all += en["cons_kwh"]
        grid_cost += ev["finance"]["grid_cost_uah"]["year"]
        if ev["has_ses"]:
            gen_t += en["gen_kwh"]
            if ev["has_data"]:
                cons_ses += en["cons_kwh"]
            capex += ev["finance"]["invested_uah"] or 0
            saved += ev["finance"]["saved_uah"]["year"]
        for m, row in enumerate(ev["monthly"][:12]):
            mon[m]["cons_kwh_all"] += row.get("cons_kwh") or 0
            if ev["has_ses"] and ev["has_data"]:
                mon[m]["gen_kwh"] += row.get("gen_kwh") or 0
                mon[m]["cons_kwh"] += row.get("cons_kwh") or 0
        lvl = access_level(user, b)
        lat, lon, approx = _coords(b)
        it = {"id": b.id, "name": b.name, "address": b.address, "category_short": b.category_short,
              "lat": lat, "lon": lon, "precision": b.geo_precision, "approximate": approx,
              "has_ses": ev["has_ses"], "k": eff.r2(ev["k"][period]), "k_class": cls,
              "gen_kwh": eff.r1(en["gen_kwh"]) if ev["has_ses"] else None,
              "cons_kwh": eff.r1(en["cons_kwh"]) if ev["has_data"] else None,
              "ses_kw": ses["total_kw"] if ev["has_ses"] else None,
              "battery_kwh": (ses.get("battery_kwh") or None) if ses else None,
              "capex_uah": eff.r0(ev["finance"]["invested_uah"]),
              "saved_uah_year": eff.r0(ev["finance"]["saved_uah"]["year"]) if ev["has_ses"] else None,
              "payback_years": eff.r1(ev["finance"]["payback_years"]),
              "grid_cost_uah_year": eff.r0(ev["finance"]["grid_cost_uah"]["year"]) if ev["has_data"] else None,
              "access": lvl, "department": _dept(b),
              "cons_kwh_month_avg": round(ev["energy"]["year"]["cons_kwh"] / 12) if ev["has_data"] else None,
              "eff_index": _eidx(store).get(b.id)}
        if lvl == PUBLIC:
            for k in ("has_ses", "k", "k_class", "gen_kwh", "ses_kw", "battery_kwh", "capex_uah",
                      "saved_uah_year", "payback_years", "grid_cost_uah_year"):
                it[k] = None
        elif lvl == SES:
            it["battery_kwh"] = None
        if lvl != PUBLIC and not can_see_finance(user, b.category_short, b.id):
            it["capex_uah"] = it["saved_uah_year"] = it["payback_years"] = it["grid_cost_uah_year"] = None
        items.append(it)

    totals = {"objects": len(items), "with_ses": sum(1 for _, _, e in evs if e["has_ses"]),
              "effective": cnt[eff.C_OK], "deficit": cnt[eff.C_LOW], "surplus": cnt[eff.C_HIGH],
              "no_ses": cnt[eff.C_NONE], "no_data": cnt[eff.C_NODATA],
              "gen_kwh": round(gen_t), "cons_kwh": round(cons_ses),
              "k": eff.r2(gen_t / cons_ses) if cons_ses else None,
              "cons_kwh_all": round(cons_all), "k_all": eff.r2(gen_t / cons_all) if cons_all else None,
              "capex_uah": round(capex), "saved_uah_year": round(saved), "grid_cost_uah_year": round(grid_cost)}
    return {"demo": True, "period": period, "day": d.isoformat(),
            "thresholds": {"low": eff.LOW, "high": eff.HIGH}, "tariff_uah_kwh": tariff,
            "totals": totals, "items": items,
            "monthly": [{"month": r["month"], "gen_kwh": round(r["gen_kwh"]), "cons_kwh": round(r["cons_kwh"]),
                         "cons_kwh_all": round(r["cons_kwh_all"]),
                         "k": eff.r2(r["gen_kwh"] / r["cons_kwh"]) if r["cons_kwh"] else None} for r in mon],
            "notes": eff.NOTES}


# ---------------- GET /api/ses/{id} ----------------

def _detail(store, sites, b, user: User, d: date, tariff: float, surplus_price: float) -> dict:
    ses = sites.registry.get(b.id)
    ev = eff.evaluate(b, ses, d, tariff, surplus_price)
    lvl = access_level(user, b)
    has = ev["has_ses"]
    lat, lon, approx = _coords(b)
    y25 = b.years.get(2025)
    building = {"id": b.id, "name": b.name, "address": b.address, "city": city_of(b.address),
                "category_short": b.category_short, "heated_area": b.heated_area, "floors": b.floors,
                "elec_kwh_2025": round(y25.elec_kwh) if y25 and y25.elec_kwh else None,
                "lat": lat, "lon": lon, "precision": b.geo_precision, "approximate": approx}

    ses_out = None
    if sites_mod.is_station(ses):
        ses_out = {k: ses.get(k) for k in sites_mod.SES_FIELDS}
        ses_out["source"] = ses.get("source") or "ДЕМО"
    costs = (ses or {}).get("costs") if ses else None
    en = {"day": eff.energy_out(ev["energy"]["day"], 1), "month": eff.energy_out(ev["energy"]["month"], 0),
          "year": eff.energy_out(ev["energy"]["year"], 0)}
    out = {"demo": True, "day": d.isoformat(), "building": building, "access": lvl, "has_ses": has,
           "ses": ses_out, "costs": dict(costs) if costs else None,
           "k": {p: eff.r2(v) for p, v in ev["k"].items()}, "k_class": dict(ev["k_class"]),
           "thresholds": {"low": eff.LOW, "high": eff.HIGH},
           "energy": en, "finance": eff.finance_out(ev["finance"]) if has else None,
           "monthly": eff.monthly_out(ev["monthly"], has),
           "meters": store.meters_for(b.id) if hasattr(store, "meters_for") else None,
           "sem": store.sem_for(b.id) if hasattr(store, "sem_for") else None,
           "can_edit": can_edit_ses(user, b.id), "notes": eff.NOTES}

    if lvl == SES and out["ses"]:
        for k in BATTERY_FIELDS:
            out["ses"][k] = None
    if lvl == PUBLIC:
        out.update(has_ses=None, ses=None, costs=None, finance=None,
                   k={p: None for p in out["k"]}, k_class={p: None for p in out["k_class"]})
        for p in en:
            en[p] = {k: (v if k == "cons_kwh" else None) for k, v in en[p].items()}
        out["monthly"] = [{**m, **{k: None for k in m if k not in ("month", "cons_kwh")}} for m in out["monthly"]]
    elif not can_see_finance(user, b.category_short, b.id):
        out.update(costs=None, finance=None)
    return out


@router.get("/api/ses/{bid}")
def ses_item(bid: int, day: str | None = None,
             tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
             surplus_price: float = Query(eff.SURPLUS_PRICE_UAH_KWH, ge=0, le=100),
             user: User = Depends(current_user)):
    store, sites = _ctx()
    b = _find(store, bid)
    return _detail(store, sites, b, user, _day(day), tariff, surplus_price)


# ---------------- PUT /api/ses/{id} ----------------

class SesIn(BaseModel):
    """Дані СЕС і вартість. Порожнє поле (null / "") = «немає даних». Запис замінюється повністю."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    panels_count: int | None = Field(None, ge=0, le=100_000)
    panel_w: float | None = Field(None, ge=100, le=800)
    total_kw: float | None = Field(None, ge=0, le=20_000)  # якщо не задано к-сть і потужність панелей
    inverter_model: str | None = Field(None, max_length=120)
    inverter_kw: float | None = Field(None, ge=0, le=20_000)
    battery_count: int | None = Field(None, ge=0, le=1000)
    battery_module_kwh: float | None = Field(None, gt=0, le=1000)
    battery_kwh: float | None = Field(None, ge=0, le=100_000)
    battery_kw: float | None = Field(None, ge=0, le=20_000)
    connected_kw: float | None = Field(None, ge=0, le=100_000)
    launched: date | None = None
    panels_uah: float | None = Field(None, ge=0, le=1e10)
    inverter_uah: float | None = Field(None, ge=0, le=1e10)
    batteries_uah: float | None = Field(None, ge=0, le=1e10)
    install_uah: float | None = Field(None, ge=0, le=1e10)

    @field_validator("*", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        return None if isinstance(v, str) and v.strip() == "" else v

    @field_validator("launched")
    @classmethod
    def _launched_range(cls, v):
        if v is not None and not (date(2000, 1, 1) <= v <= datetime.now(KYIV).date()):
            raise ValueError("Дата запуску — від 2000-01-01 до сьогодні")
        return v


@router.put("/api/ses/{bid}")
def ses_update(bid: int, body: dict = Body(...), user: User = Depends(current_user)):
    store, sites = _ctx()
    b = _find(store, bid)
    if user.role == "public":
        raise HTTPException(401, "Потрібен вхід")
    if not can_edit_ses(user, b.id):
        raise HTTPException(403, "Редагувати дані СЕС цього об'єкта можуть лише енергоменеджер або керівник закладу")
    # приймаємо і плоский формат, і {ses:{...}, costs:{...}}
    flat = {k: v for k, v in body.items() if k not in ("ses", "costs")}
    for part in ("ses", "costs"):
        if isinstance(body.get(part), dict):
            flat.update(body[part])
    try:
        data = SesIn.model_validate(flat).model_dump()
    except ValidationError as e:
        raise RequestValidationError(e.errors(include_url=False, include_context=False))
    if data["launched"] is not None:
        data["launched"] = data["launched"].isoformat()
    sites_mod.save_entry(b.id, data)
    sites.reload()
    invalidate()
    return _detail(store, sites, b, user, datetime.now(KYIV).date(), eff.TARIFF_UAH_KWH,
                   eff.SURPLUS_PRICE_UAH_KWH)
