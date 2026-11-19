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
import os
import random
import re
import tempfile
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import solar

KYIV = timezone(timedelta(hours=2))  # листопад: EET, UTC+2 (спрощення для демо)
BATTERY_RESERVE = 0.3  # 30 % ємності акумулятора тримаємо в резерві на відключення
REGISTRY_FILE = (Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
                 / "ses_registry.csv")

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

# --- ДЕМО-реєстр СЕС ---
# Реальні моделі інверторів (номінал, кВт) за виробниками; якщо одного не вистачає — кілька паралельно.
INVERTER_FAMILIES = {
    "Deye": [("Deye SUN-5K-SG04LP3-EU", 5), ("Deye SUN-8K-SG04LP3-EU", 8), ("Deye SUN-10K-SG04LP3-EU", 10),
             ("Deye SUN-12K-SG04LP3-EU", 12), ("Deye SUN-15K-SG01HP3-EU-AM2", 15),
             ("Deye SUN-20K-SG01HP3-EU-AM2", 20), ("Deye SUN-25K-SG01HP3-EU-AM2", 25),
             ("Deye SUN-30K-SG01HP3-EU-BM3", 30), ("Deye SUN-50K-SG01HP3-EU-BM4", 50)],
    "Huawei": [("Huawei SUN2000-5KTL-M1", 5), ("Huawei SUN2000-8KTL-M1", 8), ("Huawei SUN2000-10KTL-M1", 10),
               ("Huawei SUN2000-20KTL-M2", 20), ("Huawei SUN2000-30KTL-M3", 30),
               ("Huawei SUN2000-50KTL-M3", 50), ("Huawei SUN2000-100KTL-M1", 100)],
    "Growatt": [("Growatt MOD 6KTL3-XH", 6), ("Growatt MOD 10KTL3-XH", 10), ("Growatt MOD 15KTL3-XH", 15),
                ("Growatt MID 25KTL3-X", 25), ("Growatt MAX 50KTL3 LV", 50), ("Growatt MAX 100KTL3-X LV", 100)],
    "LuxPower": [("LuxPower LXP-LB-EU 10K", 10), ("LuxPower LXP-LB-EU 12K", 12)],
}
INVERTER_WEIGHTS = {"Deye": 0.45, "Huawei": 0.25, "Growatt": 0.2, "LuxPower": 0.1}
DC_AC_RATIO_MAX = 1.3  # панелей може бути до 1,3× номіналу інвертора (типове перевантаження DC/AC)
PANEL_W_CHOICES = (410, 450, 550, 590)
BATTERY_MODULES_KWH = (5.12, 10.24)  # LiFePO4-модулі 51,2 В × 100 / 200 А·год
BATTERY_C_RATE = 0.5  # потужність акумулятора ≈ 0,5 × ємність

SES_MIN_KWH = 8000  # станції лише в будівлях із річним споживанням е/е 2025 ≥ 8 000 кВт·год
SES_SHARE = 0.4  # ≈ 40 % таких будівель мають станцію (детерміновано за id)
PV_DERATE = 0.92  # втрати й деградація понад PVGIS (той самий множник, що й у detail())
# суміш цільових річних K = генерація ÷ споживання: (частка, від, до)
K_MIX = ((0.50, 0.3, 0.8), (0.38, 0.8, 1.2), (0.12, 1.2, 1.5))  # місто ставить СЕС під власне споживання; надлишок — рідко

# --- Ціни 2026 (роздріб Україна, листопад 2026; гібрид під ключ виходить ≈ 31–37 тис. грн/кВт, як у тендерах шкіл) ---
PANEL_UAH_PER_450W = 3825.0  # 8,5 грн/Вт (Jinko 590 Вт N-type 4,5–5,7 тис. грн); інші потужності — пропорційно
INVERTER_UAH_PER_KW = 7000.0  # гібрид Deye/LuxPower 10–30 кВт (великі 4,5–5 тис., малі 10–12 тис.)
BATTERY_UAH_PER_KWH = 9500.0  # LiFePO4 Deye/Pylontech 7,8–12 тис. грн/кВт·год
INSTALL_SHARE, INSTALL_FIXED_UAH = 0.20, 30000.0  # монтаж ≈ 20 % обладнання + 30 000 грн (проєкт, щит, підключення)

# Колонки CSV реєстру (data/ses_registry.csv) — ключ у коді → заголовок українською
CSV_COLUMNS = {
    "building_id": "building_id",
    "panels_count": "панелей_шт",
    "panel_w": "потужність_панелі_Вт",
    "total_kw": "потужність_СЕС_кВт",
    "inverter_model": "інвертор_модель",
    "inverter_kw": "інвертор_кВт",
    "battery_count": "к-сть_акумуляторів",
    "battery_module_kwh": "ємність_модуля_кВт·год",
    "battery_kwh": "акумулятор_кВт·год",
    "battery_kw": "акумулятор_кВт",
    "connected_kw": "приєднана_потужність_кВт",
    "launched": "дата_запуску",
    "panels_uah": "вартість_панелей_грн",
    "inverter_uah": "вартість_інвертора_грн",
    "batteries_uah": "вартість_акумуляторів_грн",
    "install_uah": "вартість_монтажу_грн",
    "source": "джерело",
    "updated": "оновлено",
}
SES_FIELDS = ("panels_count", "panel_w", "total_kw", "inverter_model", "inverter_kw", "battery_count",
              "battery_module_kwh", "battery_kwh", "battery_kw", "connected_kw", "launched")
COST_FIELDS = ("panels_uah", "inverter_uah", "batteries_uah", "install_uah")
_registry_lock = threading.Lock()


def city_of(address: str) -> str:
    m = re.search(r"\bс(?:ело)?\.\s*([А-ЯІЇЄҐ][\w'’\-]+)", address)
    return m.group(1) if m else "Полтава"


def _f(v, default=None):
    try:
        return float(str(v).replace(",", ".")) if str(v).strip() != "" else default
    except ValueError:
        return default


def _pick_inverter(family: str, need_kw: float) -> tuple[str, float]:
    """Найменший інвертор родини з номіналом ≥ need_kw; якщо такого немає — N однакових паралельно."""
    models = INVERTER_FAMILIES[family]
    for name, kw in models:
        if kw >= need_kw:
            return name, float(kw)
    name, kw = models[-1]
    n = math.ceil(need_kw / kw)
    return f"{n} × {name}", float(n * kw)


def _round10(x: float) -> float:
    return float(round(x, -1))


def demo_costs(panels_count: int, panel_w: float, inverter_kw: float, battery_kwh: float,
               rng: random.Random | None = None) -> dict:
    """Орієнтовні витрати на станцію (ДЕМО-ціни вище; rng — невеликий розкид цін постачальників)."""
    j = (lambda: rng.uniform(0.92, 1.08)) if rng else (lambda: 1.0)
    panels = _round10(panels_count * PANEL_UAH_PER_450W * panel_w / 450 * j())
    inverter = _round10(inverter_kw * INVERTER_UAH_PER_KW * j())
    batteries = _round10(battery_kwh * BATTERY_UAH_PER_KWH * j())
    install = _round10(INSTALL_SHARE * (panels + inverter + batteries) + INSTALL_FIXED_UAH)
    return {"panels_uah": panels, "inverter_uah": inverter, "batteries_uah": batteries, "install_uah": install}


def demo_station(b, elec_kwh: float, rng: random.Random) -> dict:
    """Одна ДЕМО-станція під цільовий річний K (суміш K_MIX)."""
    u, acc = rng.random(), 0.0
    lo, hi = K_MIX[-1][1:]
    for share, a, z in K_MIX:
        acc += share
        if u < acc:
            lo, hi = a, z
            break
    k_target = rng.uniform(lo, hi)
    kw_target = k_target * elec_kwh / (sum(solar.pvgis_monthly()) * PV_DERATE)
    panel_w = rng.choice(PANEL_W_CHOICES)
    n = max(4, round(kw_target * 1000 / panel_w))
    total_kw = round(n * panel_w / 1000, 2)
    fam = rng.choices(list(INVERTER_WEIGHTS), weights=list(INVERTER_WEIGHTS.values()))[0]
    model, inv_kw = _pick_inverter(fam, total_kw / DC_AC_RATIO_MAX)
    bat_n = rng.choices(range(7), weights=[15, 12, 20, 14, 18, 9, 12])[0]  # ≈15 % без акумулятора (школи-укриття — гібрид)
    module = rng.choice(BATTERY_MODULES_KWH) if bat_n else None
    bat_kwh = round(bat_n * module, 2) if bat_n else 0.0
    bat_kw = round(min(bat_kwh * BATTERY_C_RATE, inv_kw), 1) if bat_n else 0.0
    peak_kw = elec_kwh / 8760 * 3  # орієнтовний пік навантаження
    connected = next((c for c in (15, 30, 50, 75, 100, 150, 200, 300, 400, 500, 750, 1000)
                      if c >= max(peak_kw * rng.uniform(1.2, 1.8), inv_kw * 0.8)), 1000)
    if bat_kw >= 8 and rng.random() < 0.1:  # кілька станцій навмисно з порушенням «акумулятор > приєднаної»
        connected = max(5, round(bat_kw * 0.8))
    start = min(date(2023, 1, 15) + timedelta(days=rng.randint(0, 1080)), date(2025, 12, 20))
    st = {"panels_count": n, "panel_w": panel_w, "total_kw": total_kw, "inverter_model": model,
          "inverter_kw": inv_kw, "battery_count": bat_n, "battery_module_kwh": module, "battery_kwh": bat_kwh,
          "battery_kw": bat_kw, "connected_kw": float(connected), "launched": start.isoformat(),
          "source": "ДЕМО", "k_target": round(k_target, 3)}
    st["costs"] = _with_total(demo_costs(n, panel_w, inv_kw, bat_kwh, rng))
    return st


def _with_total(costs: dict) -> dict | None:
    vals = [costs.get(k) for k in COST_FIELDS]
    if all(v is None for v in vals):
        return None
    return {**{k: costs.get(k) for k in COST_FIELDS}, "total_uah": float(sum(v or 0 for v in vals))}


def make_entry(raw: dict, source: str = "введено") -> dict:
    """Нормалізує введені дані (CSV / форма): порожнє = None («немає даних»); похідні поля — тут."""
    num = lambda k: _f(raw.get(k)) if raw.get(k) is not None else None
    n, w = num("panels_count"), num("panel_w")
    total = round(n * w / 1000, 2) if n and w else num("total_kw")
    bat_n, module = num("battery_count"), num("battery_module_kwh")
    bat_kwh = round(bat_n * module, 2) if bat_n is not None and module else num("battery_kwh")
    if bat_n == 0 and bat_kwh is None:
        bat_kwh = 0.0
    launched = str(raw.get("launched") or "").strip()[:10] or None
    e = {"panels_count": int(n) if n is not None else None, "panel_w": w, "total_kw": total,
         "inverter_model": (str(raw.get("inverter_model") or "").strip() or None), "inverter_kw": num("inverter_kw"),
         "battery_count": int(bat_n) if bat_n is not None else None, "battery_module_kwh": module,
         "battery_kwh": bat_kwh, "battery_kw": num("battery_kw"), "connected_kw": num("connected_kw"),
         "launched": launched, "source": source}
    e["costs"] = _with_total({k: num(k) for k in COST_FIELDS})
    return e


def is_station(e: dict | None) -> bool:
    """Запис реєстру описує СЕС (є панелі) або хоча б акумулятор."""
    return bool(e and ((e.get("total_kw") or 0) > 0 or (e.get("battery_kwh") or 0) > 0))


def read_csv(path: Path | None = None) -> dict[int, dict]:
    """Сирі рядки CSV за building_id (ключі — англійські, як у CSV_COLUMNS)."""
    path = path or REGISTRY_FILE
    out: dict[int, dict] = {}
    if not path.exists():
        return out
    back = {v: k for k, v in CSV_COLUMNS.items()}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            row = {back.get(h, h): (v.strip() if isinstance(v, str) else v) for h, v in r.items() if h}
            bid = int(_f(row.get("building_id"), 0) or 0)
            if bid:
                out[bid] = {k: (v if v not in ("", None) else None) for k, v in row.items()}
    return out


def save_entry(bid: int, data: dict, path: Path | None = None) -> None:
    """Записати/оновити рядок будівлі в CSV атомарно (тимчасовий файл + os.replace), UTF-8 з BOM для Excel."""
    path = path or REGISTRY_FILE
    with _registry_lock:
        rows = read_csv(path)
        row = {k: data.get(k) for k in (*SES_FIELDS, *COST_FIELDS)}
        row.update(building_id=bid, source="введено", updated=datetime.now(KYIV).isoformat(timespec="seconds"))
        rows[bid] = row
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".ses_registry.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(CSV_COLUMNS.values())
                for b_id in sorted(rows):
                    r = rows[b_id]
                    w.writerow(["" if r.get(k) is None else r.get(k) for k in CSV_COLUMNS])
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def load_registry(buildings) -> dict[int, dict]:
    """Реєстр СЕС: ДЕМО-генерація (детерміновано за id), поверх неї — рядки data/ses_registry.csv ('введено').

    Рядок CSV без панелей і акумулятора означає «станції немає» — ДЕМО-станцію цієї будівлі прибираємо.
    """
    reg: dict[int, dict] = {}
    for b in buildings:
        y = b.years.get(2025)
        if not y or not y.elec_kwh or y.elec_kwh < SES_MIN_KWH:
            continue
        rng = random.Random(f"ses-v5-{b.id}")  # сіль підібрано: розподіл K близький до K_MIX
        if rng.random() >= SES_SHARE:
            continue
        reg[b.id] = demo_station(b, y.elec_kwh, rng)
    for bid, raw in read_csv().items():
        e = make_entry(raw, raw.get("source") or "введено")
        if is_station(e):
            reg[bid] = e
        else:
            reg.pop(bid, None)
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
        e_day = solar.pvgis_monthly()[d.month - 1] / days * (ses.get("total_kw") or 0.0)
        e_day *= _weather(d) * random.Random(f"gen-{b.id}-{d}").uniform(0.92, 1.05)
        gen = [e_day * s for s in _solar_shape(d.month)]
        bat_kwh = ses.get("battery_kwh") or 0.0
        soc = random.Random(f"soc-{b.id}-{d}").uniform(0.45, 0.85) * bat_kwh
    rows = []
    for h in range(24):
        g, c = gen[h], cons[h]
        self_use = min(g, c)
        net = g - c
        to_bat = from_bat = surplus = 0.0
        p = (ses.get("battery_kw") or bat_kwh * BATTERY_C_RATE) if ses else 0.0
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
        if ses and ses.get("launched") and ses.get("total_kw"):
            start = date.fromisoformat(ses["launched"])
            gen_total = 0.0
            cur = start
            while cur <= d:  # помісячно за PVGIS × 0,92 (втрати й деградація)
                dim = calendar.monthrange(cur.year, cur.month)[1]
                last = min(date(cur.year, cur.month, dim), d)
                gen_total += solar.pvgis_monthly()[cur.month - 1] * ses["total_kw"] * PV_DERATE * ((last - cur).days + 1) / dim
                cur = last + timedelta(days=1)
            period.update(since=ses["launched"], days=(d - start).days, generated_kwh=round(gen_total),
                          saved_uah=round(gen_total * 0.9 * tariff))

        dist = {"peak_kw": _r(peak["cons_kwh"]), "peak_hour": peak["hour"],
                "need_kwh_rest_of_day": _r(sm(fut, "cons_kwh")),
                "battery_kwh_now": None, "battery_soc_pct": None, "solar_kw_now": None, "solar_kwh_rest_of_day": None}
        available = 0.0
        if ses:
            soc_now = past[-1]["soc_kwh"] if past else rows[0]["soc_kwh"]
            bk = ses.get("battery_kwh") or 0.0
            usable = max(0.0, soc_now - BATTERY_RESERVE * bk)
            dist.update(battery_kwh_now=_r(soc_now), battery_soc_pct=_r(100 * soc_now / bk) if bk else None,
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
