"""Ефективність використання СЕС: K = згенеровано ÷ спожито за день / місяць / рік, фінанси й окупність.

ДЕМО: станції — з реєстру sites.py (синтетика або введені дані в data/ses_registry.csv).
Реальні: річне споживання е/е 2025 (UMUNI), генерація 1 кВт за PVGIS.

- День: погодинна модель sites.simulate_day (погода дня, профіль доби категорії, акумулятор).
- Місяць: швидка оцінка «середнього» місяця без погоди: PVGIS місяця × кВт × PV_DERATE (0,92)
  проти споживання 2025 × сезонний профіль категорії (solar.profile_shares).
  Власне споживання місяця = min(генерація, денна частка споживання solar.DAYTIME_SHARE)
  + те, що акумулятор переносить на вечір (не більше доступної ємності щодня).
- Рік: сума 12 таких місяців.
- Класи K: < LOW — «Не вистачає», LOW…HIGH — «Ефективно», > HIGH — «Надлишок».
- Гроші: тариф TARIFF_UAH_KWH (8 грн/кВт·год — ПРИПУЩЕННЯ з solar.py, тариф для непобутових
  споживачів з розподілом; можна передати ?tariff=). Заощаджено = власне споживання × тариф.
  Надлишок не монетизується: бюджетна установа не може продавати е/е (surplus_price = 0 за замовчуванням).
"""

from __future__ import annotations

import calendar
import os
from datetime import date, timedelta

from . import solar
from .sites import BATTERY_RESERVE, PV_DERATE, simulate_day

LOW, HIGH = 0.8, 1.2  # пороги класів K (METHODOLOGY.md)
TARIFF_UAH_KWH = solar.TARIFF_UAH_KWH  # 8 грн/кВт·год — ПРИПУЩЕННЯ, замінити уточненим тарифом
SURPLUS_PRICE_UAH_KWH = 0.0  # надлишок не продається (бюджетна установа) — 0 грн
PAYBACK_PROGRESS_CAP = 999.0

C_OK, C_LOW, C_HIGH, C_NONE, C_NODATA = "Ефективно", "Не вистачає", "Надлишок", "Без СЕС", "Немає даних"
CLASSES = (C_OK, C_LOW, C_HIGH, C_NONE, C_NODATA)
# Обмін надлишком між будівлями поки не працює → клас «Надлишок» вимкнено: K > 1,2 теж «Ефективно».
# Увімкнути, коли з'явиться механізм передачі: SURPLUS_CLASS=1.
SURPLUS_CLASS = os.environ.get("SURPLUS_CLASS", "0") == "1"

NOTES = [
    "K = згенеровано СЕС ÷ спожито об'єктом за період. 0,8 ≤ K ≤ 1,2 — «Ефективно», K < 0,8 — «Не вистачає», "
    "K > 1,2 — «Надлишок».",
    "Станції, акумулятори та їх вартість — ДЕМО-ДАНІ (у місті немає реєстру СЕС), якщо не введені вручну.",
    "Споживання — реальне річне 2025 (UMUNI), розподілене по місяцях сезонним профілем категорії (ПРИПУЩЕННЯ).",
    "Генерація: день — модель з погодою дня; місяць і рік — PVGIS середнього року × 0,92 (втрати, деградація).",
    f"Тариф {TARIFF_UAH_KWH:g} грн/кВт·год — ПРИПУЩЕННЯ (непобутові споживачі з розподілом), можна задати ?tariff=. "
    "Заощаджено = власне споживання сонячної е/е × тариф. Надлишок не монетизується: бюджетна установа не може "
    "його продати (параметр surplus_price, за замовчуванням 0).",
    "Окупність = вкладено ÷ заощаджено за рік; прогрес = заощаджено від запуску ÷ вкладено.",
]


def k_class(k: float | None, has_ses: bool, has_data: bool = True) -> str:
    """Клас за K. Немає споживання → «Немає даних»; немає станції → «Без СЕС»."""
    if not has_data:
        return C_NODATA
    if not has_ses:
        return C_NONE
    if k is None:
        return C_NODATA
    k = round(k, 2)  # клас — за тим самим K, що бачить користувач
    if k < LOW:
        return C_LOW
    if k > HIGH and SURPLUS_CLASS:
        return C_HIGH
    return C_OK


def elec_2025(b) -> float:
    y = b.years.get(2025)
    return float(y.elec_kwh) if y and y.elec_kwh else 0.0


def has_station(ses: dict | None) -> bool:
    return bool(ses and (ses.get("total_kw") or 0) > 0)


def _balance(gen: float, cons: float, self_: float) -> dict:
    return {"gen_kwh": gen, "cons_kwh": cons, "self_kwh": self_,
            "surplus_kwh": max(0.0, gen - self_), "grid_kwh": max(0.0, cons - self_)}


def monthly(b, ses: dict | None, year: int = 2025) -> list[dict]:
    """12 «середніх» місяців: генерація PVGIS × кВт × 0,92, споживання 2025 × профіль, власне споживання."""
    elec = elec_2025(b)
    kw = (ses.get("total_kw") or 0.0) if has_station(ses) else 0.0
    bat = (ses.get("battery_kwh") or 0.0) if ses else 0.0
    e = solar.pvgis_monthly()
    shares = solar.profile_shares(b.category_short)
    out = []
    for m in range(12):
        gen = kw * e[m] * PV_DERATE
        cons = elec * shares[m]
        day = solar.DAYTIME_SHARE * cons
        direct = min(gen, day)
        days = calendar.monthrange(year, m + 1)[1]
        # акумулятор переносить денний надлишок на вечір: не більше робочої ємності (без резерву) щодня
        shifted = min(gen - direct, bat * (1 - BATTERY_RESERVE) * days, cons - day) if bat else 0.0
        out.append({"month": m + 1, **_balance(gen, cons, direct + max(0.0, shifted)),
                    "battery_kwh": max(0.0, shifted)})
    return out


def day_balance(b, ses: dict | None, d: date) -> dict:
    """Доба з погодинної моделі: власне = Σ min(генерація, споживання) погодинно; надлишок і мережа — решта.

    Акумулятор у добовому K не враховуємо (його заряд переходить з доби на добу) — так K і частки
    прозорі: генерація = власне + надлишок, споживання = власне + мережа.
    """
    rows = simulate_day(b, ses if has_station(ses) else None, d)
    gen = sum(r["gen_kwh"] for r in rows)
    cons = sum(r["cons_kwh"] for r in rows)
    self_ = sum(min(r["gen_kwh"], r["cons_kwh"]) for r in rows)
    return _balance(gen, cons, self_)


def _sum(rows: list[dict]) -> dict:
    keys = ("gen_kwh", "cons_kwh", "self_kwh", "surplus_kwh", "grid_kwh")
    return {k: sum(r[k] for r in rows) for k in keys}


def _k(en: dict, has_ses: bool) -> float | None:
    if not has_ses or not en["cons_kwh"]:
        return None
    return en["gen_kwh"] / en["cons_kwh"]


def saved_since(months: list[dict], launched: str | None, d: date, tariff: float, surplus_price: float) -> float:
    """Заощаджено від запуску до дня d: помісячно (середній місяць), неповні місяці — пропорційно дням."""
    if not launched:
        return 0.0
    try:
        cur = date.fromisoformat(launched[:10])
    except ValueError:
        return 0.0
    total = 0.0
    while cur <= d:
        dim = calendar.monthrange(cur.year, cur.month)[1]
        last = min(date(cur.year, cur.month, dim), d)
        m = months[cur.month - 1]
        total += (m["self_kwh"] * tariff + m["surplus_kwh"] * surplus_price) * ((last - cur).days + 1) / dim
        cur = last + timedelta(days=1)
    return total


def evaluate(b, ses: dict | None, d: date, tariff: float = TARIFF_UAH_KWH,
             surplus_price: float = SURPLUS_PRICE_UAH_KWH) -> dict:
    """Повна оцінка об'єкта на день d (сирі числа, без округлення)."""
    has = has_station(ses)
    has_data = elec_2025(b) > 0
    months = monthly(b, ses)
    en = {"day": day_balance(b, ses, d), "month": dict(months[d.month - 1]), "year": _sum(months)}
    en["month"].pop("month", None)
    k = {p: _k(en[p], has) for p in en}
    cls = {p: k_class(k[p], has, has_data) for p in en}
    money = lambda e: e["self_kwh"] * tariff + e["surplus_kwh"] * surplus_price
    costs = (ses or {}).get("costs") if has else None
    invested = (costs or {}).get("total_uah") or None
    saved_year = money(en["year"]) if has else 0.0
    since = saved_since(months, ses.get("launched"), d, tariff, surplus_price) if has else 0.0
    fin = {
        "tariff_uah_kwh": tariff, "surplus_price_uah_kwh": surplus_price,
        "grid_cost_uah": {"month": en["month"]["grid_kwh"] * tariff, "year": en["year"]["grid_kwh"] * tariff},
        "saved_uah": {"month": money(en["month"]) if has else 0.0, "year": saved_year, "since_launch": since},
        "invested_uah": invested,
        "payback_years": invested / saved_year if invested and saved_year > 0 else None,
        "payback_progress_pct": min(PAYBACK_PROGRESS_CAP, 100 * since / invested) if invested else None,
    }
    return {"has_ses": has, "has_data": has_data, "energy": en, "k": k, "k_class": cls,
            "monthly": months, "finance": fin, "costs": costs}


# --- округлення для API ---

def r0(x):
    return None if x is None else round(x)


def r1(x):
    return None if x is None else round(x, 1)


def r2(x):
    return None if x is None else round(x, 2)


def energy_out(en: dict, digits: int) -> dict:
    return {k: (round(v, digits) if digits else round(v)) for k, v in en.items()}


def finance_out(fin: dict) -> dict:
    return {"tariff_uah_kwh": fin["tariff_uah_kwh"], "surplus_price_uah_kwh": fin["surplus_price_uah_kwh"],
            "grid_cost_uah": {k: r0(v) for k, v in fin["grid_cost_uah"].items()},
            "saved_uah": {k: r0(v) for k, v in fin["saved_uah"].items()},
            "invested_uah": r0(fin["invested_uah"]), "payback_years": r1(fin["payback_years"]),
            "payback_progress_pct": r1(fin["payback_progress_pct"])}


def monthly_out(months: list[dict], has_ses: bool) -> list[dict]:
    return [{"month": m["month"], "gen_kwh": round(m["gen_kwh"]), "cons_kwh": round(m["cons_kwh"]),
             "self_kwh": round(m["self_kwh"]), "surplus_kwh": round(m["surplus_kwh"]),
             "grid_kwh": round(m["grid_kwh"]), "k": r2(_k(m, has_ses))} for m in months]
