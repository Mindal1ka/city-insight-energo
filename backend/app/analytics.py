"""Розрахунки: перерахунок у МВт·год, питоме споживання, умовний клас, рейтинг, дефекти даних.

Усі коефіцієнти й пороги — тут, описані в METHODOLOGY.md.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .import_umuni import AnnualReport, Building, detect_kind, key, read_annual, read_buildings

# --- Коефіцієнти перерахунку (METHODOLOGY.md, розділ 1) ---
GCAL_TO_MWH = 1.163  # 1 Гкал = 1,163 МВт·год (вимога ТЗ Ф2.1-01)
GAS_KWH_PER_M3 = 9.3  # нижча теплота згоряння природного газу ≈ 33,5 МДж/м³ ≈ 9,3 кВт·год/м³ (припущення, погодити з ментором)

# --- Умовні класи: відношення питомого споживання до медіани категорії ---
CLASS_BOUNDS = [(0.5, "A"), (0.75, "B"), (0.9, "C"), (1.1, "D"), (1.5, "E"), (2.0, "F")]  # далі — G

# --- Пороги валідатора ---
MIN_AREA_M2 = 1.0  # площа ≤ 1 м² — дефект
ELEC_KWH_M2_MAX = 150.0  # неможливо великий питомий показник електроенергії
ELEC_KWH_M2_MIN = 0.5  # підозріло малий (якщо споживання є)
JUMP_ERROR_RATIO = 10.0  # зростання в 10+ разів — ймовірна помилка даних
OUTLIER_RATIO = 5.0  # питоме в 5+ разів вище медіани категорії — виключаємо з рейтингу з поясненням

SHORT_CATEGORY = {
    "Будинок або споруда навчального закладу": "Заклади освіти",
    "Будинок або споруда дитячого дошкільного закладу": "Дошкільні заклади",
    "Заклад охорони здоров'я": "Охорона здоров'я",
    "Громадська будівля або споруда": "Громадські будівлі",
    "Спортивна споруда": "Спортивні споруди",
    "Житловий будинок": "Житлові будинки",
}


@dataclass
class YearData:
    year: int
    partial: bool
    coverage: float  # частка року, охоплена вивантаженням
    heat_gcal: float | None
    elec_kwh: float | None
    gas_m3: float | None
    cold_m3: float | None
    hot_m3: float | None
    heat_mwh: float | None = None
    elec_mwh: float | None = None
    gas_mwh: float | None = None
    total_mwh: float | None = None
    kwh_m2: float | None = None  # загальне питоме, кВт·год/м² за рік
    elec_kwh_m2: float | None = None


@dataclass
class BuildingView:
    id: int
    name: str
    address: str
    category: str
    category_short: str
    heating: str
    year_built: int | None
    floors: int | None
    heated_area: float | None
    heated_volume: float | None
    has_coords: bool
    years: dict[int, YearData] = field(default_factory=dict)
    in_rating: bool = False
    excluded_reason: str | None = None
    ratio_to_median: float | None = None
    eff_class: str | None = None
    rank: int | None = None
    rank_of: int | None = None
    defects: list[dict] = field(default_factory=list)


def _sum(*vals):
    v = [x for x in vals if x is not None]
    return sum(v) if v else None


def _cls(ratio: float) -> str:
    for bound, c in CLASS_BOUNDS:
        if ratio <= bound:
            return c
    return "G"


class Store:
    """Тримає дані в пам'яті й перераховує все після завантаження нового файлу."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.buildings: list[BuildingView] = []
        self.defects: list[dict] = []
        self.reports: dict[int, AnnualReport] = {}
        self.base_year: int | None = None
        self.sources: list[dict] = []
        self.reload()

    # ---------- завантаження ----------
    def reload(self) -> None:
        reg: list[Building] = []
        reports: dict[int, AnnualReport] = {}
        sources = []
        for p in sorted(self.data_dir.glob("*.xlsx")):
            kind = detect_kind(p)
            if kind == "buildings":
                reg = read_buildings(p)
                sources.append({"file": p.name, "kind": "Реєстр будівель", "rows": len(reg)})
            elif kind == "annual":
                rep = read_annual(p)
                # якщо за рік кілька файлів — беремо новіший за датою створення
                old = reports.get(rep.year)
                if not old or (rep.created and (not old.created or rep.created > old.created)):
                    reports[rep.year] = rep
                sources.append({"file": p.name, "kind": f"Річне споживання {rep.year}", "rows": len(rep.rows),
                                "created": rep.created.isoformat() if rep.created else None})
        self.reports = reports
        self.sources = sources
        full_years = [y for y, r in reports.items() if not self._partial(r)[0]]
        self.base_year = max(full_years) if full_years else (min(reports) if reports else None)
        self._build(reg, reports)

    @staticmethod
    def _partial(rep: AnnualReport) -> tuple[bool, float]:
        if rep.created and rep.created.year == rep.year:
            doy = rep.created.timetuple().tm_yday
            days = 366 if date(rep.year, 12, 31).timetuple().tm_yday == 366 else 365
            return True, round(doy / days, 3)
        return False, 1.0

    # ---------- розрахунок ----------
    def _build(self, reg: list[Building], reports: dict[int, AnnualReport]) -> None:
        by_key = {key(b.name, b.address): b for b in reg}
        views: dict[tuple, BuildingView] = {}
        defects: list[dict] = []

        def defect(bv, dataset, field_, value, rule, hint, kind="дефект даних"):
            d = {"тип": kind, "набір": dataset, "будівля_id": bv.id if bv else "", "будівля": bv.name if bv else "",
                 "поле": field_, "значення": "" if value is None else value, "правило": rule, "що_робити": hint}
            defects.append(d)
            if bv:
                bv.defects.append(d)

        for year in sorted(reports):
            rep = reports[year]
            partial, cov = self._partial(rep)
            for r in rep.rows:
                k = key(r.name, r.address)
                b = by_key.get(k)
                if k not in views:
                    views[k] = BuildingView(
                        id=b.id if b else -(len(views) + 1),
                        name=r.name, address=r.address, category=r.category,
                        category_short=SHORT_CATEGORY.get(r.category, r.category or "Інше"),
                        heating=r.heating or "", year_built=(b.year_built if b and b.year_built else r.year_built),
                        floors=b.floors if b else None,
                        heated_area=r.heated_area if r.heated_area is not None else (b.heated_area if b else None),
                        heated_volume=b.heated_volume if b else None,
                        has_coords=bool(b and b.lat),
                    )
                    if not b:
                        defect(views[k], rep.source, "назва+адреса", f"{r.name}; {r.address}",
                               "Будівлю не знайдено в реєстрі будівель", "Перевірити назву й адресу в UMUNI")
                bv = views[k]
                yd = YearData(year=year, partial=partial, coverage=cov, heat_gcal=r.heat_gcal, elec_kwh=r.elec_kwh,
                              gas_m3=r.gas_m3, cold_m3=r.cold_m3, hot_m3=r.hot_m3)
                yd.heat_mwh = r.heat_gcal * GCAL_TO_MWH if r.heat_gcal is not None else None
                yd.elec_mwh = r.elec_kwh / 1000 if r.elec_kwh is not None else None
                yd.gas_mwh = r.gas_m3 * GAS_KWH_PER_M3 / 1000 if r.gas_m3 is not None else None
                yd.total_mwh = _sum(yd.heat_mwh, yd.elec_mwh, yd.gas_mwh)
                area = bv.heated_area
                if area and area > MIN_AREA_M2:
                    if yd.total_mwh:
                        yd.kwh_m2 = yd.total_mwh * 1000 / area
                    if r.elec_kwh:
                        yd.elec_kwh_m2 = r.elec_kwh / area
                bv.years[year] = yd

        # --- правила валідатора ---
        for bv in views.values():
            src = "Реєстр будівель / річні звіти"
            if bv.heated_area is not None and bv.heated_area <= MIN_AREA_M2:
                defect(bv, src, "опалювана площа", bv.heated_area, "Площа ≤ 1 м²",
                       "Внести фактичну опалювану площу; питомі показники не рахуються")
            if bv.heated_area is None:
                defect(bv, src, "опалювана площа", None, "Немає площі", "Внести опалювану площу")
            if not bv.has_coords:
                defect(bv, "Реєстр будівель", "координати", "0,0", "Координати відсутні (0,0)", "Геокодувати адресу")
            if not bv.year_built:
                defect(bv, "Реєстр будівель", "рік забудови", None, "Не заповнено рік забудови", "Заповнити в UMUNI")
            if not bv.heating:
                defect(bv, "Річний звіт", "вид опалення", None, "Не заповнено вид опалення", "Заповнити в UMUNI")
            for y, yd in bv.years.items():
                ds = f"Річне споживання {y}"
                if all(v is None for v in (yd.heat_gcal, yd.elec_kwh, yd.gas_m3, yd.cold_m3, yd.hot_m3)):
                    defect(bv, ds, "усі ресурси", None, "Жодного показника споживання",
                           "Перевірити лічильники; будівля виключена з рейтингу")
                if yd.elec_kwh_m2 is not None and yd.elec_kwh_m2 / max(yd.coverage, 0.01) > ELEC_KWH_M2_MAX:
                    defect(bv, ds, "електроенергія", round(yd.elec_kwh_m2, 1),
                           f"Питоме споживання електроенергії > {ELEC_KWH_M2_MAX:.0f} кВт·год/м²",
                           "Ймовірна помилка вводу або площі")
                if yd.elec_kwh_m2 is not None and 0 < yd.elec_kwh_m2 < ELEC_KWH_M2_MIN:
                    defect(bv, ds, "електроенергія", round(yd.elec_kwh_m2, 2),
                           f"Питоме споживання електроенергії < {ELEC_KWH_M2_MIN} кВт·год/м²",
                           "Перевірити, чи враховано всі лічильники")
            # стрибки між роками (2026 неповний: порівнюємо з поправкою на охоплення року)
            ys = sorted(bv.years)
            for a, b in zip(ys, ys[1:]):
                A, B = bv.years[a], bv.years[b]
                for fld, label, unit in (("heat_gcal", "теплова енергія", "Гкал"), ("elec_kwh", "електроенергія", "кВт·год"),
                                         ("gas_m3", "газ", "м³"), ("hot_m3", "гаряча вода", "м³"), ("cold_m3", "холодна вода", "м³")):
                    va, vb = getattr(A, fld), getattr(B, fld)
                    if not va or vb is None:
                        continue
                    ratio = vb / va
                    if ratio >= JUMP_ERROR_RATIO:
                        defect(bv, f"Річне споживання {b}", label, f"{va:g} → {vb:g} {unit}",
                               f"Зростання в {ratio:.0f} разів — ймовірна помилка даних",
                               "Перевірити показники лічильника в UMUNI")
                    elif B.partial and vb > va:
                        defect(bv, f"Річне споживання {b}", label, f"{va:g} → {vb:g} {unit}",
                               f"Неповний {b} рік уже перевищив весь {a} рік (+{(ratio - 1) * 100:.0f}%)",
                               "Перевірити: зміна споживання чи помилка вводу", kind="аномалія споживання")

        # --- рейтинг у межах категорії за базовим роком ---
        by: dict[str, list[BuildingView]] = {}
        for bv in views.values():
            yd = bv.years.get(self.base_year) if self.base_year else None
            reason = None
            if bv.heated_area is None or bv.heated_area <= MIN_AREA_M2:
                reason = "Немає коректної опалюваної площі"
            elif not yd or not yd.total_mwh:
                reason = "Немає даних про енергоспоживання"
            bv.excluded_reason = reason
            bv.in_rating = reason is None
            if bv.in_rating:
                by.setdefault(bv.category_short, []).append(bv)
        self.medians = {}
        for cat, lst in list(by.items()):
            # викиди: питоме в OUTLIER_RATIO+ разів вище медіани — найчастіше помилка площі або облік кількох будівель
            med0 = statistics.median(b.years[self.base_year].kwh_m2 for b in lst)
            keep = []
            for b in lst:
                r = b.years[self.base_year].kwh_m2 / med0 if med0 else 0
                if r > OUTLIER_RATIO:
                    b.in_rating = False
                    b.excluded_reason = f"Питоме споживання в {r:.0f} разів вище медіани категорії"
                    defect(b, f"Річне споживання {self.base_year}", "питоме споживання",
                           round(b.years[self.base_year].kwh_m2), b.excluded_reason,
                           "Перевірити опалювану площу та чи не обліковано на будівлю споживання інших об'єктів")
                else:
                    keep.append(b)
            by[cat] = lst = keep
            med = statistics.median(b.years[self.base_year].kwh_m2 for b in lst)
            self.medians[cat] = med
            for b in lst:
                b.ratio_to_median = b.years[self.base_year].kwh_m2 / med if med else None
                b.eff_class = _cls(b.ratio_to_median) if b.ratio_to_median else None
            lst.sort(key=lambda b: b.years[self.base_year].kwh_m2, reverse=True)  # 1 = найменш ефективна
            for i, b in enumerate(lst, 1):
                b.rank, b.rank_of = i, len(lst)

        self.buildings = sorted(views.values(), key=lambda b: (b.category_short, b.rank or 10**6))
        self.defects = defects

    # ---------- представлення для API ----------
    def summary(self) -> dict:
        by_year = {}
        for y, rep in sorted(self.reports.items()):
            partial, cov = self._partial(rep)
            tot = lambda f: round(sum(getattr(b.years[y], f) or 0 for b in self.buildings if y in b.years), 1)
            by_year[y] = {"partial": partial, "coverage": cov,
                          "created": rep.created.isoformat() if rep.created else None,
                          "heat_gcal": tot("heat_gcal"), "elec_kwh": tot("elec_kwh"), "gas_m3": tot("gas_m3"),
                          "total_mwh": tot("total_mwh")}
        cats = {}
        for b in self.buildings:
            c = cats.setdefault(b.category_short, {"count": 0, "in_rating": 0, "median_kwh_m2": None})
            c["count"] += 1
            c["in_rating"] += int(b.in_rating)
        for c, med in self.medians.items():
            cats[c]["median_kwh_m2"] = round(med, 1)
        classes = {}
        for b in self.buildings:
            if b.eff_class:
                classes[b.eff_class] = classes.get(b.eff_class, 0) + 1
        return {"buildings": len(self.buildings), "in_rating": sum(b.in_rating for b in self.buildings),
                "base_year": self.base_year, "years": by_year, "categories": cats,
                "classes": dict(sorted(classes.items())), "defects": len(self.defects),
                "defect_buildings": len({d["будівля_id"] for d in self.defects}), "sources": self.sources,
                "coefficients": {"GCAL_TO_MWH": GCAL_TO_MWH, "GAS_KWH_PER_M3": GAS_KWH_PER_M3}}

    def view(self, b: BuildingView, full: bool = False) -> dict:
        d = asdict(b)
        d["years"] = {str(k): v for k, v in d["years"].items()}
        if not full:
            d.pop("defects")
            d["defects_count"] = len(b.defects)
        return d
