"""Імпорт вивантажень UMUNI (XLSX) без ручної переробки.

Підтримувані звіти:
- «Характеристики будівель» (Buildings_Info_Report) — реєстр будівель з id;
- «Річний звіт використання ресурсів по будівлям» — споживання за рік (без id).

Тип файлу визначається за заголовками, рік — з аркуша «Інформація» (або з назви звіту).
Порожня клітинка означає «немає даних», а не нуль.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import openpyxl


def _num(v) -> float | None:
    """Число або None. Рядки з комою/пробілами теж розбираємо."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _str(v) -> str:
    return "" if v is None else str(v).strip()


def key(name: str, address: str) -> tuple[str, str]:
    """Ключ зв'язування будівлі між звітами: назва + адреса (у річних звітах немає id)."""
    norm = lambda s: re.sub(r"\s+", " ", s.strip().lower())
    return norm(name), norm(address)


@dataclass
class Building:
    id: int
    name: str
    address: str
    lat: float | None
    lon: float | None
    year_built: int | None
    floors: int | None
    people: float | None
    height: float | None
    area: float | None
    volume: float | None
    heated_area: float | None
    heated_volume: float | None


@dataclass
class AnnualRow:
    name: str
    address: str
    category: str
    year_built: int | None
    heated_area: float | None
    heating: str
    heat_gcal: float | None
    elec_kwh: float | None
    cold_m3: float | None
    hot_m3: float | None
    gas_m3: float | None


@dataclass
class AnnualReport:
    year: int
    created: datetime | None
    rows: list[AnnualRow] = field(default_factory=list)
    source: str = ""


def _find_header(rows: list[tuple], must: str) -> int:
    for i, r in enumerate(rows[:15]):
        if any(_str(c) == must for c in r):
            return i
    raise ValueError(f"Не знайдено рядок заголовків із колонкою «{must}»")


def _info_sheet(wb) -> dict[str, object]:
    for ws in wb.worksheets:
        if ws.title.strip().lower() == "інформація":
            return {_str(r[0]).rstrip(":"): r[1] for r in ws.iter_rows(values_only=True) if r and r[0]}
    return {}


def detect_kind(path: Path) -> str:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    first = [r for _, r in zip(range(5), wb.worksheets[0].iter_rows(values_only=True))]
    wb.close()  # Windows: не тримати файл відкритим
    flat = " ".join(_str(c) for r in first for c in r if c is not None).lower()
    if "характеристики будівель" in flat or ("heated_area" in flat and "latitude" in flat):
        return "buildings"
    if "річний звіт використання ресурсів" in flat:
        return "annual"
    if "id\nлічильника" in flat or "лічильника" in flat:
        return "meters"
    return "unknown"


def read_buildings(path: Path) -> list[Building]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    wb.close()
    h = _find_header(rows, "id")
    cols = {_str(c): i for i, c in enumerate(rows[h])}
    get = lambda r, c: r[cols[c]] if c in cols and cols[c] < len(r) else None
    out = []
    for r in rows[h + 1 :]:
        if get(r, "id") is None:
            continue
        lat, lon = _num(get(r, "latitude")), _num(get(r, "longitude"))
        if not lat or not lon:  # 0,0 у UMUNI означає «немає координат»
            lat = lon = None
        yb = _num(get(r, "year"))
        fl = _num(get(r, "floor"))
        out.append(
            Building(
                id=int(_num(get(r, "id"))),
                name=_str(get(r, "name")),
                address=_str(get(r, "address")),
                lat=lat,
                lon=lon,
                year_built=int(yb) if yb else None,
                floors=int(fl) if fl else None,
                people=_num(get(r, "people_quantity")),
                height=_num(get(r, "height")),
                area=_num(get(r, "area")),
                volume=_num(get(r, "area_size")),
                heated_area=_num(get(r, "heated_area")),
                heated_volume=_num(get(r, "heated_area_size")),
            )
        )
    return out


ANNUAL_COLS = {
    "name": "Назва будівлі",
    "address": "Адреса будівлі",
    "category": "Категорія",
    "year_built": "Рік",
    "heated_area": "Опалювана площа, м²",
    "heating": "Опалення",
    "heat_gcal": "Теплова енергія, Гкал",
    "elec_kwh": "Електроенергія, кВт*год",
    "cold_m3": "Холодна вода, м³",
    "hot_m3": "Гаряча вода, м³",
    "gas_m3": "Газ, м³",
}


def read_annual(path: Path) -> AnnualReport:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    info = _info_sheet(wb)
    rows = list(wb.worksheets[0].iter_rows(values_only=True))
    wb.close()
    h = _find_header(rows, "Назва будівлі")
    cols = {_str(c): i for i, c in enumerate(rows[h])}
    missing = [v for v in ANNUAL_COLS.values() if v not in cols]
    if missing:
        raise ValueError(f"У річному звіті бракує колонок: {', '.join(missing)}")

    year = _num(info.get("Рік запиту"))
    if not year:
        m = re.search(r"(20\d\d)", " ".join(_str(c) for c in rows[0] if c))
        year = float(m.group(1)) if m else None
    if not year:
        raise ValueError("Не вдалося визначити рік звіту")
    created = None
    if info.get("Дата створення"):
        try:
            created = datetime.strptime(_str(info["Дата створення"]), "%d.%m.%Y %H:%M:%S")
        except ValueError:
            pass

    rep = AnnualReport(year=int(year), created=created, source=path.name)
    for r in rows[h + 1 :]:
        g = lambda k: r[cols[ANNUAL_COLS[k]]] if cols[ANNUAL_COLS[k]] < len(r) else None
        if not _str(g("name")):
            continue
        yb = _num(g("year_built"))
        rep.rows.append(
            AnnualRow(
                name=_str(g("name")),
                address=_str(g("address")),
                category=_str(g("category")),
                year_built=int(yb) if yb else None,
                heated_area=_num(g("heated_area")),
                heating=_str(g("heating")),
                heat_gcal=_num(g("heat_gcal")),
                elec_kwh=_num(g("elec_kwh")),
                cold_m3=_num(g("cold_m3")),
                hot_m3=_num(g("hot_m3")),
                gas_m3=_num(g("gas_m3")),
            )
        )
    return rep
