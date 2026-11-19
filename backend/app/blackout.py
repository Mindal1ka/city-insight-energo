"""Генератори і повний блекаут (лише для ролей з повним доступом до об'єкта).

МОК: у пакеті даних генераторів немає. Детерміновано ~35 % лікарень, ~20 % шкіл/садків, ~10 % решти;
справжні значення вводяться формою (data/generators.csv).
Гібридний інвертор має вхід генератора: при повному блекауті генератор живить навантаження
і заряджає акумулятор надлишком своєї потужності; сонце вдень теж заряджає акумулятор.
Публічні /api/map і /api/solar цих даних не містять (автотести).
"""

from __future__ import annotations

import csv
import os
import random
import tempfile
from datetime import date, datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from . import efficiency as eff
from .auth import User, can_edit_ses, can_see_sensitive, current_user
from .insight import DATA, MOCK, _lock, _now, _r, department_of
from .ses_api import _ctx, _find
from .sites import BATTERY_RESERVE, simulate_day

router = APIRouter(tags=["v2: генератори, блекаут"])

GEN_FILE = DATA / "generators.csv"
FUEL_L_PER_KWH = 0.30  # дизель-генератор 100 кВА при 75 % навантаження: 0,21–0,33 л/кВт·год
FUEL_PRICE_UAH_L = 101.0  # дизель, грн/л — середня по Україні 17.11.2026 (А-95)
HORIZON_H = 48
BLACKOUT_FLOOR = 0.05  # при блекауті резерв акумулятора (BATTERY_RESERVE) якраз і витрачається — до 5 %
GEN_SIZES = (5, 8, 10, 15, 20, 30, 45, 60, 80, 100, 150, 200)
GEN_SHARE = {"Охорона здоров'я": 0.35, "Заклади освіти": 0.2, "Дошкільні заклади": 0.2}


def read_generators() -> dict[int, dict]:
    if not GEN_FILE.exists():
        return {}
    out = {}
    with GEN_FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[int(r["building_id"])] = {"generator_kw": float(r["generator_kw"] or 0),
                                              "fuel": r.get("fuel") or "дизель",
                                              "tank_l": float(r["tank_l"] or 0), "source": "введено"}
            except (KeyError, ValueError):
                continue
    return out


def generator_of(b, overrides: dict[int, dict]) -> dict | None:
    if b.id in overrides:
        g = overrides[b.id]
        return g if g["generator_kw"] > 0 else None
    rng = random.Random(f"gen-unit-{b.id}")
    if rng.random() >= GEN_SHARE.get(b.category_short, 0.1) or not eff.elec_2025(b):
        return None
    peak = eff.elec_2025(b) / 365 / 10  # ≈ середнє навантаження робочого дня, кВт
    kw = next((s for s in GEN_SIZES if s >= peak * 1.3), GEN_SIZES[-1])
    return {"generator_kw": float(kw), "fuel": "дизель", "tank_l": float(rng.choice((50, 100, 200, 400))),
            "source": MOCK}


def blackout(b, ses: dict | None, gen: dict | None, now: datetime | None = None) -> dict:
    """Повний блекаут від поточної години: скільки годин (до 48) протримається об'єкт."""
    now = now or _now()
    st = ses if eff.has_station(ses) else None
    bat_only = (ses or {}).get("battery_kwh") or 0.0 if not st else 0.0  # акумулятор без панелей (резерв)
    today = now.date()
    rows = simulate_day(b, st, today) + simulate_day(b, st, date.fromordinal(today.toordinal() + 1))
    h0 = now.hour
    cap = (st or {}).get("battery_kwh") or bat_only
    if st:
        soc = (rows[h0 - 1]["soc_kwh"] if h0 else cap * 0.6) if cap else 0.0
    else:
        soc = cap * 0.9  # резервний акумулятор тримають зарядженим від мережі
    room = cap * (1 - BLACKOUT_FLOOR)  # ємність, доступна при блекауті
    load_avg = sum(r["cons_kwh"] for r in rows[:24]) / 24

    def run(with_sun: bool, with_gen: bool) -> tuple[float, float]:
        e = max(0.0, soc - BLACKOUT_FLOOR * cap)
        fuel = gen["tank_l"] if with_gen and gen else 0.0
        used = 0.0
        for i, r in enumerate(rows[h0:h0 + HORIZON_H]):
            need = r["cons_kwh"] - (r["gen_kwh"] if with_sun else 0.0)
            if need <= 0:
                e = min(room, e - need)  # сонце заряджає акумулятор
                continue
            if e >= need:
                e -= need
                continue
            full = need
            need -= e
            covered = e
            e = 0.0
            if with_gen and fuel > 0:
                out = min(gen["generator_kw"], need + room)  # навантаження + дозаряд акумулятора
                lit = out * FUEL_L_PER_KWH
                if lit > fuel:
                    out, lit = fuel / FUEL_L_PER_KWH, fuel
                fuel -= lit
                used += lit
                if out >= need:
                    e = min(room, out - need)
                    continue
                covered += out
            return i + covered / full, used  # частина години, яку ще покрили
        return float(HORIZON_H), used

    bat_h, _ = run(False, False)
    sun_h, _ = run(True, False)
    gen_h, fuel_used = run(True, True) if gen else (None, 0.0)
    charge_h = None
    if gen and cap:
        charge_kw = min(gen["generator_kw"] - load_avg, (st or {}).get("battery_kw") or cap * 0.5)
        charge_h = room / charge_kw if charge_kw > 0 else None
    return {"load_kw_avg": load_avg, "battery_kwh_now": soc if cap else None, "battery_capacity_kwh": cap or None,
            "hours_battery": bat_h, "hours_battery_sun": sun_h, "hours_with_generator": gen_h,
            "horizon_h": HORIZON_H, "generator": gen, "generator_charges_battery": bool(gen and cap),
            "generator_full_charge_h": charge_h,
            "generator_cost_uah_kwh": FUEL_L_PER_KWH * FUEL_PRICE_UAH_L if gen else None,
            "fuel_l_per_day": load_avg * 24 * FUEL_L_PER_KWH if gen else None,
            "fuel_used_l": fuel_used if gen else None,
            "assumptions": {"fuel_l_per_kwh": FUEL_L_PER_KWH, "fuel_price_uah_l": FUEL_PRICE_UAH_L,
                            "battery_floor": BLACKOUT_FLOOR, "daily_reserve": BATTERY_RESERVE}}


def _round(d: dict) -> dict:
    return {k: (_r(v, 1) if isinstance(v, float) else v) for k, v in d.items()}


@router.get("/api/blackout/{bid}")
def blackout_item(bid: int, user: User = Depends(current_user)):
    store, sites = _ctx()
    b = _find(store, bid)
    if not can_see_sensitive(user, b.category_short, b.id):
        raise HTTPException(403, "Дані резервного живлення — лише для служб з повним доступом")
    bo = blackout(b, sites.registry.get(b.id), generator_of(b, read_generators()))
    return {"id": b.id, "source": MOCK, **_round(bo)}


@router.get("/api/blackout")
def blackout_all(user: User = Depends(current_user)):
    """Зведення по громаді: скільки об'єктів протримається при повному блекауті."""
    if user.role not in ("energy_manager", "data_admin"):
        raise HTTPException(403, "Лише енергоменеджер / адміністратор даних")
    store, sites = _ctx()
    gens = read_generators()
    now = _now()
    items = []
    for b in store.buildings:
        ses = sites.registry.get(b.id)
        g = generator_of(b, gens)
        if (not eff.has_station(ses) and not (ses or {}).get("battery_kwh") and not g) or not eff.elec_2025(b):
            continue
        bo = blackout(b, ses, g, now)
        items.append({"id": b.id, "name": b.name, "department": department_of(b),
                      "has_ses": eff.has_station(ses), "battery_kwh": bo["battery_capacity_kwh"],
                      "source": (ses or {}).get("source"),
                      "generator_kw": g["generator_kw"] if g else None,
                      "generator_source": g["source"] if g else None,
                      "hours_battery_sun": _r(bo["hours_battery_sun"], 1),
                      "hours_with_generator": _r(bo["hours_with_generator"], 1),
                      "load_kw_avg": _r(bo["load_kw_avg"], 1)})
    best = lambda i: i["hours_with_generator"] if i["hours_with_generator"] is not None else i["hours_battery_sun"]
    items.sort(key=best)
    return {"source": MOCK, "updated_at": now.isoformat(timespec="seconds"), "horizon_h": HORIZON_H,
            "totals": {"objects": len(items), "with_generator": sum(1 for i in items if i["generator_kw"]),
                       "with_battery": sum(1 for i in items if i["battery_kwh"]),
                       "hold_24h": sum(1 for i in items if best(i) >= 24),
                       "under_4h": sum(1 for i in items if best(i) < 4)},
            "items": items}


@router.put("/api/generator/{bid}")
def generator_update(bid: int, body: dict = Body(...), user: User = Depends(current_user)):
    store, _ = _ctx()
    b = _find(store, bid)
    if not can_edit_ses(user, b.id):
        raise HTTPException(403, "Немає прав редагувати дані об'єкта")
    try:
        kw = float(body.get("generator_kw") or 0)
        tank = float(body.get("tank_l") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "generator_kw і tank_l — числа")
    if not (0 <= kw <= 5000 and 0 <= tank <= 100000):
        raise HTTPException(422, "Значення поза межами")
    fuel = str(body.get("fuel") or "дизель")[:20]
    with _lock:
        gens = read_generators()
        gens[b.id] = {"generator_kw": kw, "fuel": fuel, "tank_l": tank, "source": "введено"}
        DATA.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".generators.", suffix=".tmp", dir=DATA)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["building_id", "generator_kw", "fuel", "tank_l"])
            for k in sorted(gens):
                w.writerow([k, gens[k]["generator_kw"], gens[k]["fuel"], gens[k]["tank_l"]])
        os.replace(tmp, GEN_FILE)
    return blackout_item(bid, user)
