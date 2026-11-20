"""API енергонезалежності: /api/independence, /api/independence/{id}, /api/sites/{id}/outage (ДЕМО-дані станцій)."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from . import independence as ind
from .auth import User, can_see_sensitive, can_see_ses, current_user, require_login
from .sites import KYIV

router = APIRouter(tags=["Енергонезалежність"])


def _ctx():
    from .main import sites, store  # лінивий імпорт, щоб не було циклу з main.py

    return store, sites


def _moment(day: str | None, hour: int | None) -> datetime:
    """?day=YYYY-MM-DD&hour=H, як у /api/sites; за замовчуванням — зараз (Київ)."""
    now = datetime.now(KYIV)
    try:
        d = date.fromisoformat(day) if day else now.date()
    except ValueError:
        raise HTTPException(400, "Невірна дата (формат РРРР-ММ-ДД)")
    h = now.hour if hour is None else max(0, min(23, int(hour)))
    return datetime(d.year, d.month, d.day, h, 0, tzinfo=KYIV)


def _stations(store, sites) -> dict[int, dict]:
    """Реєстр СЕС (sites.py) + ДЕМО-акумулятори без СЕС."""
    reg = dict(sites.registry)
    reg.update(ind.battery_only_registry(store.buildings, sites.registry))
    return reg


def _find(store, bid: int):
    for b in store.buildings:
        if b.id == bid:
            return b
    raise HTTPException(404, "Об'єкт не знайдено")


# поля, яких не бачить finance (акумулятори й автономність)
_SENSITIVE_FIELDS = ("battery_kwh", "battery_kw", "has_battery", "autonomy_hours", "autonomy_hours_with_sun",
                     "autonomy_with_sun_capped", "index", "index_class")
# ключі зведень громади/категорій про акумулятори й автономність (не для finance)
_SENSITIVE_AGG = ("battery_sites", "battery_kwh_total", "autonomy_hours_median", "critical_with_battery",
                  "with_battery")


def _strip_agg(user: User, d: dict) -> dict:
    if user.role != "finance":
        return d
    return {**d, **{k: None for k in _SENSITIVE_AGG if k in d}}


def _visible_items(user: User, evs: list[dict]) -> list[dict]:
    """Об'єкти, дозволені ролі: повні — за can_see_sensitive, без акумуляторів/автономності — для finance."""
    out = []
    for e in evs:
        item = ind.public(e)
        if can_see_sensitive(user, item["category_short"], item["id"]):
            out.append(item)
        elif can_see_ses(user, item["category_short"], item["id"]):
            out.append({**item, **{k: None for k in _SENSITIVE_FIELDS}})
    return out


def _guard(user: User, b) -> None:
    if not can_see_sensitive(user, b.category_short, b.id):
        raise HTTPException(403, "Немає доступу до даних цього об'єкта")


def _sort_key(e: dict):
    # спершу критичні й заклади освіти, усередині — найменш захищені
    return (e["priority_rank"], e["index"], e["name"])


@router.get("/api/independence")
def independence_list(day: str | None = None, hour: int | None = None, user: User = Depends(current_user)):
    # Публічний режим: лише зведені цифри громади й категорій (без жодного об'єкта) —
    # щоб відсоток енергонезалежності збігався на всіх сторінках; items для public порожній.
    store, sites = _ctx()
    now = _moment(day, hour)
    reg = _stations(store, sites)
    evs = [ind.evaluate(b, reg.get(b.id), now) for b in store.buildings]
    evs.sort(key=_sort_key)
    return {"demo": True, "now": now.isoformat(timespec="minutes"),
            "community": _strip_agg(user, ind.community(evs)),
            "categories": [_strip_agg(user, c) for c in ind.categories(evs)],
            "items": _visible_items(user, evs), "formula": ind.formula(), "notes": ind.NOTES}


@router.get("/api/independence/{bid}")
def independence_item(bid: int, day: str | None = None, hour: int | None = None,
                      user: User = Depends(require_login)):
    store, sites = _ctx()
    now = _moment(day, hour)
    b = _find(store, bid)
    _guard(user, b)
    ev = ind.evaluate(b, _stations(store, sites).get(b.id), now)
    return {"demo": True, "now": now.isoformat(timespec="minutes"), "item": ind.public(ev),
            "explain": ind.explain(ev, now), "improve": ind.improve(ev), "formula": ind.formula(),
            "notes": ind.NOTES}


@router.get("/api/sites/{bid}/outage")
def outage(bid: int, day: str | None = None, start_hour: int | None = None,
           hours: int = Query(4, ge=1, le=72), soc: float | None = Query(None, ge=0, le=100), user: User = Depends(require_login)):
    store, sites = _ctx()
    now = _moment(day, start_hour)
    b = _find(store, bid)
    _guard(user, b)
    return ind.simulate_outage(b, _stations(store, sites).get(b.id), now.date(), now.hour, hours, soc)

