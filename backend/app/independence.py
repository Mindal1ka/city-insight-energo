"""Енергонезалежність будівель: частка власного сонця, автономність на акумуляторі, індекс 0–100.

ДЕМО: станції, акумулятори, погода дня та заряд — змодельовані (реєстр sites.py + акумулятори без СЕС нижче).
Реальні: перелік будівель, категорії, площі, річне споживання електроенергії 2025 (UMUNI), PVGIS.
Даних про реальні генератори чи резервне живлення закладів тут немає й не буде (вимога безпеки треку).

Як рахується (усе «на папері»):
  1. Частка власного сонця за рік (self_sufficiency_pct) = сонячна енергія, спожита самою будівлею ÷ електроенергія 2025.
     Помісячно: генерація = PVGIS 1 кВт × потужність станції; споживання = річне × сезонний профіль категорії;
     удень будівля може спожити solar.DAYTIME_SHARE місячного споживання; надлишок дня акумулятор переносить
     на вечір/ніч, але не більше «ємність × днів у місяці» і не більше нічного споживання. Решта надлишку пропадає
     (продавати його комунальні заклади зараз не можуть).
  2. Автономність (autonomy_hours) = корисна ємність акумулятора ÷ середнє навантаження в робочі години (кВт).
     Під час відключення резерв sites.BATTERY_RESERVE теж витрачається: розряджаємо до OUTAGE_SOC_FLOOR (10 %).
     Вважаємо, що перед відключенням акумулятор заряджений повністю. Без сонця — найгірший випадок.
  3. Автономність із сонцем (autonomy_hours_with_sun) — погодинна симуляція від обраного моменту:
     навантаження за добовим профілем категорії + сонце того дня (погода дня з sites.py), надлишок сонця
     дозаряджає акумулятор. Горизонт — AUTONOMY_HORIZON_H годин (якщо вистачає на весь — повертаємо горизонт).
  4. Індекс 0–100 = W_SELF × min(частка, SELF_CAP_PCT)/SELF_CAP_PCT + W_AUTONOMY × min(автономність, AUTONOMY_CAP_H)/AUTONOMY_CAP_H.
"""

from __future__ import annotations

import calendar
import math
import random
import statistics
from datetime import date, datetime, timedelta

from . import solar
from .sites import DAY_PROFILES, WEEKEND_FACTOR, _profile, simulate_day

# --- Індекс енергостійкості (ПРИПУЩЕННЯ, пояснюється користувачу у formula) ---
W_SELF = 50.0  # вага частки власного сонця, балів
W_AUTONOMY = 50.0  # вага автономності, балів
SELF_CAP_PCT = 40.0  # 40 % власного сонця = максимум балів (реально сонце покриває до ~30 %, за словами енергоменеджера)
AUTONOMY_CAP_H = 8.0  # 8 год на акумуляторі = максимум балів (типове планове відключення 4 год × 2)
CLASS_BOUNDS = [(70, "висока"), (40, "середня"), (1, "низька")]  # 0 — «відсутня»

# --- Акумулятор у відключення ---
OUTAGE_SOC_FLOOR = 0.10  # у відключення розряджаємо до 10 % (захист LiFePO4), а не до резерву 30 %
AUTONOMY_HORIZON_H = 48  # горизонт симуляції «з сонцем», год
BATTERY_C_RATE = 0.5  # потужність нового акумулятора = 0,5 × ємність (кВт на кВт·год)
BATTERY_MODULE_KWH = 5.12  # типовий модуль LiFePO4 48 В 100 А·год
BATTERY_UAH_PER_KWH = 16000.0  # ПРИПУЩЕННЯ — замінити: акумулятор + частка гібридного інвертора, грн за кВт·год

# --- Пріоритет критичних об'єктів (інтерв'ю: охорона здоров'я → освіта → інші) ---
CRITICAL_CATEGORIES = {"Охорона здоров'я"}
PRIORITY = {"Охорона здоров'я": 1, "Заклади освіти": 2, "Дошкільні заклади": 2}  # решта — 3
TARGET_AUTONOMY_H = {1: 8.0, 2: 4.0, 3: 4.0}  # цільова автономність для рекомендації акумулятора, год

# --- ДЕМО: інвертори з акумулятором БЕЗ сонячної станції (школи заряджаються від мережі, коли є світло) ---
BATTERY_ONLY_CATEGORIES = {"Заклади освіти", "Дошкільні заклади"}
BATTERY_ONLY_SHARE = 0.2  # приблизно кожен п'ятий заклад освіти без СЕС
BATTERY_ONLY_MIN_KWH_YEAR = 10000.0

BASE_YEAR = 2025


def _r(x, n=1):
    return None if x is None else round(x, n)


def _uah(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _num(x: float, n: int = 1) -> str:
    """Число українською: кома як десятковий роздільник, без зайвих нулів."""
    s = f"{x:.{n}f}".rstrip("0").rstrip(".") if n else f"{x:.0f}"
    return s.replace(".", ",")


def priority_of(category_short: str | None) -> int:
    return PRIORITY.get(category_short or "", 3)


def elec_2025(b) -> float | None:
    y = b.years.get(BASE_YEAR)
    return y.elec_kwh if y and y.elec_kwh and y.elec_kwh > 0 else None


def battery_only_registry(buildings, ses_registry: dict) -> dict[int, dict]:
    """ДЕМО: акумулятори без СЕС (детерміновано, щоб цифри не стрибали між запитами)."""
    reg = {}
    for b in buildings:
        e = elec_2025(b)
        if b.id in ses_registry or b.category_short not in BATTERY_ONLY_CATEGORIES or not e or e < BATTERY_ONLY_MIN_KWH_YEAR:
            continue
        rng = random.Random(f"batonly-{b.id}")
        if rng.random() > BATTERY_ONLY_SHARE:
            continue
        kwh = rng.choice([10.24, 15.36, 20.48])
        reg[b.id] = {"total_kw": 0.0, "battery_kwh": kwh, "battery_kw": round(kwh * BATTERY_C_RATE, 1),
                     "connected_kw": None, "source": "ДЕМО", "battery_only": True}
    return reg


def load_profile(category_short: str | None) -> list[float]:
    return DAY_PROFILES.get(category_short or "", _profile(0.3, 1.0, 8, 18))


def hourly_load(b, d: date) -> list[float]:
    """Погодинне навантаження доби, кВт·год (середня доба місяця, без випадкового шуму; вихідні — менше)."""
    e = elec_2025(b)
    if not e:
        return [0.0] * 24
    days = calendar.monthrange(d.year, d.month)[1]
    day_kwh = e * solar.profile_shares(b.category_short)[d.month - 1] / days
    if d.weekday() >= 5:
        day_kwh *= WEEKEND_FACTOR.get(b.category_short, 0.6)
    p = load_profile(b.category_short)
    ps = sum(p)
    return [day_kwh * w / ps for w in p]


def work_load_kw(b, month: int, year: int) -> float | None:
    """Середнє навантаження в робочі (найнавантаженіші) години буднього дня місяця, кВт."""
    e = elec_2025(b)
    if not e:
        return None
    days = calendar.monthrange(year, month)[1]
    day_kwh = e * solar.profile_shares(b.category_short)[month - 1] / days
    p = load_profile(b.category_short)
    return day_kwh * max(p) / sum(p)


def annual_self(elec: float, category_short: str | None, kw: float, battery_kwh: float) -> dict:
    """Річна частка власного сонця для станції kw (кВт) з акумулятором battery_kwh (помісячно, PVGIS)."""
    e = solar.pvgis_monthly()
    cons = [elec * s for s in solar.profile_shares(category_short)]
    gen_y = self_y = surplus_y = 0.0
    for m in range(12):
        gen = kw * e[m]
        day = solar.DAYTIME_SHARE * cons[m]
        direct = min(gen, day)
        surplus = gen - direct
        days = calendar.monthrange(2025, m + 1)[1]
        shifted = min(surplus, battery_kwh * (1 - OUTAGE_SOC_FLOOR) * days, cons[m] - day)
        gen_y += gen
        self_y += direct + shifted
        surplus_y += surplus - shifted
    return {"gen_kwh": gen_y, "self_kwh": self_y, "lost_kwh": surplus_y,
            "pct": 100 * self_y / elec if elec else 0.0}


def usable_kwh(battery_kwh: float) -> float:
    return battery_kwh * (1 - OUTAGE_SOC_FLOOR)


def autonomy_with_sun(b, station: dict, now: datetime) -> tuple[float, bool]:
    """Погодинно від now: акумулятор (повний) + сонце дня. Повертає (години, чи вистачило на весь горизонт)."""
    cap = station["battery_kwh"] or 0.0
    if cap <= 0:
        return 0.0, False
    floor = cap * OUTAGE_SOC_FLOOR
    soc = cap
    hours = 0.0
    d, h = now.date(), now.hour
    cache: dict[date, tuple[list[float], list[float]]] = {}
    for _ in range(AUTONOMY_HORIZON_H):
        if d not in cache:
            load = hourly_load(b, d)
            gen = ([r["gen_kwh"] for r in simulate_day(b, station, d)] if station.get("total_kw") else [0.0] * 24)
            cache[d] = (load, gen)
        load, gen = cache[d]
        need = load[h] - gen[h]
        if need <= 0:
            soc = min(cap, soc - need)
            hours += 1
        elif soc - floor >= need:
            soc -= need
            hours += 1
        else:
            hours += (soc - floor) / need
            return hours, False
        h += 1
        if h == 24:
            h, d = 0, d + timedelta(days=1)
    return float(AUTONOMY_HORIZON_H), True


def index_of(self_pct: float, autonomy_h: float) -> float:
    return (W_SELF * min(self_pct, SELF_CAP_PCT) / SELF_CAP_PCT
            + W_AUTONOMY * min(autonomy_h, AUTONOMY_CAP_H) / AUTONOMY_CAP_H)


def class_of(index: int, has_assets: bool) -> str:
    if not has_assets and index == 0:
        return "відсутня"
    for bound, name in CLASS_BOUNDS:
        if index >= bound:
            return name
    return "низька"


def formula() -> dict:
    return {
        "text": (f"Індекс енергостійкості = {W_SELF:g} × min(частка власного сонця; {SELF_CAP_PCT:g} %) ÷ {SELF_CAP_PCT:g} % + "
                 f"{W_AUTONOMY:g} × min(автономність на акумуляторі; {AUTONOMY_CAP_H:g} год) ÷ {AUTONOMY_CAP_H:g} год. "
                 f"Клас: висока ≥ 70, середня 40–69, низька 1–39, відсутня — 0 (немає ні СЕС, ні акумулятора). "
                 f"Автономність = ємність акумулятора × {1 - OUTAGE_SOC_FLOOR:.0%} (розряд до {OUTAGE_SOC_FLOOR:.0%}) ÷ "
                 f"середнє навантаження в робочі години поточного місяця, без сонця."),
        "weights": {"self_sufficiency": W_SELF / 100, "autonomy": W_AUTONOMY / 100,
                    "self_sufficiency_cap_pct": SELF_CAP_PCT, "autonomy_cap_h": AUTONOMY_CAP_H,
                    "outage_soc_floor": OUTAGE_SOC_FLOOR, "daytime_share": solar.DAYTIME_SHARE,
                    "horizon_h": AUTONOMY_HORIZON_H},
    }


def _potential_exclusion(b) -> str | None:
    from .solar_api import _exclusion  # та сама логіка відбору, що й на екрані «Де ставити нові СЕС»

    return _exclusion(b)


def evaluate(b, station: dict | None, now: datetime) -> dict:
    """Усі показники однієї будівлі. Повертає item (контракт API) + службові поля з префіксом «_»."""
    elec = elec_2025(b)
    pr = priority_of(b.category_short)
    has_ses = bool(station and station.get("total_kw"))
    bat = (station or {}).get("battery_kwh") or 0.0
    ses_kw = station["total_kw"] if has_ses else 0.0
    item = {"id": b.id, "name": b.name, "address": b.address, "category_short": b.category_short,
            "critical": b.category_short in CRITICAL_CATEGORIES, "priority_rank": pr,
            "has_ses": has_ses, "ses_kw": ses_kw if has_ses else None,
            "has_battery": bat > 0, "battery_kwh": bat if bat > 0 else None,
            "battery_kw": (station or {}).get("battery_kw") if bat > 0 else None,
            "connected_kw": (station or {}).get("connected_kw"),
            "elec_kwh_year": round(elec) if elec else None,
            "self_sufficiency_pct": 0.0, "solar_kwh_year": None, "solar_self_kwh_year": None,
            "autonomy_hours": None, "autonomy_hours_with_sun": None, "autonomy_with_sun_capped": False,
            "work_load_kw": None, "index": 0, "index_class": "відсутня",
            "potential_kw": None, "potential_add_kw": None, "potential_self_sufficiency_pct": None,
            "potential_cost_uah": None, "potential_payback_years": None,
            "data_ok": elec is not None, "demo_assets": bool(station)}
    calc = {"elec": elec, "annual": None, "pot": None, "pot_reason": None}
    if not elec:
        item["index_class"] = class_of(0, bool(station))
        return {**item, "_calc": calc}

    ann = annual_self(elec, b.category_short, ses_kw, bat)
    calc["annual"] = ann
    item["self_sufficiency_pct"] = round(ann["pct"], 1)
    if has_ses:
        item["solar_kwh_year"] = round(ann["gen_kwh"])
        item["solar_self_kwh_year"] = round(ann["self_kwh"])
    p_work = work_load_kw(b, now.month, now.year)
    item["work_load_kw"] = _r(p_work)
    aut = 0.0
    if bat > 0 and p_work:
        aut = usable_kwh(bat) / p_work
        sun, capped = autonomy_with_sun(b, station, now)
        item["autonomy_hours_with_sun"] = round(max(sun, aut), 1)
        item["autonomy_with_sun_capped"] = capped
    elif p_work:
        item["autonomy_hours_with_sun"] = 0.0
    item["autonomy_hours"] = round(aut, 1)
    idx = index_of(ann["pct"], aut)
    item["index"] = max(1, round(idx)) if (has_ses or bat > 0) else round(idx)
    item["index_class"] = class_of(item["index"], has_ses or bat > 0)

    # потенціал: рекомендована станція «під власне споживання» (solar.estimate) поверх наявної
    reason = _potential_exclusion(b)
    calc["pot_reason"] = reason
    if not reason:
        r = solar.estimate(elec, b.heated_area, b.floors, b.category_short)
        rec = r.kw_recommended
        add = max(0.0, rec - ses_kw)
        if add < solar.MIN_KW:
            add = 0.0
        new = annual_self(elec, b.category_short, ses_kw + add, bat)
        cost = solar.CAPEX_FIXED_UAH + add * solar.CAPEX_UAH_PER_KW if add > 0 else 0.0
        extra = (new["self_kwh"] - ann["self_kwh"]) * solar.TARIFF_UAH_KWH
        item.update(potential_kw=round(rec, 1), potential_add_kw=round(add, 1),
                    potential_self_sufficiency_pct=round(new["pct"], 1), potential_cost_uah=round(cost),
                    potential_payback_years=round(cost / extra, 1) if add > 0 and extra > 0 else None)
        calc["pot"] = {"rec": rec, "add": add, "new": new, "cost": cost, "limited_by": r.limited_by,
                       "kw_max_roof": r.kw_max_roof}
    return {**item, "_calc": calc}


def public(ev: dict) -> dict:
    return {k: v for k, v in ev.items() if not k.startswith("_")}


# ---------------- пояснення й рекомендації ----------------

def _battery_offer(ev: dict) -> dict | None:
    p_work = ev["work_load_kw"]
    if not p_work:
        return None
    target = TARGET_AUTONOMY_H[ev["priority_rank"]]
    cur = ev["autonomy_hours"] or 0.0
    if cur >= target:
        return None
    have = ev["battery_kwh"] or 0.0
    need_total = p_work * target / (1 - OUTAGE_SOC_FLOOR)
    add = math.ceil(max(0.0, need_total - have) / BATTERY_MODULE_KWH) * BATTERY_MODULE_KWH
    if add <= 0:
        return None
    total = have + add
    bat_kw = total * BATTERY_C_RATE
    conn = ev["connected_kw"]
    limited = bool(conn and bat_kw > conn)
    if limited:
        bat_kw = float(conn)
    new_h = usable_kwh(total) / p_work
    return {"add_kwh": round(add, 2), "total_kwh": round(total, 2), "battery_kw": round(bat_kw, 1),
            "limited_by_connected": limited, "new_hours": new_h, "cost": add * BATTERY_UAH_PER_KWH, "target": target}


def improve(ev: dict) -> list[dict]:
    out: list[dict] = []
    calc = ev["_calc"]
    if not ev["data_ok"]:
        out.append({"action": "Внести споживання електроенергії за 2025 рік в UMUNI",
                    "effect": "Без річного споживання не можна оцінити ні частку сонця, ні автономність, ні потрібну станцію.",
                    "kw": None, "battery_kwh": None, "cost_uah": None, "payback_years": None, "priority": "висока"})
        return out

    # 1) невідповідність наявного акумулятора приєднаній потужності (правило з інтерв'ю)
    if ev["battery_kw"] and ev["connected_kw"] and ev["battery_kw"] > ev["connected_kw"]:
        out.append({"action": f"Обмежити потужність акумулятора до {_num(ev['connected_kw'])} кВт",
                    "effect": (f"Зараз {_num(ev['battery_kw'])} кВт перевищує приєднану потужність "
                               f"{_num(ev['connected_kw'])} кВт — так не можна (ДЕМО-дані реєстру)."),
                    "kw": None, "battery_kwh": None, "cost_uah": None, "payback_years": None, "priority": "висока"})

    # 2) акумулятор — автономність у відключення (критичні — найвищий пріоритет)
    bo = _battery_offer(ev)
    if bo:
        tag = {1: " (критичний заклад)", 2: " (заклад освіти)"}.get(ev["priority_rank"], "")
        lim = (f" Потужність акумулятора обмежено приєднаною потужністю {_num(ev['connected_kw'])} кВт."
               if bo["limited_by_connected"] else
               ("" if ev["connected_kw"] else
                f" Перевірити приєднану потужність: потужність акумулятора ({_num(bo['battery_kw'])} кВт) не може її перевищувати."))
        out.append({"action": f"Додати акумулятор {_num(bo['add_kwh'])} кВт·год",
                    "effect": (f"Автономність {_num(ev['autonomy_hours'] or 0)} → {_num(bo['new_hours'])} год{tag}, "
                               f"орієнтовно {_uah(bo['cost'])} грн.{lim}"),
                    "kw": bo["battery_kw"], "battery_kwh": bo["add_kwh"], "cost_uah": round(bo["cost"]),
                    "payback_years": None,
                    "priority": {1: "висока", 2: "середня"}.get(ev["priority_rank"], "низька")})

    # 3) сонячна станція «під власне споживання»
    pot = calc["pot"]
    if pot and pot["add"] > 0:
        pb = ev["potential_payback_years"]
        verb = "Розширити СЕС на" if ev["has_ses"] else "Додати"
        out.append({"action": f"{verb} {_num(pot['add'])} кВт СЕС",
                    "effect": (f"Енергонезалежність {_num(ev['self_sufficiency_pct'])} % → "
                               f"{_num(ev['potential_self_sufficiency_pct'])} %"
                               + (f", окупність {_num(pb)} року" if pb is not None else "")
                               + f", вартість ≈ {_uah(pot['cost'])} грн."),
                    "kw": round(pot["add"], 1), "battery_kwh": None, "cost_uah": round(pot["cost"]),
                    "payback_years": pb,
                    "priority": "висока" if pb is not None and pb <= 6 else ("середня" if pb is not None and pb <= 10 else "низька")})

    # 4) втрачений надлишок наявної станції
    ann = calc["annual"]
    if ev["has_ses"] and ann and ann["lost_kwh"] > 0.05 * ann["gen_kwh"]:
        out.append({"action": "Перенести енергоємні роботи на сонячні години",
                    "effect": (f"≈ {_uah(ann['lost_kwh'])} кВт·год сонця на рік не використовується "
                               f"(переважно влітку), продати надлишок заклад не може."),
                    "kw": None, "battery_kwh": None, "cost_uah": None, "payback_years": None, "priority": "низька"})

    if not out:
        out.append({"action": "Підтримувати поточний рівень",
                    "effect": "Перед графіками відключень перевіряти заряд акумулятора; раз на рік — стан панелей.",
                    "kw": None, "battery_kwh": None, "cost_uah": None, "payback_years": None, "priority": "низька"})
    order = {"висока": 0, "середня": 1, "низька": 2}
    out.sort(key=lambda x: order[x["priority"]])
    return out[:4]


def explain(ev: dict, now: datetime) -> list[str]:
    calc = ev["_calc"]
    lines = []
    if not ev["data_ok"]:
        lines.append("У UMUNI немає споживання електроенергії цієї будівлі за 2025 рік — індекс 0, показники не розраховуються.")
        lines.append("Будівля лишається у списку, щоб її не загубити: спершу треба доповнити дані.")
        return lines
    lines.append(f"Споживання електроенергії 2025: {_uah(ev['elec_kwh_year'])} кВт·год (реальні дані UMUNI).")
    if ev["has_ses"]:
        ann = calc["annual"]
        lines.append(f"Станція {_num(ev['ses_kw'])} кВт (ДЕМО) за PVGIS дає ≈ {_uah(ann['gen_kwh'])} кВт·год на рік; "
                     f"будівля сама використовує ≈ {_uah(ann['self_kwh'])} кВт·год → частка власного сонця "
                     f"{_num(ev['self_sufficiency_pct'])} %.")
        lines.append(f"Удень будівля споживає {solar.DAYTIME_SHARE:.0%} електроенергії; надлишок понад це "
                     f"акумулятор переносить на вечір, решта ({_uah(ann['lost_kwh'])} кВт·год) пропадає.")
    else:
        lines.append("Сонячної станції немає — частка власного сонця 0 %.")
    if ev["has_battery"]:
        src = "без СЕС, заряджається від мережі" if not ev["has_ses"] else "у складі СЕС"
        lines.append(f"Акумулятор {_num(ev['battery_kwh'], 2)} кВт·год ({src}, ДЕМО): у відключення доступно "
                     f"{_num(usable_kwh(ev['battery_kwh']))} кВт·год (розряд до {OUTAGE_SOC_FLOOR:.0%}).")
        lines.append(f"Навантаження в робочі години ({now.month:02d}.{now.year}): ≈ {_num(ev['work_load_kw'])} кВт → "
                     f"автономність {_num(ev['autonomy_hours'])} год без сонця"
                     + (f", {_num(ev['autonomy_hours_with_sun'])} год із сонцем від {now.hour:02d}:00"
                        + (" (і далі — на весь горизонт)" if ev["autonomy_with_sun_capped"] else "")
                        if ev["autonomy_hours_with_sun"] is not None else "") + ".")
        if ev["battery_kw"] and ev["work_load_kw"] and ev["battery_kw"] < ev["work_load_kw"]:
            lines.append(f"Увага: потужність акумулятора {_num(ev['battery_kw'])} кВт менша за навантаження — "
                         "у відключення доведеться живити лише критичні споживачі.")
    else:
        lines.append("Акумулятора немає — у відключення будівля без живлення (мережева СЕС без акумулятора вимикається разом із мережею).")
    a = ev["self_sufficiency_pct"]
    h = ev["autonomy_hours"] or 0.0
    lines.append(f"Індекс енергостійкості = {W_SELF:g} × {_num(min(a, SELF_CAP_PCT))}/{SELF_CAP_PCT:g} + {W_AUTONOMY:g} × "
                 f"{_num(min(h, AUTONOMY_CAP_H))}/{AUTONOMY_CAP_H:g} = {ev['index']} ({ev['index_class']}).")
    if ev["critical"]:
        lines.append("Критичний об'єкт (охорона здоров'я) — перший у черзі на акумулятори й СЕС.")
    if calc["pot"]:
        p = calc["pot"]
        lines.append(f"Рекомендована станція під власне споживання — {_num(p['rec'])} кВт (обмеження: {p['limited_by']}).")
    elif calc["pot_reason"]:
        lines.append(f"Потенціал СЕС не оцінено: {calc['pot_reason']}.")
    return lines


# ---------------- громада ----------------

def _median(vals):
    v = [x for x in vals if x is not None]
    return round(statistics.median(v), 1) if v else None


def community(evs: list[dict]) -> dict:
    ok = [e for e in evs if e["data_ok"]]
    elec = sum(e["_calc"]["elec"] for e in ok)
    self_kwh = sum(e["_calc"]["annual"]["self_kwh"] for e in ok)
    gen = sum(e["_calc"]["annual"]["gen_kwh"] for e in ok)
    pot_self = sum((e["_calc"]["pot"]["new"]["self_kwh"] if e["_calc"]["pot"] else e["_calc"]["annual"]["self_kwh"])
                   for e in ok)
    crit = [e for e in evs if e["critical"]]
    return {
        "sites": len(evs),
        "sites_with_data": len(ok),
        "ses_sites": sum(e["has_ses"] for e in evs),
        "battery_sites": sum(e["has_battery"] for e in evs),
        "ses_kw_total": round(sum(e["ses_kw"] or 0 for e in evs), 1),
        "battery_kwh_total": round(sum(e["battery_kwh"] or 0 for e in evs), 1),
        "elec_kwh_year_2025": round(elec),
        "solar_kwh_year_est": round(gen),
        "solar_self_kwh_year_est": round(self_kwh),
        "self_sufficiency_pct": round(100 * self_kwh / elec, 2) if elec else 0.0,
        "autonomy_hours_median": _median([e["autonomy_hours"] for e in evs if e["has_battery"]]),
        "critical_sites_total": len(crit),
        "critical_with_ses": sum(e["has_ses"] for e in crit),
        "critical_with_battery": sum(e["has_battery"] for e in crit),
        "potential_kw": round(sum(e["potential_add_kw"] or 0 for e in evs), 1),
        "potential_total_kw": round(sum(e["ses_kw"] or 0 for e in evs) + sum(e["potential_add_kw"] or 0 for e in evs), 1),
        "potential_sites": sum(1 for e in evs if (e["potential_add_kw"] or 0) > 0),
        "potential_self_sufficiency_pct": round(100 * pot_self / elec, 1) if elec else 0.0,
        "potential_cost_uah": round(sum(e["potential_cost_uah"] or 0 for e in evs)),
    }


def categories(evs: list[dict]) -> list[dict]:
    out = []
    for cat in sorted({e["category_short"] for e in evs}, key=lambda c: (priority_of(c), c)):
        grp = [e for e in evs if e["category_short"] == cat]
        ok = [e for e in grp if e["data_ok"]]
        elec = sum(e["_calc"]["elec"] for e in ok)
        self_kwh = sum(e["_calc"]["annual"]["self_kwh"] for e in ok)
        out.append({"category_short": cat, "priority_rank": priority_of(cat), "critical": cat in CRITICAL_CATEGORIES,
                    "sites": len(grp), "with_ses": sum(e["has_ses"] for e in grp),
                    "with_battery": sum(e["has_battery"] for e in grp),
                    "self_sufficiency_pct": round(100 * self_kwh / elec, 2) if elec else 0.0,
                    "autonomy_hours_median": _median([e["autonomy_hours"] for e in grp if e["has_battery"]]),
                    "potential_kw": round(sum(e["potential_add_kw"] or 0 for e in grp), 1)})
    return out


NOTES = [
    "ДЕМО: сонячні станції, акумулятори, погода дня й заряд змодельовані; реальні — будівлі, категорії та "
    "річне споживання електроенергії 2025 (UMUNI), генерація 1 кВт за PVGIS.",
    "Даних про реальні генератори чи резервне живлення закладів система не містить і не публікує.",
    "Потенціал — станції «під власне споживання» (екран «Де ставити нові СЕС»); тариф і ціни — ПРИПУЩЕННЯ.",
]


# ---------------- симуляція відключення ----------------

def simulate_outage(b, station: dict | None, day: date, start_hour: int, hours: int,
                    soc_pct: float | None = None) -> dict:
    """Погодинно: навантаження проти сонця й акумулятора під час відключення мережі."""
    elec = elec_2025(b)
    cap = (station or {}).get("battery_kwh") or 0.0
    has_ses = bool(station and station.get("total_kw"))
    floor = cap * OUTAGE_SOC_FLOOR
    # заряд на початку: заданий користувачем; або з симуляції доби (sites.py); акумулятор без СЕС — повний
    if soc_pct is not None:
        soc = cap * max(0.0, min(100.0, soc_pct)) / 100
        soc_src = "задано"
    elif cap and has_ses:
        rows = simulate_day(b, station, day)
        soc = (rows[start_hour - 1]["soc_kwh"] if start_hour > 0
               else random.Random(f"soc-{b.id}-{day}").uniform(0.45, 0.85) * cap)
        soc_src = "модель доби"
    else:
        soc = cap
        soc_src = "повний (заряджається від мережі)"
    soc_start = soc
    timeline = []
    survived = 0.0
    failed = False
    unmet = 0.0
    d, h = day, start_hour
    cache: dict[date, tuple[list[float], list[float]]] = {}
    for _ in range(hours):
        if d not in cache:
            rows = simulate_day(b, station if has_ses else None, d)
            cache[d] = ([r["cons_kwh"] for r in rows], [r["gen_kwh"] for r in rows])
        load, gen = cache[d][0][h], (cache[d][1][h] if cap > 0 else 0.0)  # без акумулятора інвертор вимкнено
        from_bat = 0.0
        if not elec:
            covered = False
        elif gen >= load:
            soc = min(cap, soc + (gen - load))
            covered = True
        else:
            need = load - gen
            from_bat = min(need, max(0.0, soc - floor))
            soc -= from_bat
            covered = from_bat >= need - 1e-9
            if not covered:
                unmet += need - from_bat
                if not failed:
                    survived += from_bat / need if need else 0.0
        if covered and not failed:
            survived += 1
        failed = failed or not covered
        timeline.append({"date": d.isoformat(), "hour": h, "load_kwh": round(load, 2),
                         "solar_kwh": round(gen, 2), "battery_kwh_after": round(soc, 2),
                         "from_battery_kwh": round(from_bat, 2), "covered": covered})
        h += 1
        if h == 24:
            h, d = 0, d + timedelta(days=1)

    if not elec:
        note = "У UMUNI немає споживання електроенергії цієї будівлі за 2025 рік — симуляція неможлива."
    elif cap <= 0:
        note = ("Акумулятора немає: у відключення мережева СЕС вимикається (захист від острівного режиму), "
                "будівля без живлення." if has_ses else "Ні СЕС, ні акумулятора — у відключення будівля без живлення.")
    elif not failed:
        note = (f"Будівля витримує все відключення ({hours} год): акумулятор"
                + (" і сонце" if has_ses else "") + f", наприкінці лишається {_num(soc)} кВт·год.")
    else:
        note = (f"Живлення вистачить на ≈ {_num(survived)} год із {hours}; не покрито {_num(unmet)} кВт·год. "
                "Варто живити лише критичні споживачі або додати акумулятор.")
    note += " ДЕМО: параметри акумулятора, погода й заряд змодельовані; споживання — з реального річного UMUNI."
    return {"demo": True, "id": b.id, "name": b.name, "day": day.isoformat(), "start_hour": start_hour, "hours": hours,
            "has_ses": has_ses, "battery_kwh": cap or None, "soc_start_kwh": round(soc_start, 2),
            "soc_start_pct": round(100 * soc_start / cap, 1) if cap else None, "soc_start_source": soc_src,
            "soc_floor_pct": round(100 * OUTAGE_SOC_FLOOR), "timeline": timeline,
            "survives_hours": round(survived, 1), "survives_all": bool(elec) and not failed,
            "unmet_kwh": round(unmet, 1), "note": note}
