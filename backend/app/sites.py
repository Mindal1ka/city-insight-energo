"""Об'єкти з сонячними станціями та добова телеметрія — ДЕМО-ДАНІ.

У пакеті міста немає переліку наявних СЕС та даних інверторів, тому:
- реєстр станцій береться з data/ses_registry.csv, якщо команда його заповнила, інакше генерується детерміновано;
- погодинна генерація моделюється за PVGIS (середня місячна генерація 1 кВт для Полтави) + «погода дня»;
- погодинне споживання — з реального річного споживання UMUNI 2025, сезонного профілю та добового профілю категорії.
Реальні: будівлі, адреси, площі, річне споживання 2025/2026 (UMUNI), PVGIS. Усе інше — змодельоване й позначене.
"""

from __future__ import annotations

import calendar
import csv
import math
import random
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import solar

KYIV = timezone(timedelta(hours=2))  # листопад: EET, UTC+2 (спрощення для демо)
BATTERY_RESERVE = 0.3  # 30 % ємності акумулятора тримаємо в резерві на відключення
REGISTRY_FILE = Path(__file__).resolve().parents[1] / "data" / "ses_registry.csv"

# тривалість світлового дня в Полтаві по місяцях, годин (наближено)
DAYLIGHT_H = [8.5, 10.0, 11.8, 13.6, 15.2, 16.0, 15.6, 14.2, 12.4, 10.6, 9.0, 8.1]
SOLAR_NOON = 12.0

# добові профілі споживання (відносні ваги по годинах 0..23)
def _profile(base: float, day: float, start: int, end: int, evening: float = 0.0) -> list[float]:
    p = []
    for h in range(24):
        if start <= h < end:
            v = day
        elif end <= h < end + 3:
            v = max(base, evening)
        else:
            v = base
        p.append(v)
    return p

DAY_PROFILES = {
    "Заклади освіти": _profile(0.18, 1.0, 8, 16, 0.45),
    "Дошкільні заклади": _profile(0.25, 1.0, 7, 18, 0.35),
    "Охорона здоров'я": _profile(0.65, 1.0, 7, 20, 0.85),
    "Громадські будівлі": _profile(0.2, 1.0, 9, 18, 0.3),
    "Спортивні споруди": _profile(0.2, 0.9, 8, 21, 0.5),
    "Житлові будинки": _profile(0.4, 0.8, 7, 22, 1.0),
}
WEEKEND_FACTOR = {"Заклади освіти": 0.35, "Дошкільні заклади": 0.35, "Громадські будівлі": 0.45,
                  "Спортивні споруди": 0.8, "Охорона здоров'я": 0.95, "Житлові будинки": 1.0}

INVERTERS = [("Deye SUN-10K-SG04LP3", 10), ("Deye SUN-12K-SG04LP3", 12), ("Deye SUN-20K-SG01HP3", 20),
             ("Deye SUN-30K-SG01HP3", 30), ("Deye SUN-50K-SG01HP3", 50), ("Growatt MOD 15KTL3-XH", 15),
             ("LuxPower LXP-LB-EU 12K", 12)]
SES_CATEGORIES = {"Заклади освіти", "Дошкільні заклади", "Охорона здоров'я", "Громадські будівлі"}


def city_of(address: str) -> str:
    m = re.search(r"\bс(?:ело)?\.\s*([А-ЯІЇЄҐ][\w'’\-]+)", address)
    return m.group(1) if m else "Полтава"


def _f(v, default=None):
    try:
        return float(str(v).replace(",", ".")) if str(v).strip() != "" else default
    except ValueError:
        return default


def load_registry(buildings) -> dict[int, dict]:
    """Реєстр СЕС: CSV команди (якщо є) або детермінована генерація."""
    reg: dict[int, dict] = {}
    if REGISTRY_FILE.exists():
        with REGISTRY_FILE.open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                bid = int(_f(r.get("building_id"), 0) or 0)
                if not bid:
                    continue
                n, w = int(_f(r.get("панелей_шт"), 0) or 0), _f(r.get("потужність_панелі_Вт"), 450)
                reg[bid] = {
                    "panels_count": n, "panel_w": w, "total_kw": round(n * w / 1000, 1),
                    "inverter_model": r.get("інвертор_модель") or "—", "inverter_kw": _f(r.get("інвертор_кВт"), 0),
                    "battery_kwh": _f(r.get("акумулятор_кВт·год"), 0), "battery_kw": _f(r.get("акумулятор_кВт"), 0),
                    "connected_kw": _f(r.get("приєднана_потужність_кВт"), 0),
                    "launched": (r.get("дата_запуску") or "2024-06-01")[:10], "source": r.get("джерело") or "CSV",
                }
        if reg:
            return reg

    for b in buildings:
        y = b.years.get(2025)
        if b.category_short not in SES_CATEGORIES or not y or not y.elec_kwh or y.elec_kwh < 15000:
            continue
        rng = random.Random(f"ses-{b.id}")
        if rng.random() > 0.3:  # приблизно третина великих споживачів має станцію
            continue
        model, inv_kw = min(INVERTERS, key=lambda m: abs(m[1] - max(8.0, y.elec_kwh / 6000)))
        panel_w = rng.choice([410, 450, 550, 590])
        total_kw = inv_kw * rng.uniform(1.0, 1.25)
        n = max(10, round(total_kw * 1000 / panel_w))
        bat_kwh = rng.choice([10.0, 15.36, 20.48, 30.72, 40.96]) if inv_kw <= 20 else rng.choice([40.96, 61.44, 81.92])
        bat_kw = min(bat_kwh / 2, inv_kw)
        connected = rng.choice([30, 50, 75, 100, 150, 200])
        if rng.random() < 0.1:  # кілька станцій навмисно з порушенням «акумулятор > приєднаної потужності»
            connected = max(5, round(bat_kw * 0.8))
        start = date(2023, 3, 1) + timedelta(days=rng.randint(0, 900))
        reg[b.id] = {"panels_count": n, "panel_w": panel_w, "total_kw": round(n * panel_w / 1000, 1),
                     "inverter_model": model, "inverter_kw": inv_kw, "battery_kwh": bat_kwh,
                     "battery_kw": round(bat_kw, 1), "connected_kw": connected,
                     "launched": start.isoformat(), "source": "ДЕМО"}
    return reg


def _weather(d: date) -> float:
    """Спільна для міста «хмарність дня»: 0,3 — похмуро, 1,15 — ясно."""
    return random.Random(f"weather-{d.isoformat()}").uniform(0.3, 1.15)


def _solar_shape(month: int) -> list[float]:
    dl = DAYLIGHT_H[month - 1]
    rise, set_ = SOLAR_NOON - dl / 2, SOLAR_NOON + dl / 2
    w = []
    for h in range(24):
        t = h + 0.5
        w.append(math.sin(math.pi * (t - rise) / dl) ** 1.3 if rise < t < set_ else 0.0)
    s = sum(w) or 1
    return [x / s for x in w]


def daily_consumption(b, d: date) -> float:
    y = b.years.get(2025)
    if not y or not y.elec_kwh:
        return 0.0
    share = solar.profile_shares(b.category_short)[d.month - 1]
    days = calendar.monthrange(d.year, d.month)[1]
    wk = WEEKEND_FACTOR.get(b.category_short, 0.6) if d.weekday() >= 5 else 1.0
    noise = random.Random(f"cons-{b.id}-{d.isoformat()}").uniform(0.9, 1.1)
    return y.elec_kwh * share / days * wk * noise


def simulate_day(b, ses: dict | None, d: date) -> list[dict]:
    """Погодинний баланс доби: генерація → навантаження → акумулятор → мережа / надлишок."""
    prof = DAY_PROFILES.get(b.category_short, _profile(0.3, 1.0, 8, 18))
    ps = sum(prof)
    cons_day = daily_consumption(b, d)
    cons = [cons_day * p / ps for p in prof]
    gen = [0.0] * 24
    bat_kwh = soc = 0.0
    if ses:
        days = calendar.monthrange(d.year, d.month)[1]
        e_day = solar.pvgis_monthly()[d.month - 1] / days * ses["total_kw"]
        e_day *= _weather(d) * random.Random(f"gen-{b.id}-{d}").uniform(0.92, 1.05)
        gen = [e_day * s for s in _solar_shape(d.month)]
        bat_kwh = ses["battery_kwh"] or 0.0
        soc = random.Random(f"soc-{b.id}-{d}").uniform(0.45, 0.85) * bat_kwh
    rows = []
    for h in range(24):
        g, c = gen[h], cons[h]
        self_use = min(g, c)
        net = g - c
        to_bat = from_bat = surplus = 0.0
        p = ses["battery_kw"] if ses else 0.0
        if net > 0 and bat_kwh:
            to_bat = min(net, p, bat_kwh - soc)
            soc += to_bat
            surplus = net - to_bat
        elif net > 0:
            surplus = net
        elif bat_kwh and h >= 16:  # вечірній пік — розряд до резерву
            from_bat = min(-net, p, max(0.0, soc - BATTERY_RESERVE * bat_kwh))
            soc -= from_bat
        grid = max(0.0, c - self_use - from_bat)
        rows.append({"hour": h, "gen_kwh": g, "cons_kwh": c, "self_kwh": self_use, "to_battery_kwh": to_bat,
                     "from_battery_kwh": from_bat, "from_grid_kwh": grid, "surplus_kwh": surplus,
                     "soc_kwh": soc, "soc_pct": round(100 * soc / bat_kwh, 1) if bat_kwh else None})
    return rows


def _r(x, n=1):
    return None if x is None else round(x, n)


class Sites:
    def __init__(self, store):
        self.store = store
        self.reload()

    def reload(self):
        self.registry = load_registry(self.store.buildings)

    def _now(self) -> datetime:
        return datetime.now(KYIV)

    def detail(self, b, now: datetime | None = None) -> dict:
        now = now or self._now()
        d, hnow = now.date(), now.hour
        ses = self.registry.get(b.id)
        rows = simulate_day(b, ses, d)
        past = rows[:hnow]
        fut = rows[hnow:]
        sm = lambda rr, k: sum(r[k] for r in rr)
        peak = max(rows, key=lambda r: r["cons_kwh"])
        y25 = b.years.get(2025)
        y26 = b.years.get(2026)
        tariff = solar.TARIFF_UAH_KWH

        # ліміти (ДЕМО): місячний грошовий — прогноз місяця × тариф × 1,05; добовий — середня доба × 1,1
        days_in_month = calendar.monthrange(d.year, d.month)[1]
        month_cons = sum(daily_consumption(b, d.replace(day=i)) for i in range(1, days_in_month + 1))
        mtd = sum(daily_consumption(b, d.replace(day=i)) for i in range(1, d.day)) + sm(past, "cons_kwh")
        mtd_grid = mtd - (sum(sm(simulate_day(b, ses, d.replace(day=i)), "self_kwh") for i in range(1, d.day))
                          + sm(past, "self_kwh") if ses else 0)
        money_limit = round(month_cons * tariff * 1.05, -2)
        money_used = mtd_grid * tariff
        day_limit = round(month_cons / days_in_month * 1.1)
        day_used = sm(past, "cons_kwh")

        period = {"since": None, "days": 0, "generated_kwh": None, "saved_uah": None,
                  "consumed_kwh": round((y25.elec_kwh or 0) + ((y26.elec_kwh or 0) if y26 else 0)) if y25 else None,
                  "consumed_since": "2025-01-01"}
        if ses:
            start = date.fromisoformat(ses["launched"])
            gen_total = 0.0
            cur = start
            while cur <= d:  # помісячно за PVGIS × 0,92 (втрати й деградація)
                dim = calendar.monthrange(cur.year, cur.month)[1]
                last = min(date(cur.year, cur.month, dim), d)
                gen_total += solar.pvgis_monthly()[cur.month - 1] * ses["total_kw"] * 0.92 * ((last - cur).days + 1) / dim
                cur = last + timedelta(days=1)
            period.update(since=ses["launched"], days=(d - start).days, generated_kwh=round(gen_total),
                          saved_uah=round(gen_total * 0.9 * tariff))

        dist = {"peak_kw": _r(peak["cons_kwh"]), "peak_hour": peak["hour"],
                "need_kwh_rest_of_day": _r(sm(fut, "cons_kwh")),
                "battery_kwh_now": None, "battery_soc_pct": None, "solar_kw_now": None, "solar_kwh_rest_of_day": None}
        available = 0.0
        if ses:
            soc_now = past[-1]["soc_kwh"] if past else rows[0]["soc_kwh"]
            usable = max(0.0, soc_now - BATTERY_RESERVE * ses["battery_kwh"])
            dist.update(battery_kwh_now=_r(soc_now), battery_soc_pct=_r(100 * soc_now / ses["battery_kwh"]) if ses["battery_kwh"] else None,
                        solar_kw_now=_r(rows[hnow]["gen_kwh"], 2), solar_kwh_rest_of_day=_r(sm(fut, "gen_kwh")))
            available = usable + sm(fut, "gen_kwh")
        balance = available - sm(fut, "cons_kwh")
        dist.update(available_kwh=_r(available), balance_kwh=_r(balance), enough=balance >= 0,
                    reserve_to_grid_kwh=_r(sm(rows, "surplus_kwh")))

        out_ses = None
        if ses:
            out_ses = {k: ses[k] for k in ("panels_count", "panel_w", "total_kw", "inverter_model", "inverter_kw",
                                           "battery_kwh", "battery_kw", "connected_kw", "launched")}
            out_ses["battery_within_connected"] = (ses["battery_kw"] or 0) <= (ses["connected_kw"] or 0)
            out_ses["source"] = ses.get("source", "ДЕМО")

        notes = ["Будівля, адреса, площа та річне споживання 2025–2026 — реальні дані UMUNI."]
        if ses:
            notes.append("Параметри станції, генерація, заряд акумулятора й ліміти — ДЕМО-ДАНІ (змодельовано за PVGIS і профілями споживання).")
        if not y25 or not y25.elec_kwh:
            notes.append("У UMUNI немає даних про електроенергію цієї будівлі за 2025 рік.")

        return {
            "demo": True, "now": now.isoformat(timespec="minutes"),
            "building": {"id": b.id, "name": b.name, "address": b.address, "city": city_of(b.address),
                         "category_short": b.category_short, "heated_area": b.heated_area, "floors": b.floors,
                         "elec_kwh_2025": round(y25.elec_kwh) if y25 and y25.elec_kwh else None},
            "ses": out_ses,
            "today": {"date": d.isoformat(), "generated_kwh": _r(sm(past, "gen_kwh")), "consumed_kwh": _r(sm(past, "cons_kwh")),
                      "self_kwh": _r(sm(past, "self_kwh")), "from_grid_kwh": _r(sm(past, "from_grid_kwh")),
                      "to_battery_kwh": _r(sm(past, "to_battery_kwh")), "surplus_kwh": _r(sm(past, "surplus_kwh")),
                      "peak_kw": _r(peak["cons_kwh"]), "peak_hour": peak["hour"]},
            "period": period,
            "limits": {"tariff_uah_kwh": tariff, "money_month_uah": money_limit, "money_month_used_uah": round(money_used),
                       "money_month_pct": _r(100 * money_used / money_limit) if money_limit else None,
                       "energy_day_kwh": day_limit, "energy_day_used_kwh": _r(day_used),
                       "energy_day_pct": _r(100 * day_used / day_limit) if day_limit else None,
                       "over_money": bool(money_limit and money_used > money_limit),
                       "over_day": bool(day_limit and day_used > day_limit)},
            "distribution": dist,
            "hourly": [{"hour": r["hour"], "gen_kwh": _r(r["gen_kwh"], 2), "cons_kwh": _r(r["cons_kwh"], 2),
                        "soc_pct": r["soc_pct"], "forecast": r["hour"] >= hnow} for r in rows],
            "notes": notes,
        }

    def listing(self, now: datetime | None = None) -> dict:
        now = now or self._now()
        items, gen_t, cons_t, surplus_t = [], 0.0, 0.0, 0.0
        n_def = n_sur = 0
        for b in sorted(self.store.buildings, key=lambda x: x.name):
            det = self.detail(b, now)
            has = det["ses"] is not None
            dist = det["distribution"]
            status = "no_ses"
            if has:
                status = "surplus" if dist["enough"] else "deficit"
                n_sur += status == "surplus"
                n_def += status == "deficit"
                gen_t += det["today"]["generated_kwh"] or 0
                surplus_t += dist["reserve_to_grid_kwh"] or 0
            cons_t += det["today"]["consumed_kwh"] or 0
            items.append({"id": b.id, "name": b.name, "address": b.address, "city": det["building"]["city"],
                          "category_short": b.category_short, "has_ses": has,
                          "ses_kw": det["ses"]["total_kw"] if has else None, "status": status,
                          "balance_kwh_today": dist["balance_kwh"] if has else None,
                          "generated_today_kwh": det["today"]["generated_kwh"] if has else None})
        return {"demo": True, "now": now.isoformat(timespec="minutes"),
                "totals": {"sites": len(items), "with_ses": sum(i["has_ses"] for i in items),
                           "generated_today_kwh": round(gen_t, 1), "consumed_today_kwh": round(cons_t, 1),
                           "surplus_today_kwh": round(surplus_t, 1), "deficit_sites": n_def, "surplus_sites": n_sur},
                "items": items}
