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
# Облік витрат на генератори (ПРИПУЩЕННЯ для МОК; справжні значення — з картки об'єкта)
# Ціна дизель-генератора з АВР, листопад 2026: малі ~18 тис. грн/кВт, 15–45 кВт ~13 тис., понад 45 кВт ~9,5 тис.
GEN_UAH_PER_KW = ((10, 18000.0), (45, 13000.0), (10**9, 9500.0))
GEN_INSTALL_SHARE = 0.15  # монтаж, АВР, кабелі
GEN_HOURS_YEAR = 150  # мотогодин на рік за графіків відключень 2025–2026 (оцінка)
GEN_LOAD = 0.6  # середнє навантаження генератора під час роботи
FUEL_FILE_NAME = "fuel_log.csv"
GEN_SHARE = {"Охорона здоров'я": 0.35, "Заклади освіти": 0.2, "Дошкільні заклади": 0.2}


def read_generators() -> dict[int, dict]:
    if not GEN_FILE.exists():
        return {}
    out = {}
    with GEN_FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                cost = (r.get("cost_uah") or "").strip()
                out[int(r["building_id"])] = {"generator_kw": float(r["generator_kw"] or 0),
                                              "fuel": r.get("fuel") or "дизель",
                                              "tank_l": float(r["tank_l"] or 0), "source": "введено",
                                              "cost_uah": float(cost) if cost else None,
                                              "bought": (r.get("bought") or "").strip() or None,
                                              "doc": (r.get("doc") or "").strip() or None}
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
            "source": MOCK, "cost_uah": None, "bought": None, "doc": None}


def gen_capex_estimate(kw: float) -> float:
    per_kw = next(p for lim, p in GEN_UAH_PER_KW if kw <= lim)
    return round(kw * per_kw * (1 + GEN_INSTALL_SHARE), -3)


def gen_fuel_estimate_year(kw: float) -> tuple[float, float]:
    """Пальне за рік (оцінка): мотогодини × потужність × навантаження × витрата. → (л, грн)"""
    lit = kw * GEN_LOAD * GEN_HOURS_YEAR * FUEL_L_PER_KWH
    return round(lit), round(lit * FUEL_PRICE_UAH_L, -2)


# ---------------- журнал пального ----------------

def _fuel_file():
    return DATA / FUEL_FILE_NAME


def read_fuel() -> list[dict]:
    f = _fuel_file()
    if not f.exists():
        return []
    out = []
    with f.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                out.append({"id": int(r["id"]), "building_id": int(r["building_id"]), "date": r["date"],
                            "liters": float(r["liters"] or 0), "uah": float(r["uah"] or 0), "note": r.get("note") or ""})
            except (KeyError, ValueError):
                continue
    return out


def _write_fuel(rows: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fuel.", suffix=".tmp", dir=DATA)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "building_id", "date", "liters", "uah", "note"])
        for r in rows:
            w.writerow([r["id"], r["building_id"], r["date"], r["liters"], r["uah"], r["note"]])
    os.replace(tmp, _fuel_file())


def gen_money(gen: dict | None, fuel_rows: list[dict], year: int) -> dict | None:
    """Скільки вкладено в генератор і скільки йде на пальне за рік (журнал або оцінка)."""
    if not gen:
        return None
    kw = gen["generator_kw"]
    capex_real = gen.get("cost_uah")
    est_l, est_uah = gen_fuel_estimate_year(kw)
    yr = [r for r in fuel_rows if r["date"][:4] == str(year)]
    return {"capex_uah": capex_real if capex_real is not None else gen_capex_estimate(kw),
            "capex_source": "введено" if capex_real is not None else MOCK,
            "bought": gen.get("bought"), "doc": gen.get("doc"),
            "fuel_year": year,
            "fuel_year_l": round(sum(r["liters"] for r in yr)) if yr else est_l,
            "fuel_year_uah": round(sum(r["uah"] for r in yr)) if yr else est_uah,
            "fuel_source": "журнал" if yr else MOCK,
            "fuel_entries": len(yr)}


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
    g = generator_of(b, read_generators())
    bo = blackout(b, sites.registry.get(b.id), g)
    fuel = [r for r in read_fuel() if r["building_id"] == b.id]
    fuel.sort(key=lambda r: r["date"], reverse=True)
    return {"id": b.id, "source": MOCK, **_round(bo), "money": gen_money(g, fuel, _now().year),
            "fuel_log": fuel, "can_edit": can_edit_ses(user, b.id)}


@router.get("/api/blackout")
def blackout_all(user: User = Depends(current_user)):
    """Зведення по громаді: скільки об'єктів протримається при повному блекауті."""
    if user.role not in ("energy_manager", "data_admin"):
        raise HTTPException(403, "Лише провідний фахівець з енергозабезпечення / адміністратор даних")
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
    from .outages import outages as _out
    worst = _out(user).get("worst_longest_h")  # найдовше відключення сьогодні за ГПВ Полтаваобленерго
    items.sort(key=best)
    return {"source": MOCK, "updated_at": now.isoformat(timespec="seconds"), "horizon_h": HORIZON_H,
            "totals": {"objects": len(items), "with_generator": sum(1 for i in items if i["generator_kw"]),
                       "with_battery": sum(1 for i in items if i["battery_kwh"]),
                       "hold_24h": sum(1 for i in items if best(i) >= 24),
                       "outage_today_h": worst,
                       "hold_today": sum(1 for i in items if worst is not None and best(i) >= worst),
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
    cost = body.get("cost_uah")
    try:
        cost = None if cost in (None, "") else float(cost)
    except (TypeError, ValueError):
        raise HTTPException(422, "cost_uah — число")
    if cost is not None and not (0 <= cost <= 50_000_000):
        raise HTTPException(422, "Вартість поза межами")
    bought = str(body.get("bought") or "")[:10] or None
    if bought:
        try:
            date.fromisoformat(bought)
        except ValueError:
            raise HTTPException(422, "Дата покупки — РРРР-ММ-ДД")
    doc = str(body.get("doc") or "")[:200] or None
    with _lock:
        gens = read_generators()
        gens[b.id] = {"generator_kw": kw, "fuel": fuel, "tank_l": tank, "source": "введено",
                      "cost_uah": cost, "bought": bought, "doc": doc}
        DATA.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".generators.", suffix=".tmp", dir=DATA)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["building_id", "generator_kw", "fuel", "tank_l", "cost_uah", "bought", "doc"])
            for k in sorted(gens):
                g = gens[k]
                w.writerow([k, g["generator_kw"], g["fuel"], g["tank_l"],
                            "" if g.get("cost_uah") is None else g["cost_uah"], g.get("bought") or "", g.get("doc") or ""])
        os.replace(tmp, GEN_FILE)
    return blackout_item(bid, user)


# ---------------- журнал пального й зведення витрат ----------------

@router.post("/api/generator/{bid}/fuel")
def fuel_add(bid: int, body: dict = Body(...), user: User = Depends(current_user)):
    store, _ = _ctx()
    b = _find(store, bid)
    if not can_edit_ses(user, b.id):
        raise HTTPException(403, "Немає прав редагувати дані об'єкта")
    try:
        d = date.fromisoformat(str(body.get("date") or ""))
        liters = float(body.get("liters") or 0)
        uah = float(body.get("uah") or 0)
    except (TypeError, ValueError):
        raise HTTPException(422, "date — РРРР-ММ-ДД, liters і uah — числа")
    if not (0 < liters <= 100_000 and 0 <= uah <= 10_000_000) or d > _now().date():
        raise HTTPException(422, "Значення поза межами")
    note = str(body.get("note") or "")[:200]
    with _lock:
        rows = read_fuel()
        nid = max((r["id"] for r in rows), default=0) + 1
        rows.append({"id": nid, "building_id": b.id, "date": d.isoformat(), "liters": liters,
                     "uah": uah or round(liters * FUEL_PRICE_UAH_L, 2), "note": note})
        _write_fuel(rows)
    return blackout_item(bid, user)


@router.delete("/api/generator/{bid}/fuel/{eid}")
def fuel_delete(bid: int, eid: int, user: User = Depends(current_user)):
    store, _ = _ctx()
    b = _find(store, bid)
    if not can_edit_ses(user, b.id):
        raise HTTPException(403, "Немає прав редагувати дані об'єкта")
    with _lock:
        rows = read_fuel()
        keep = [r for r in rows if not (r["id"] == eid and r["building_id"] == b.id)]
        if len(keep) == len(rows):
            raise HTTPException(404, "Запис не знайдено")
        _write_fuel(keep)
    return blackout_item(bid, user)


@router.get("/api/generators")
def generators_summary(user: User = Depends(current_user)):
    """Витрати на резервне живлення: вкладено в генератори й пальне за рік. Лише гроші, без автономії."""
    if user.role not in ("energy_manager", "data_admin", "finance"):
        raise HTTPException(403, "Лише провідний фахівець з енергозабезпечення, адміністратор даних або фінансовий орган")
    store, _ = _ctx()
    gens = read_generators()
    fuel = read_fuel()
    year = _now().year
    by_b: dict[int, list] = {}
    for r in fuel:
        by_b.setdefault(r["building_id"], []).append(r)
    items, depts = [], {}
    for b in store.buildings:
        g = generator_of(b, gens)
        if not g:
            continue
        m = gen_money(g, by_b.get(b.id, []), year)
        dep = department_of(b)
        items.append({"id": b.id, "name": b.name, "department": dep, "generator_kw": g["generator_kw"],
                      "generator_source": g["source"], **m})
        d = depts.setdefault(dep, {"department": dep, "count": 0, "kw": 0.0, "capex_uah": 0.0, "fuel_year_uah": 0.0})
        d["count"] += 1
        d["kw"] += g["generator_kw"]
        d["capex_uah"] += m["capex_uah"]
        d["fuel_year_uah"] += m["fuel_year_uah"]
    items.sort(key=lambda i: -i["fuel_year_uah"])
    tot = lambda k: round(sum(i[k] for i in items))
    if user.role == "finance":
        # фінансовий орган: лише гроші (разом і по розпорядниках), без переліку закладів і кВт —
        # перелік об'єктів з генераторами = резервне живлення, яке finance не бачить
        return {"year": year, "demo": True, "aggregates_only": True,
                "totals": {"count": len(items), "capex_uah": tot("capex_uah"),
                           "fuel_year_uah": tot("fuel_year_uah"), "fuel_year_l": tot("fuel_year_l")},
                "departments": sorted(({"department": d["department"], "count": d["count"],
                                        "capex_uah": round(d["capex_uah"]),
                                        "fuel_year_uah": round(d["fuel_year_uah"])} for d in depts.values()),
                                      key=lambda d: -d["capex_uah"]),
                "items": None,
                "assumptions": {"fuel_price_uah_l": FUEL_PRICE_UAH_L}}
    return {"year": year, "demo": True, "aggregates_only": False,
            "totals": {"count": len(items), "kw": tot("generator_kw"), "capex_uah": tot("capex_uah"),
                       "capex_real": sum(1 for i in items if i["capex_source"] != MOCK),
                       "fuel_year_uah": tot("fuel_year_uah"), "fuel_year_l": tot("fuel_year_l"),
                       "fuel_real": sum(1 for i in items if i["fuel_source"] == "журнал")},
            "departments": sorted(({**d, "kw": round(d["kw"]), "capex_uah": round(d["capex_uah"]),
                                    "fuel_year_uah": round(d["fuel_year_uah"])} for d in depts.values()),
                                  key=lambda d: -d["capex_uah"]),
            "items": items,
            "assumptions": {"uah_per_kw": [p for _, p in GEN_UAH_PER_KW], "install_share": GEN_INSTALL_SHARE,
                            "hours_year": GEN_HOURS_YEAR, "load": GEN_LOAD, "fuel_l_per_kwh": FUEL_L_PER_KWH,
                            "fuel_price_uah_l": FUEL_PRICE_UAH_L}}
