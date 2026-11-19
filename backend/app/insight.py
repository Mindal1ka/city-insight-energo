"""v2: лише електроенергія + СЕС. Департаменти й фінансові ліміти, live-стан інверторів (МОК),
розподіл енергії за добу, «скільки доставити», рекомендації перерозподілу надлишку, звернення, звіт за місяць.

Що МОК (позначається в API `source: "МОК"`):
- ліміт: кВт·год 2025 × тариф × коефіцієнт 0,9–1,1 (детерміновано за id), можна перевизначити (data/limits.csv);
- live-стан інвертора: з погодинної моделі sites.simulate_day на поточну годину + шум;
  пізніше замінюється адаптером Deye / Growatt / LuxPower з тим самим форматом (LIVE_FIELDS).
Реальне: споживання 2025 (UMUNI), генерація PVGIS, категорія й назва закладу.
"""

from __future__ import annotations

import csv
import json
import math
import random
import tempfile
import threading
import os
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response

from . import calib
from . import efficiency as eff
from . import solar
from .auth import User, can_see_finance, can_see_sensitive, current_user
from .sites import KYIV, PV_DERATE, simulate_day
from .ses_api import FULL, PUBLIC, SES, _coords, _ctx, _day, _evaluations, _find, access_level

router = APIRouter(tags=["v2: бюджет, live, розподіл"])

DATA = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
LIMITS_FILE = DATA / "limits.csv"
APPEALS_FILE = DATA / "appeals.json"
_lock = threading.Lock()

MOCK = "МОК"
LIMIT_FACTOR = (0.9, 1.1)
OFFLINE_SHARE = 0.03  # ~3 % інверторів «не на зв'язку» (МОК), щоб інтерфейс показував і цей стан

# --- департаменти-розпорядники (оплата е/е йде з їхніх кошторисів) ---
D_EDU = "Управління освіти"
D_HEALTH = "Управління охорони здоров'я"
D_CULT = "Управління культури"
D_SPORT = "Управління молоді та спорту"
D_HOUSING = "Департамент ЖКГ"
D_ADMIN = "Виконавчий комітет"
DEPARTMENTS = (D_EDU, D_HEALTH, D_CULT, D_SPORT, D_HOUSING, D_ADMIN)
_CULT_WORDS = ("бібліот", "музей", "клуб", "будинок культури", "палац культури", "школа мистецтв",
               "музична школа", "художня школа", "театр", "філармон", "центр культури")
_ADMIN_WORDS = ("міська рада", "виконавч", "староста", "старостин", "управління", "департамент", "цнап")


def department_of(b) -> str:
    """Розпорядник коштів за категорією й назвою (ПРАВИЛО, уточнюється містом)."""
    cat = b.category_short or ""
    name = (b.name or "").lower()
    if cat in ("Заклади освіти", "Дошкільні заклади"):
        return D_CULT if any(w in name for w in ("мистецтв", "музичн", "художн")) else D_EDU
    if cat == "Охорона здоров'я":
        return D_HEALTH
    if cat == "Спортивні споруди" or "спорт" in name or "стадіон" in name:
        return D_SPORT
    if any(w in name for w in _CULT_WORDS):
        return D_CULT
    if any(w in name for w in _ADMIN_WORDS):
        return D_ADMIN
    return D_HOUSING


# --- індекс ефективності споживання е/е: кВт·год/м² ÷ медіана категорії (1 = типово, > 1 — гірше) ---

_eidx_cache: dict[int, dict[int, float]] = {}


def efficiency_index(store) -> dict[int, float]:
    key = id(store.buildings)
    if key in _eidx_cache:
        return _eidx_cache[key]
    import statistics
    per = {}
    for b in store.buildings:
        y = b.years.get(2025)
        if y and y.elec_kwh and b.heated_area and b.heated_area > 10:
            per[b.id] = (b.category_short, y.elec_kwh / b.heated_area)
    med = {}
    for cat in {c for c, _ in per.values()}:
        vals = [v for c, v in per.values() if c == cat]
        med[cat] = statistics.median(vals)
    res = {bid: round(v / med[c], 2) for bid, (c, v) in per.items() if med[c]}
    _eidx_cache.clear()
    _eidx_cache[key] = res
    return res


# --- ліміти ---

def _read_limits() -> dict[int, float]:
    if not LIMITS_FILE.exists():
        return {}
    out = {}
    with LIMITS_FILE.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                out[int(r["building_id"])] = float(r["limit_uah_year"])
            except (KeyError, ValueError):
                continue
    return out


def _write_limits(lim: dict[int, float]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".limits.", suffix=".tmp", dir=DATA)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["building_id", "limit_uah_year"])
        for k in sorted(lim):
            w.writerow([k, round(lim[k], 2)])
    os.replace(tmp, LIMITS_FILE)


def limit_year(b, tariff: float, overrides: dict[int, float]) -> tuple[float, str]:
    """Ліміт на рік: введений вручну → реальний план програми 2026 (openbudget) → МОК (лікарні тощо)."""
    if b.id in overrides:
        return overrides[b.id], "введено"
    from . import budget_real
    from .main import store
    real = budget_real.limit_year(b, store)
    if real:
        return real, budget_real.SOURCE
    f = random.Random(f"limit-{b.id}").uniform(*LIMIT_FACTOR)
    return eff.elec_2025(b) * tariff * f, MOCK


def budget(b, ev: dict, d: date, tariff: float, overrides: dict[int, float]) -> dict:
    """Ліміт рік → місяць (сезонний профіль) → день; оплачено = з мережі × тариф."""
    ly, src = limit_year(b, tariff, overrides)
    shares = solar.profile_shares(b.category_short)
    m = d.month - 1
    dim = _days_in_month(d)
    lm = ly * shares[m]
    paid_m = ev["monthly"][m]["grid_kwh"] * tariff
    paid_y = ev["energy"]["year"]["grid_kwh"] * tariff
    no_ses_y = ev["energy"]["year"]["cons_kwh"] * tariff  # скільки коштувало б без СЕС
    return {"source": src, "limit_uah": {"year": ly, "month": lm, "day": lm / dim},
            "paid_uah": {"year": paid_y, "month": paid_m, "day": paid_m / dim},
            "without_ses_uah_year": no_ses_y,
            "used_pct": {"year": 100 * paid_y / ly if ly else None, "month": 100 * paid_m / lm if lm else None},
            "balance_uah": {"year": ly - paid_y, "month": lm - paid_m}}


def _days_in_month(d: date) -> int:
    import calendar
    return calendar.monthrange(d.year, d.month)[1]


def _r(x, n=0):
    if x is None:
        return None
    return round(x) if n == 0 else round(x, n)


def budget_out(bu: dict) -> dict:
    return {"source": bu["source"],
            "limit_uah": {k: _r(v) for k, v in bu["limit_uah"].items()},
            "paid_uah": {k: _r(v) for k, v in bu["paid_uah"].items()},
            "without_ses_uah_year": _r(bu["without_ses_uah_year"]),
            "used_pct": {k: _r(v, 1) for k, v in bu["used_pct"].items()},
            "balance_uah": {k: _r(v) for k, v in bu["balance_uah"].items()}}


# --- скільки доставити ---

def kw_per_year() -> float:
    return sum(solar.pvgis_monthly()) * PV_DERATE


def sizing(b, ses: dict | None, ev: dict, tariff: float) -> dict:
    """Скільки доставити — лише з кВт·год (без м²).

    Панелі: потужність, за якої річна генерація = річному споживанню (K = 1).
    Акумулятор: вечірня частка добового споживання (1 − DAYTIME_SHARE) × середня доба.
    Ефект: та сама помісячна модель (efficiency.monthly) для станції «після», різниця власного споживання × тариф.
    """
    cons = ev["energy"]["year"]["cons_kwh"]
    if not cons:
        return {"need": False, "add_kw": 0.0, "reason": "немає даних споживання"}
    has = ev["has_ses"]
    cur_kw = ((ses or {}).get("total_kw") or 0.0) if has else 0.0
    cur_bat = ((ses or {}).get("battery_kwh") or 0.0) if has else 0.0
    need_kw = cons / kw_per_year()
    need_bat = (1 - solar.DAYTIME_SHARE) * cons / 365
    add_kw = math.floor(max(0.0, need_kw - cur_kw) * 2) / 2
    add_bat = math.floor(max(0.0, need_bat - cur_bat) / 2.5) * 2.5  # модулі по 2,5 кВт·год
    need = (has and (ev["k"]["year"] or 0) < eff.LOW and add_kw >= solar.MIN_KW) or (not has and add_kw >= solar.MIN_KW)
    if not need:
        add_kw = add_bat = 0.0
    after = eff.monthly(b, {"total_kw": cur_kw + add_kw, "battery_kwh": cur_bat + add_bat})
    self_after = sum(m["self_kwh"] for m in after)
    gen_after = sum(m["gen_kwh"] for m in after)
    saved = max(0.0, self_after - ev["energy"]["year"]["self_kwh"]) * tariff
    capex = 0.0
    if need:
        from .sites import BATTERY_UAH_PER_KWH, INSTALL_FIXED_UAH, INSTALL_SHARE, INVERTER_UAH_PER_KW, PANEL_UAH_PER_450W
        eq = add_kw * 1000 / 450 * PANEL_UAH_PER_450W + add_kw * INVERTER_UAH_PER_KW + add_bat * BATTERY_UAH_PER_KWH
        capex = eq * (1 + INSTALL_SHARE) + (INSTALL_FIXED_UAH if not has else 0.0)
    return {"need": bool(need), "current_kw": cur_kw, "current_battery_kwh": cur_bat,
            "need_kw": need_kw, "need_battery_kwh": need_bat,
            "add_kw": add_kw, "add_battery_kwh": add_bat,
            "cons_kwh_month_avg": cons / 12, "deficit_kwh_year": max(0.0, cons - ev["energy"]["year"]["gen_kwh"]),
            "gen_kwh_year_after": gen_after, "self_kwh_year_after": self_after,
            "k_after": gen_after / cons if cons else None,
            "capex_uah": capex, "saved_uah_year": saved,
            "payback_years": capex / saved if need and saved > 0 else None}


def sizing_out(s: dict) -> dict:
    return {k: (_r(v, 1) if isinstance(v, float) else v) for k, v in s.items()}


# --- live (МОК) і розподіл доби ---

LIVE_FIELDS = ("gen_kw", "load_kw", "grid_kw", "battery_kw", "soc_pct", "today_gen_kwh", "today_load_kwh")


def _now() -> datetime:
    return datetime.now(KYIV)


def live_state(b, ses: dict | None, now: datetime | None = None) -> dict | None:
    """Поточний стан інвертора. grid_kw > 0 — купуємо з мережі, < 0 — віддаємо надлишок."""
    if not eff.has_station(ses):
        return None
    now = now or _now()
    rows = simulate_day(b, ses, now.date())
    h = now.hour
    r = rows[h]
    jit = random.Random(f"live-{b.id}-{now:%Y%m%d%H%M}")
    gen = r["gen_kwh"] * jit.uniform(0.85, 1.12)
    load = r["cons_kwh"] * jit.uniform(0.9, 1.1)
    bat = r["to_battery_kwh"] - r["from_battery_kwh"]  # > 0 — заряд
    grid = load - gen + bat
    frac = now.minute / 60
    offline = random.Random(f"off-{b.id}-{now.date()}").random() < OFFLINE_SHARE
    done = rows[:h]
    return {"source": MOCK, "adapter": "mock", "status": "offline" if offline else "online",
            "updated_at": now.isoformat(timespec="seconds"),
            "gen_kw": gen, "load_kw": load, "grid_kw": grid, "battery_kw": bat, "soc_pct": r["soc_pct"],
            "today_gen_kwh": sum(x["gen_kwh"] for x in done) + r["gen_kwh"] * frac,
            "today_load_kwh": sum(x["cons_kwh"] for x in done) + r["cons_kwh"] * frac}


def live_out(lv: dict | None) -> dict | None:
    if not lv:
        return None
    return {**lv, **{k: _r(lv[k], 1) for k in LIVE_FIELDS}}


def distribution(b, ses: dict | None, now: datetime | None = None) -> dict:
    """Вікно 3: пік доби, доступна енергія (акумулятор + сонце до кінця дня), баланс +/−, запас."""
    now = now or _now()
    st = ses if eff.has_station(ses) else None
    rows = simulate_day(b, st, now.date())
    h = now.hour
    peak = max(rows, key=lambda r: r["cons_kwh"])
    bat_now = rows[h - 1]["soc_kwh"] if h else (rows[0]["soc_kwh"] - rows[0]["to_battery_kwh"])
    bat_cap = (st or {}).get("battery_kwh") or 0.0
    reserve_floor = 0.2 * bat_cap
    usable_bat = max(0.0, bat_now - reserve_floor)
    sun_left = sum(r["gen_kwh"] for r in rows[h:])
    demand_left = sum(r["cons_kwh"] for r in rows[h:])
    available = usable_bat + sun_left
    bal = available - demand_left
    return {"hour": h, "peak_kw": peak["cons_kwh"], "peak_hour": peak["hour"],
            "battery_kwh_now": bat_now, "battery_capacity_kwh": bat_cap, "battery_usable_kwh": usable_bat,
            "sun_left_kwh": sun_left, "demand_left_kwh": demand_left, "available_kwh": available,
            "balance_kwh": bal, "enough": bal >= 0, "reserve_kwh": max(0.0, bal),
            "day_gen_kwh": sum(r["gen_kwh"] for r in rows), "day_cons_kwh": sum(r["cons_kwh"] for r in rows),
            "hourly": [{"hour": r["hour"], "gen_kwh": round(r["gen_kwh"], 2), "cons_kwh": round(r["cons_kwh"], 2),
                        "soc_pct": r["soc_pct"], "grid_kwh": round(r["from_grid_kwh"], 2),
                        "surplus_kwh": round(r["surplus_kwh"], 2)} for r in rows]}


def distribution_out(x: dict) -> dict:
    return {k: (_r(v, 1) if isinstance(v, float) else v) for k, v in x.items()}


# ---------------- GET /api/insight/{id} ----------------

@router.get("/api/insight/{bid}")
def insight_item(bid: int, day: str | None = None, tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
                 user: User = Depends(current_user)):
    store, sites = _ctx()
    b = _find(store, bid)
    d = _day(day)
    ses = sites.registry.get(b.id)
    ev = eff.evaluate(b, ses, d, tariff)
    lvl = access_level(user, b)
    fin = lvl != PUBLIC and can_see_finance(user, b.category_short, b.id)
    sens = can_see_sensitive(user, b.category_short, b.id)
    out = {"demo": True, "id": b.id, "department": department_of(b), "day": d.isoformat(),
           "monthly_kwh": [round(m["cons_kwh"]) for m in ev["monthly"]],
           # помісячно: спожито, згенеровано, через акумулятор, надлишок, з мережі, заощаджено
           "months": [{"month": m["month"], "cons_kwh": round(m["cons_kwh"]),
                       "gen_kwh": round(m["gen_kwh"]) if lvl != PUBLIC else None,
                       "self_kwh": round(m["self_kwh"]) if lvl != PUBLIC else None,
                       "battery_kwh": round(m.get("battery_kwh", 0)) if sens else None,
                       "surplus_kwh": round(m["surplus_kwh"]) if lvl != PUBLIC else None,
                       "grid_kwh": round(m["grid_kwh"]) if lvl != PUBLIC else None,
                       "saved_uah": round(m["self_kwh"] * tariff) if fin else None} for m in ev["monthly"]],
           "battery_capacity_kwh": ((ses or {}).get("battery_kwh") or 0) if sens and ev["has_ses"] else None,
           # реальні дані UMUNI: 2025 повний рік, 2026 до дати вивантаження → оцінка 2026 і тренд
           "y2026": calib.estimate_out(calib.estimate(b, store)),
           "budget": budget_out(budget(b, ev, d, tariff, _read_limits())) if fin else None,
           "sizing": sizing_out(sizing(b, ses, ev, tariff)) if lvl != PUBLIC else None,
           "live": live_out(live_state(b, ses)) if lvl != PUBLIC else None,
           "distribution": distribution_out(distribution(b, ses)) if lvl != PUBLIC else None}
    if out["live"] and not sens:  # роль finance: без акумуляторів
        out["live"]["soc_pct"] = out["live"]["battery_kw"] = None
    if out["distribution"] and not sens:
        for k in ("battery_kwh_now", "battery_capacity_kwh", "battery_usable_kwh"):
            out["distribution"][k] = None
    return out


@router.put("/api/limits/{bid}")
def limit_update(bid: int, body: dict = Body(...), user: User = Depends(current_user)):
    if user.role not in ("energy_manager", "finance"):
        raise HTTPException(403, "Ліміт змінюють енергоменеджер або фінансовий орган")
    store, _ = _ctx()
    b = _find(store, bid)
    v = body.get("limit_uah_year")
    with _lock:
        lim = _read_limits()
        if v in (None, ""):
            lim.pop(b.id, None)
        else:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                raise HTTPException(422, "limit_uah_year — число, грн/рік")
            if not 0 <= fv <= 1e10:
                raise HTTPException(422, "limit_uah_year поза межами")
            lim[b.id] = fv
        _write_limits(lim)
    return {"id": b.id, "limit_uah_year": lim.get(b.id), "source": "введено" if b.id in lim else MOCK}


# ---------------- GET /api/live ----------------

@router.get("/api/live")
def live_all(user: User = Depends(current_user)):
    """Live-стан усіх станцій (МОК) + розподіл доби по громаді."""
    store, sites = _ctx()
    now = _now()
    items, tot = [], {"gen_kw": 0.0, "load_kw": 0.0, "grid_kw": 0.0, "online": 0, "offline": 0,
                      "available_kwh": 0.0, "demand_left_kwh": 0.0, "battery_kwh_now": 0.0}
    for b in store.buildings:
        ses = sites.registry.get(b.id)
        lv = live_state(b, ses, now)
        if not lv:
            continue
        ds = distribution(b, ses, now)
        tot[lv["status"]] += 1
        if lv["status"] == "online":
            for k in ("gen_kw", "load_kw", "grid_kw"):
                tot[k] += lv[k]
        tot["available_kwh"] += ds["available_kwh"]
        tot["demand_left_kwh"] += ds["demand_left_kwh"]
        tot["battery_kwh_now"] += ds["battery_kwh_now"]
        lvl = access_level(user, b)
        if lvl == PUBLIC:
            continue
        lo = live_out(lv)
        if lvl == SES:
            lo["soc_pct"] = lo["battery_kw"] = None
        items.append({"id": b.id, "name": b.name, "department": department_of(b), **lo,
                      "peak_kw": _r(ds["peak_kw"], 1), "balance_kwh": _r(ds["balance_kwh"], 1),
                      "enough": ds["enough"]})
    bal = tot["available_kwh"] - tot["demand_left_kwh"]
    return {"source": MOCK, "updated_at": now.isoformat(timespec="seconds"),
            "totals": {**{k: _r(v, 1) if isinstance(v, float) else v for k, v in tot.items()},
                       "balance_kwh": _r(bal, 1), "enough": bal >= 0},
            "items": items}


# ---------------- GET /api/departments ----------------

@router.get("/api/departments")
def departments(day: str | None = None, tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
                user: User = Depends(current_user)):
    store, sites = _ctx()
    d = _day(day)
    lim = _read_limits()
    agg = {n: {"department": n, "objects": 0, "with_ses": 0, "deficit": 0, "surplus": 0, "over_limit": 0,
               "cons_kwh_year": 0.0, "gen_kwh_year": 0.0, "limit_uah_year": 0.0, "paid_uah_year": 0.0,
               "without_ses_uah_year": 0.0, "saved_uah_year": 0.0, "invested_uah": 0.0,
               "limit_uah_month": 0.0, "paid_uah_month": 0.0} for n in DEPARTMENTS}
    for b, ses, ev in _evaluations(store, sites, d, tariff, eff.SURPLUS_PRICE_UAH_KWH):
        a = agg[department_of(b)]
        bu = budget(b, ev, d, tariff, lim)
        a["objects"] += 1
        a["cons_kwh_year"] += ev["energy"]["year"]["cons_kwh"]
        a["limit_uah_year"] += bu["limit_uah"]["year"]
        a["paid_uah_year"] += bu["paid_uah"]["year"]
        a["limit_uah_month"] += bu["limit_uah"]["month"]
        a["paid_uah_month"] += bu["paid_uah"]["month"]
        a["without_ses_uah_year"] += bu["without_ses_uah_year"]
        a["over_limit"] += bu["balance_uah"]["year"] < 0
        if ev["has_ses"]:
            a["with_ses"] += 1
            a["gen_kwh_year"] += ev["energy"]["year"]["gen_kwh"]
            a["saved_uah_year"] += ev["finance"]["saved_uah"]["year"]
            a["invested_uah"] += ev["finance"]["invested_uah"] or 0
            a["deficit"] += ev["k_class"]["year"] == eff.C_LOW
            a["surplus"] += ev["k_class"]["year"] == eff.C_HIGH
    rows = []
    for a in agg.values():
        if not a["objects"]:
            continue
        a["balance_uah_year"] = a["limit_uah_year"] - a["paid_uah_year"]
        a["used_pct_year"] = 100 * a["paid_uah_year"] / a["limit_uah_year"] if a["limit_uah_year"] else None
        a["payback_years"] = a["invested_uah"] / a["saved_uah_year"] if a["saved_uah_year"] else None
        rows.append({k: (_r(v, 1) if k in ("used_pct_year", "payback_years") else _r(v))
                     if isinstance(v, float) else v for k, v in a.items()})
    rows.sort(key=lambda r: -r["paid_uah_year"])
    keys = ("objects", "with_ses", "deficit", "surplus", "over_limit", "cons_kwh_year", "gen_kwh_year",
            "limit_uah_year", "paid_uah_year", "without_ses_uah_year", "saved_uah_year", "invested_uah",
            "balance_uah_year", "limit_uah_month", "paid_uah_month")
    tot = {k: sum(r[k] or 0 for r in rows) for k in keys}
    tot["used_pct_year"] = _r(100 * tot["paid_uah_year"] / tot["limit_uah_year"], 1) if tot["limit_uah_year"] else None
    return {"source": MOCK, "tariff_uah_kwh": tariff, "month": d.month, "totals": tot, "items": rows}


# ---------------- GET /api/network (вікно 4) ----------------

def _km(a, b) -> float | None:
    (la1, lo1, _), (la2, lo2, _) = _coords(a), _coords(b)
    if None in (la1, lo1, la2, lo2):
        return None
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2
         + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


@router.get("/api/network")
def network(period: Literal["day", "month", "year"] = "year", day: str | None = None,
            tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100), user: User = Depends(current_user)):
    """Σ генерація / Σ споживання / різниця / K і пари «надлишок → дефіцит» (рекомендація перенести панелі)."""
    store, sites = _ctx()
    d = _day(day)
    evs = _evaluations(store, sites, d, tariff, eff.SURPLUS_PRICE_UAH_KWH)
    gen = cons = surplus = grid = 0.0
    donors, takers = [], []
    kwy = kw_per_year()
    for b, ses, ev in evs:
        if not ev["has_ses"] or not ev["has_data"]:
            continue
        en = ev["energy"][period]
        gen += en["gen_kwh"]
        cons += en["cons_kwh"]
        surplus += en["surplus_kwh"]
        grid += en["grid_kwh"]
        ky = ev["k"]["year"] or 0
        kw = ses.get("total_kw") or 0
        if ky > eff.HIGH:
            donors.append([b, kw - kw / ky * eff.HIGH if ky else 0, ev])  # зайве понад K = 1,2
        elif ky < eff.LOW:
            takers.append([b, ev["energy"]["year"]["cons_kwh"] / kwy * eff.LOW - kw, ev])
    pairs = []
    n_donors, n_takers = len(donors), len(takers)
    donors.sort(key=lambda x: -x[1])
    for dn in donors:
        while dn[1] >= 1 and takers:
            cand = [(t, _km(dn[0], t[0])) for t in takers if t[1] >= 1]
            if not cand:
                break
            same = department_of(dn[0])
            t, km = min(cand, key=lambda c: (department_of(c[0][0]) != same, c[1] if c[1] is not None else 1e9))
            mv = math.floor(min(dn[1], t[1]) * 2) / 2
            if mv < 1:
                break
            pairs.append({"from_id": dn[0].id, "from_name": dn[0].name, "to_id": t[0].id, "to_name": t[0].name,
                          "same_department": department_of(t[0]) == same, "department_from": same,
                          "department_to": department_of(t[0]), "distance_km": _r(km, 1), "move_kw": mv,
                          "gain_kwh_year": round(mv * kwy), "saved_uah_year": round(mv * kwy * tariff * 0.9)})
            dn[1] -= mv
            t[1] -= mv
            takers = [x for x in takers if x[1] >= 1]
    public = user.role == "public"
    return {"demo": True, "period": period, "day": d.isoformat(),
            "totals": {"gen_kwh": round(gen), "cons_kwh": round(cons), "diff_kwh": round(gen - cons),
                       "k": eff.r2(gen / cons) if cons else None, "surplus_kwh": round(surplus),
                       "grid_kwh": round(grid), "surplus_uah": round(surplus * tariff),
                       "donors": n_donors, "takers": n_takers,
                       "pairs": len(pairs), "move_kw": sum(p["move_kw"] for p in pairs)},
            "pairs": None if public else pairs[:50],
            "note": "Рекомендація: перенести частину панелей/акумуляторів зі станцій із надлишком на об'єкти з "
                    "дефіцитом. Перетоку енергії між закладами немає: бюджетна установа не може продавати е/е."}


# ---------------- звіт за місяць (вікно 7) ----------------

def _report(user: User, month: str | None, tariff: float):
    store, sites = _ctx()
    today = _now().date()
    if month:
        try:
            y, m = (int(x) for x in month.split("-"))
            d = date(y, m, 1)
        except ValueError:
            raise HTTPException(422, "month — у форматі РРРР-ММ")
    else:
        d = today.replace(day=1)
    lim = _read_limits()
    rows, tot = [], {k: 0.0 for k in ("cons_kwh", "gen_kwh", "self_kwh", "surplus_kwh", "grid_kwh", "cost_uah",
                                      "saved_uah", "limit_uah", "saved_uah_year", "invested_uah",
                                      "saved_since_launch_uah")}
    for b, ses, ev in _evaluations(store, sites, d, tariff, eff.SURPLUS_PRICE_UAH_KWH):
        mm = ev["monthly"][d.month - 1]
        bu = budget(b, ev, d, tariff, lim)
        r = {"id": b.id, "name": b.name, "department": department_of(b), "has_ses": ev["has_ses"],
             "cons_kwh": mm["cons_kwh"], "gen_kwh": mm["gen_kwh"], "self_kwh": mm["self_kwh"],
             "surplus_kwh": mm["surplus_kwh"], "grid_kwh": mm["grid_kwh"], "cost_uah": mm["grid_kwh"] * tariff,
             "saved_uah": mm["self_kwh"] * tariff, "limit_uah": bu["limit_uah"]["month"],
             "saved_uah_year": ev["finance"]["saved_uah"]["year"],
             "invested_uah": ev["finance"]["invested_uah"] or 0.0,
             "saved_since_launch_uah": ev["finance"]["saved_uah"]["since_launch"]}
        for k in tot:
            tot[k] += r[k]
        if access_level(user, b) == PUBLIC or not can_see_finance(user, b.category_short, b.id):
            continue
        rows.append({k: (_r(v) if isinstance(v, float) else v) for k, v in r.items()})
    t = {k: _r(v) for k, v in tot.items()}
    t["over_limit_uah"] = max(0, t["cost_uah"] - t["limit_uah"])
    t["k"] = eff.r2(tot["gen_kwh"] / tot["cons_kwh"]) if tot["cons_kwh"] else None
    return d, t, rows


@router.get("/api/report")
def report(month: str | None = None, tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
           user: User = Depends(current_user)):
    d, t, rows = _report(user, month, tariff)
    return {"demo": True, "month": f"{d:%Y-%m}", "tariff_uah_kwh": tariff, "totals": t, "items": rows}


REPORT_COLS = (("id", "id"), ("name", "Об'єкт"), ("department", "Розпорядник"), ("has_ses", "СЕС"),
               ("cons_kwh", "Спожито, кВт·год"), ("gen_kwh", "Згенеровано, кВт·год"),
               ("self_kwh", "Власне споживання, кВт·год"), ("surplus_kwh", "Надлишок, кВт·год"),
               ("grid_kwh", "З мережі, кВт·год"), ("cost_uah", "Вартість, грн"), ("limit_uah", "Ліміт, грн"),
               ("saved_uah", "Заощаджено за місяць, грн"), ("saved_uah_year", "Заощаджено за рік, грн"),
               ("invested_uah", "Вкладено в СЕС, грн"), ("saved_since_launch_uah", "Заощаджено від запуску, грн"))


@router.get("/api/report.csv")
def report_csv(month: str | None = None, tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100),
               user: User = Depends(current_user)):
    import io
    d, t, rows = _report(user, month, tariff)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([h for _, h in REPORT_COLS])
    for r in rows:
        w.writerow(["так" if r[k] is True else "ні" if r[k] is False else r[k] for k, _ in REPORT_COLS])
    w.writerow(["", "РАЗОМ", "", ""] + [t.get(k) for k, _ in REPORT_COLS[4:]])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="report-{d:%Y-%m}.csv"'})


# ---------------- звернення (вікно 6) ----------------

APPEAL_TYPES = {"expand": "Потрібне розширення СЕС", "surplus": "Є надлишок — можемо передати",
                "over_limit": "Перевищення ліміту", "repair": "Несправність СЕС", "other": "Інше"}
APPEAL_STATUSES = ("нове", "в роботі", "виконано", "відхилено")


def _load_appeals() -> list[dict]:
    if not APPEALS_FILE.exists():
        return []
    try:
        return json.loads(APPEALS_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []


def _save_appeals(items: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".appeals.", suffix=".tmp", dir=DATA)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, APPEALS_FILE)


def _visible(user: User, a: dict, store) -> bool:
    if user.role in ("energy_manager", "data_admin", "finance"):
        return True
    if user.role == "facility_head":
        return a["building_id"] == user.building_id
    if user.role == "department":
        return True  # управління бачить звернення, адресовані йому (фільтр на фронті за to)
    return False


@router.get("/api/appeals")
def appeals_list(user: User = Depends(current_user)):
    if user.role == "public":
        raise HTTPException(401, "Потрібен вхід")
    store, _ = _ctx()
    items = [a for a in _load_appeals() if _visible(user, a, store)]
    items.sort(key=lambda a: a["created_at"], reverse=True)
    return {"types": APPEAL_TYPES, "statuses": APPEAL_STATUSES, "departments": DEPARTMENTS, "items": items}


@router.post("/api/appeals")
def appeals_create(body: dict = Body(...), user: User = Depends(current_user)):
    if user.role == "public":
        raise HTTPException(401, "Потрібен вхід")
    store, _ = _ctx()
    try:
        bid = int(body.get("building_id"))
    except (TypeError, ValueError):
        raise HTTPException(422, "building_id обов'язковий")
    b = _find(store, bid)
    if user.role == "facility_head" and user.building_id != b.id:
        raise HTTPException(403, "Керівник закладу подає звернення лише від свого об'єкта")
    typ = body.get("type") or "other"
    if typ not in APPEAL_TYPES:
        raise HTTPException(422, "Невідомий тип звернення")
    to = body.get("to") or department_of(b)
    if to not in DEPARTMENTS:
        raise HTTPException(422, "Невідомий адресат")
    text = str(body.get("text") or "").strip()[:2000]
    kw = body.get("kw")
    try:
        kw = None if kw in (None, "") else max(0.0, min(1e5, float(kw)))
    except (TypeError, ValueError):
        kw = None
    with _lock:
        items = _load_appeals()
        a = {"id": max((x["id"] for x in items), default=0) + 1, "building_id": b.id, "building_name": b.name,
             "type": typ, "type_name": APPEAL_TYPES[typ], "to": to, "kw": kw, "text": text,
             "status": APPEAL_STATUSES[0], "author": user.full_name, "author_role": user.role,
             "created_at": _now().isoformat(timespec="seconds"), "updated_at": None}
        items.append(a)
        _save_appeals(items)
    return a


@router.patch("/api/appeals/{aid}")
def appeals_update(aid: int, body: dict = Body(...), user: User = Depends(current_user)):
    if user.role not in ("energy_manager", "department", "finance"):
        raise HTTPException(403, "Статус змінюють енергоменеджер, управління або фінансовий орган")
    st = body.get("status")
    if st not in APPEAL_STATUSES:
        raise HTTPException(422, "Невідомий статус")
    with _lock:
        items = _load_appeals()
        for a in items:
            if a["id"] == aid:
                a["status"] = st
                a["updated_at"] = _now().isoformat(timespec="seconds")
                if body.get("answer"):
                    a["answer"] = str(body["answer"])[:2000]
                _save_appeals(items)
                return a
    raise HTTPException(404, "Звернення не знайдено")


# ---------------- GET /api/zones (зони мапи) ----------------

ZONE_RADIUS_KM = 0.35  # сусіди в радіусі 350 м від «якоря» (школа / об'єкт зі СЕС)


def _zones(store, has_ses: dict[int, bool]) -> list[list]:
    """Жадібно: якір (спершу зі СЕС, потім заклади освіти, потім за споживанням) + вільні сусіди в радіусі.

    Лише будівлі з точними координатами (без приблизних — до вулиці / села)."""
    pts = []
    for b in store.buildings:
        la, lo, approx = _coords(b)
        if la is not None and lo is not None and not approx:
            pts.append((b, la, lo))
    pts.sort(key=lambda p: (not has_ses.get(p[0].id), p[0].category_short not in ("Заклади освіти", "Дошкільні заклади"),
                            -eff.elec_2025(p[0])))
    kx = 111.32 * math.cos(49.59 * math.pi / 180)
    used: set[int] = set()
    groups = []
    for a in pts:
        if a[0].id in used:
            continue
        g = [a] + [p for p in pts if p[0].id not in used and p[0].id != a[0].id
                   and ((p[2] - a[2]) * kx) ** 2 + ((p[1] - a[1]) * 110.57) ** 2 <= ZONE_RADIUS_KM ** 2]
        if len(g) >= 2:
            used.update(p[0].id for p in g)
            groups.append(g)
    return groups


@router.get("/api/zones")
def zones(period: Literal["day", "month", "year"] = "month", day: str | None = None,
          tariff: float = Query(eff.TARIFF_UAH_KWH, gt=0, le=100), user: User = Depends(current_user)):
    """Зони: школа й сусідні комунальні будівлі. Баланс зони і скільки надлишку можна віддати сусідам."""
    store, sites = _ctx()
    d = _day(day)
    evmap = {b.id: (ses, ev) for b, ses, ev in _evaluations(store, sites, d, tariff, eff.SURPLUS_PRICE_UAH_KWH)}
    out = []
    for g in _zones(store, {bid: v[1]["has_ses"] for bid, v in evmap.items()}):
        mem, tot = [], {"cons_kwh": 0.0, "gen_kwh": 0.0, "surplus_kwh": 0.0, "grid_kwh": 0.0, "self_kwh": 0.0}
        for b, la, lo in g:
            ses, ev = evmap[b.id]
            en = ev["energy"][period]
            for k in tot:
                tot[k] += en[k]
            role = "donor" if en["surplus_kwh"] > 1 else "taker" if en["grid_kwh"] > 1 else "neutral"
            lvl = access_level(user, b)
            mem.append({"id": b.id, "name": b.name, "category_short": b.category_short, "lat": la, "lon": lo,
                        "department": department_of(b), "role": role if lvl != PUBLIC else None,
                        "has_ses": ev["has_ses"] if lvl != PUBLIC else None,
                        "k_class": ev["k_class"][period] if lvl != PUBLIC else None,
                        "cons_kwh": round(en["cons_kwh"]),
                        "gen_kwh": round(en["gen_kwh"]) if lvl != PUBLIC else None,
                        "surplus_kwh": round(en["surplus_kwh"]) if lvl != PUBLIC else None,
                        "grid_kwh": round(en["grid_kwh"]) if lvl != PUBLIC else None})
        if not tot["gen_kwh"] and len(mem) < 3:
            continue  # без жодної станції і малих — не показуємо як зону
        anchor = mem[0]
        clat = sum(m["lat"] for m in mem) / len(mem)
        clon = sum(m["lon"] for m in mem) / len(mem)
        kx = 111.32 * math.cos(clat * math.pi / 180)
        rad = max(math.hypot((m["lon"] - clon) * kx, (m["lat"] - clat) * 110.57) for m in mem) + 0.08
        share = min(tot["surplus_kwh"], tot["grid_kwh"])
        k = tot["gen_kwh"] / tot["cons_kwh"] if tot["cons_kwh"] else None
        status = ("surplus" if k and k > eff.HIGH else "balanced" if k and k >= eff.LOW
                  else "deficit" if tot["gen_kwh"] else "no_ses")
        out.append({"id": anchor["id"], "name": anchor["name"], "lat": round(clat, 6), "lon": round(clon, 6),
                    "radius_m": round(rad * 1000), "members": mem, "count": len(mem),
                    "with_ses": sum(1 for b, _, _ in g if evmap[b.id][1]["has_ses"]),
                    "status": status, "k": eff.r2(k),
                    **{k_: round(v) for k_, v in tot.items()},
                    "shareable_kwh": round(share), "shareable_uah": round(share * tariff)})
    out.sort(key=lambda z: -z["shareable_kwh"])
    public = user.role == "public"
    if public:
        for z in out:
            z["status"] = z["k"] = None
            z["gen_kwh"] = z["surplus_kwh"] = z["shareable_kwh"] = z["shareable_uah"] = z["with_ses"] = None
    return {"demo": True, "period": period, "day": d.isoformat(), "radius_m": round(ZONE_RADIUS_KM * 1000),
            "totals": {"zones": len(out), "buildings": sum(z["count"] for z in out),
                       "shareable_kwh": None if public else sum(z["shareable_kwh"] for z in out),
                       "with_share": None if public else sum(1 for z in out if z["shareable_kwh"] > 0)},
            "items": out}


@router.get("/api/trend")
def trend(user: User = Depends(current_user)):
    """2025 (факт) проти оцінки 2026 (з реальних даних до дати вивантаження) по громаді."""
    store, _ = _ctx()
    return calib.city(store)


@router.get("/api/budget-real")
def budget_real_summary(user: User = Depends(current_user)):
    """Реальний бюджет на е/е (КЕКВ 2273) за програмами: план/факт 2025–2026, фактична ціна кВт·год."""
    from . import budget_real
    store, _ = _ctx()
    return budget_real.summary(store)
