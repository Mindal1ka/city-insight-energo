"""Потенціал нових сонячних станцій (СЕС) — кейс 2.2, вимоги Ф2.2-01…04.

Ланцюжок (усе рахується «на папері», без чорних скриньок):
  1. Площа даху ≈ опалювана площа ÷ поверховість; корисна частка й кВт на м² — константи нижче.
  2. Генерація на 1 кВт піку по місяцях — PVGIS (кеш у data/pvgis_poltava.json, мережа не потрібна).
  3. Місячне споживання = річна електроенергія 2025 (UMUNI) × сезонний профіль категорії.
  4. Розмір станції ПІД ВЛАСНЕ СПОЖИВАННЯ: найбільша потужність, за якої генерація жодного місяця
     не перевищує денного споживання (продавати надлишок комунальні заклади зараз не можуть).
  5. Покриття, капвитрати, економія, проста окупність, рейтинг.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PVGIS_FILE = Path(__file__).resolve().parents[1] / "data" / "pvgis_poltava.json"

# --- PVGIS: одна точка для всіх будівель ---
# Координати є лише в 34 з 311 будівель, тому беремо центр Полтави. Різниця інсоляції в межах
# громади — частки відсотка, на рейтинг не впливає.
PVGIS_LAT, PVGIS_LON = 49.589, 34.551
PVGIS_ANGLE, PVGIS_ASPECT, PVGIS_LOSS = 35, 0, 14  # нахил 35°, на південь, втрати системи 14 % (типові PVGIS)
PVGIS_URL = (f"https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat={PVGIS_LAT}&lon={PVGIS_LON}&peakpower=1"
             f"&loss={PVGIS_LOSS}&angle={PVGIS_ANGLE}&aspect={PVGIS_ASPECT}&outputformat=json")

# --- Дах (ПРИПУЩЕННЯ, користувач може передати власні значення в estimate()) ---
DEFAULT_FLOORS = 2  # якщо поверховість не заповнена
ROOF_USABLE_SHARE = 0.5  # 50 % даху придатні під панелі (парапети, вентиляція, затінення, проходи)
M2_PER_KWP = 6.0  # ≈ 6 м² корисного даху на 1 кВт піку (панель ~2 м² × 0,4 кВт + міжрядні відступи)
KWP_PER_M2_ROOF = ROOF_USABLE_SHARE / M2_PER_KWP  # кВт піку на 1 м² ВСЬОГО даху ≈ 0,083

# --- Споживання ---
DAYTIME_SHARE = 0.7  # частка споживання у світлий час доби (заклади працюють ≈ 8–16; оцінка 70–80 %)
MAX_SELF_SHARE = 1.0  # генерація місяця ≤ 100 % денного споживання місяця (без надлишку)
MIN_KW = 1.0  # менше 1 кВт — станцію не рекомендуємо

# --- Економіка: ПРИПУЩЕННЯ — замінити (значення шукає команда; можна передати ?tariff=&capex=) ---
# Фактична ціна 2025: касові видатки КЕКВ 2273 (openbudget) ÷ споживання UMUNI = 11,57 грн/кВт·год (/api/budget-real).
# Для порівняння: ПУП Полтаваенергозбут, 2 клас, листопад 2026 — 12,09; Prozorro, ліцей №3 — 12,29.
TARIFF_UAH_KWH = 11.57  # грн/кВт·год з ПДВ — та сама ціна, що в «Бюджеті» й пітчі
CAPEX_UAH_PER_KW = 22000.0  # мережева СЕС під ключ без акумулятора, грн/кВт (панелі 8–9,5 грн/Вт + інвертор + монтаж 20 %), 2026
# ПРИПУЩЕННЯ — замінити: фіксовані витрати на один об'єкт незалежно від потужності (проєкт, техумови й
# підключення, лічильник, моніторинг). Без них окупність усіх станцій «під власне споживання» однакова
# (та сама інсоляція, без надлишку), і рейтинг за окупністю нічого не розрізняє. Задати 0, щоб вимкнути.
CAPEX_FIXED_UAH = 60000.0

# --- Сезонні профілі споживання електроенергії (відносні ваги по місяцях, січень…грудень) ---
# ПРИПУЩЕННЯ: UMUNI дає лише річну суму. Профілі замінити помісячними даними UMUNI, щойно місто їх надасть.
# Школи: літні канікули (червень–серпень) — споживання різко падає.
# Садки: влітку працюють чергові групи — падіння менше.
# Лікарні: працюють цілодобово й цілорічно — рівний профіль.
# Громадські будівлі: м'який профіль (взимку більше освітлення).
SEASONAL_PROFILES: dict[str, list[float]] = {
    "Заклади освіти":     [1.15, 1.10, 1.05, 1.00, 0.95, 0.45, 0.28, 0.32, 1.00, 1.05, 1.10, 1.15],  # КМДА: канікули в 3–6 разів менше
    "Дошкільні заклади":  [1.10, 1.05, 1.05, 1.00, 1.00, 0.80, 0.65, 0.70, 1.00, 1.05, 1.10, 1.10],
    "Охорона здоров'я":   [1.00] * 12,
    "Громадські будівлі": [1.10, 1.05, 1.00, 0.95, 0.90, 0.90, 0.90, 0.90, 0.95, 1.00, 1.05, 1.10],
    "Спортивні споруди":  [1.10, 1.05, 1.00, 0.95, 0.90, 0.85, 0.85, 0.85, 0.95, 1.00, 1.05, 1.10],
    "Житлові будинки":    [1.15, 1.10, 1.00, 0.95, 0.90, 0.85, 0.85, 0.85, 0.95, 1.00, 1.10, 1.15],
}
FLAT_PROFILE = [1.0] * 12


def profile_shares(category_short: str | None) -> list[float]:
    """Частки річного споживання по місяцях (сума = 1)."""
    w = SEASONAL_PROFILES.get(category_short or "", FLAT_PROFILE)
    s = sum(w)
    return [x / s for x in w]


@lru_cache(maxsize=1)
def pvgis_monthly() -> tuple[float, ...]:
    """Генерація 1 кВт піку по місяцях, кВт·год (PVGIS, середнє за 2005–2023)."""
    d = json.loads(PVGIS_FILE.read_text(encoding="utf-8"))
    rows = sorted(d["outputs"]["monthly"]["fixed"], key=lambda r: r["month"])
    return tuple(float(r["E_m"]) for r in rows)


def pvgis_meta() -> dict:
    d = json.loads(PVGIS_FILE.read_text(encoding="utf-8"))
    return {"meteo": d["inputs"]["meteo_data"], "cache": d.get("_cache", {}),
            "E_y": d["outputs"]["totals"]["fixed"]["E_y"]}


def fetch_pvgis(path: Path = PVGIS_FILE) -> None:
    """Оновити кеш PVGIS (потрібна мережа; під час роботи сервера не викликається)."""
    import datetime
    import urllib.request

    with urllib.request.urlopen(PVGIS_URL, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    d = {"_cache": {"url": PVGIS_URL, "fetched": datetime.date.today().isoformat(),
                    "note": "Кеш відповіді PVGIS PVcalc для центру Полтави, 1 кВт піку"}, **d}
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    pvgis_monthly.cache_clear()


@dataclass
class SolarResult:
    roof_area_m2: float
    floors_assumed: bool
    kw_max_roof: float
    kw_recommended: float
    limited_by: str  # "споживання" або "дах"
    gen: list[float] = field(default_factory=list)  # по місяцях, кВт·год
    cons: list[float] = field(default_factory=list)
    self_: list[float] = field(default_factory=list)
    surplus: list[float] = field(default_factory=list)
    elec_kwh_year: float = 0.0
    gen_kwh_year: float = 0.0
    self_consumed_kwh_year: float = 0.0
    surplus_kwh_year: float = 0.0
    coverage_pct: float = 0.0
    capex_uah: float = 0.0
    savings_uah_year: float = 0.0
    payback_years: float | None = None


def _floor1(x: float) -> float:
    """Округлення ВНИЗ до 0,1 кВт — щоб після округлення обмеження «без надлишку» не порушувалось."""
    return math.floor(x * 10 + 1e-9) / 10


def estimate(elec_kwh_year: float, heated_area: float, floors: int | None, category_short: str | None, *,
             roof_area_m2: float | None = None, usable_share: float = ROOF_USABLE_SHARE,
             m2_per_kwp: float = M2_PER_KWP, daytime_share: float = DAYTIME_SHARE,
             max_self_share: float = MAX_SELF_SHARE, tariff: float = TARIFF_UAH_KWH,
             capex_per_kw: float = CAPEX_UAH_PER_KW,
             capex_fixed: float = CAPEX_FIXED_UAH, kw_override: float | None = None) -> SolarResult:
    """Розрахунок для однієї будівлі. roof_area_m2 / kw_override — ручне уточнення користувачем."""
    floors_assumed = not floors or floors < 1
    fl = DEFAULT_FLOORS if floors_assumed else floors
    roof = roof_area_m2 if roof_area_m2 is not None else heated_area / fl
    kw_max_roof = _floor1(roof * usable_share / m2_per_kwp)

    e = pvgis_monthly()
    cons = [elec_kwh_year * s for s in profile_shares(category_short)]
    # найбільша потужність, за якої в КОЖНОМУ місяці генерація ≤ частка × денне споживання
    kw_cons = min(max_self_share * daytime_share * c / em for c, em in zip(cons, e))
    if kw_override is not None:
        kw, limited_by = kw_override, "користувач"
    elif kw_cons <= kw_max_roof:
        kw, limited_by = _floor1(kw_cons), "споживання"
    else:
        kw, limited_by = kw_max_roof, "дах"

    gen = [kw * em for em in e]
    day = [daytime_share * c for c in cons]
    self_ = [min(g, d) for g, d in zip(gen, day)]
    surplus = [g - s for g, s in zip(gen, self_)]

    r = SolarResult(roof_area_m2=roof, floors_assumed=floors_assumed, kw_max_roof=kw_max_roof,
                    kw_recommended=kw, limited_by=limited_by, gen=gen, cons=cons, self_=self_, surplus=surplus)
    r.elec_kwh_year = elec_kwh_year
    r.gen_kwh_year = sum(gen)
    r.self_consumed_kwh_year = sum(self_)
    r.surplus_kwh_year = sum(surplus)
    r.coverage_pct = 100 * r.self_consumed_kwh_year / elec_kwh_year if elec_kwh_year else 0.0
    r.capex_uah = capex_fixed + kw * capex_per_kw if kw > 0 else 0.0
    r.savings_uah_year = r.self_consumed_kwh_year * tariff
    r.payback_years = r.capex_uah / r.savings_uah_year if r.savings_uah_year > 0 else None
    return r


def item_dict(bid: int, name: str, category_short: str, r: SolarResult) -> dict:
    """Поля для API (округлення: кВт — 0,1; кВт·год і грн — цілі; окупність — 0,1 року)."""
    return {
        "id": bid, "name": name, "category_short": category_short,
        "elec_kwh_year": round(r.elec_kwh_year),
        "roof_area_m2": round(r.roof_area_m2),
        "kw_max_roof": round(r.kw_max_roof, 1),
        "kw_recommended": round(r.kw_recommended, 1),
        "gen_kwh_year": round(r.gen_kwh_year),
        "self_consumed_kwh_year": round(r.self_consumed_kwh_year),
        "coverage_pct": round(r.coverage_pct, 1),
        "surplus_kwh_year": round(r.surplus_kwh_year),
        "capex_uah": round(r.capex_uah),
        "savings_uah_year": round(r.savings_uah_year),
        "payback_years": round(r.payback_years, 1) if r.payback_years is not None else None,
        "limited_by": r.limited_by,
        "rank": None,
    }


def monthly_rows(r: SolarResult) -> list[dict]:
    return [{"month": m + 1, "gen_kwh": round(r.gen[m]), "cons_kwh": round(r.cons[m]),
             "self_kwh": round(r.self_[m]), "surplus_kwh": round(r.surplus[m])} for m in range(12)]


def source_notes() -> list[str]:
    meta = pvgis_meta()
    m = meta["meteo"]
    return [
        f"Генерація: PVGIS v5.3 PVcalc ({m.get('radiation_db')}, {m.get('year_min')}–{m.get('year_max')}), "
        f"центр Полтави {PVGIS_LAT}, {PVGIS_LON} для всіх будівель (координати є лише в 34 з 311), "
        f"нахил {PVGIS_ANGLE}°, південь, втрати {PVGIS_LOSS} %: {meta['E_y']:.0f} кВт·год на 1 кВт за рік.",
        f"Дах ≈ опалювана площа ÷ поверховість (якщо поверховість не вказана — {DEFAULT_FLOORS} поверхи); "
        f"під панелі придатно {ROOF_USABLE_SHARE:.0%} даху, {M2_PER_KWP:g} м² на 1 кВт.",
        "Споживання: електроенергія 2025 року з UMUNI, розподілена по місяцях за сезонним профілем категорії "
        "(ПРИПУЩЕННЯ — замінити помісячними даними UMUNI; школи й садки влітку споживають менше).",
        f"Розмір під власне споживання: генерація жодного місяця не перевищує {MAX_SELF_SHARE:.0%} денного "
        f"споживання (удень — {DAYTIME_SHARE:.0%} доби), бо продавати надлишок комунальні заклади зараз не можуть.",
        f"Вартість станції = {CAPEX_FIXED_UAH:,.0f} грн на об'єкт (проєкт, підключення) + потужність × ціна кВт. "
        .replace(",", " ") +
        "Тариф і вартість монтажу — ПРИПУЩЕННЯ, замінити уточненими значеннями (можна задати у формі).",
        "Проста окупність = вартість монтажу ÷ річна економія, без кредиту, інфляції й деградації панелей. "
        "Це аналітична оцінка, а не проєкт станції.",
    ]


def assumptions_for(r: SolarResult, floors: int | None, tariff: float, capex: float,
                    capex_fixed: float = CAPEX_FIXED_UAH) -> list[str]:
    a = []
    if r.floors_assumed:
        a.append(f"Поверховість не вказана в реєстрі — прийнято {DEFAULT_FLOORS} поверхи.")
    else:
        a.append(f"Дах ≈ опалювана площа ÷ {floors} пов. = {r.roof_area_m2:.0f} м².")
    a.append(f"Придатно під панелі {ROOF_USABLE_SHARE:.0%} даху, {M2_PER_KWP:g} м² на 1 кВт → "
             f"максимум на дах {r.kw_max_roof:.1f} кВт.")
    a.append(f"Рекомендована потужність {r.kw_recommended:.1f} кВт обмежена: {r.limited_by}.")
    a.append(f"Удень споживається {DAYTIME_SHARE:.0%} електроенергії; генерація місяця ≤ {MAX_SELF_SHARE:.0%} "
             "денного споживання.")
    a.append("Сезонний профіль споживання — ПРИПУЩЕННЯ за категорією, до отримання помісячних даних UMUNI.")
    money = lambda x: f"{x:,.0f}".replace(",", " ")
    a.append(f"Вартість = {money(capex_fixed)} грн на об'єкт + {r.kw_recommended:.1f} кВт × {money(capex)} грн/кВт "
             f"= {money(r.capex_uah)} грн; тариф {str(round(tariff, 2)).replace('.', ',')} грн/кВт·год. Тариф і ціни — ПРИПУЩЕННЯ, замінити.")
    a.append("Генерація — PVGIS для центру Полтави, середній рік; фактична залежить від погоди й затінення.")
    return a
