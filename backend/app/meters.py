"""Лічильники (набір D2-04, Ф2.1-02): кількість лічильників за ресурсами на будівлю.

У репозиторії зберігається лише знеособлений `data/meters.csv` (без заводських номерів),
його готує `scripts/sanitize_sources.py` з вивантаження UMUNI «Перелік будівель та їх лічильників».
Зв'язок з будівлями — за `id будівлі` UMUNI (той самий id, що й у реєстрі будівель).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

METERS_CSV = "meters.csv"
FIELDS = ["building_id", "building", "meter_id", "model", "resource", "type", "technical", "transit"]
ELECTRICITY = "Електроенергія"

# колонки вихідного XLSX (заголовки з переносами рядків нормалізуємо до одного пробілу)
_SRC = {
    "building_id": "id будівлі",
    "building": "Назва будівлі",
    "meter_id": "id лічильника",
    "model": "модель лічильника",
    "resource": "Ресурс",
    "type": "Тип",
    "technical": "Технічний",
    "transit": "Транзитний",
}
# «Номер лічильника» (заводський номер) навмисно НЕ читається


def _h(v) -> str:
    return re.sub(r"\s+", " ", "" if v is None else str(v)).strip()


def _flag(v) -> bool:
    return _h(v) in ("+", "1", "так", "Так", "true", "True")


def clean_model(model: str, serial: str = "") -> str:
    """Модель без вкраплень заводського номера: прибираємо сам номер і будь-які 7+ цифр поспіль."""
    m = _h(model)
    s = re.sub(r"[^\w]", "", serial or "")
    s = s.lstrip("№")
    if len(s) >= 5 and s in m:
        m = m.replace(s, "")
    m = re.sub(r"[A-Za-zА-Яа-яІіЇїЄє]?\d{7,}[\w-]*", "", m)
    m = re.sub(r"\(\s*\)", "", m)
    return re.sub(r"\s+", " ", m).strip(" -–(),")


def sanitize_meters(xlsx: Path) -> list[dict]:
    """XLSX UMUNI → рядки для meters.csv (без заводських номерів, без даних аркуша «Інформація»)."""
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    try:
        ws = wb["Лічильники"] if "Лічильники" in wb.sheetnames else wb.worksheets[0]
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()  # Windows: інакше файл лишається зайнятим і тимчасовий файл не видалити
    hi = next(i for i, r in enumerate(rows[:15]) if any(_h(c) == "id лічильника" for c in r))
    cols = {_h(c): i for i, c in enumerate(rows[hi])}
    missing = [v for v in _SRC.values() if v not in cols]
    if missing:
        raise ValueError(f"У файлі лічильників бракує колонок: {', '.join(missing)}")
    serial_col = cols.get("Номер лічильника")
    out = []
    for r in rows[hi + 1:]:
        g = lambda k: r[cols[_SRC[k]]] if cols[_SRC[k]] < len(r) else None
        bid = _h(g("building_id"))
        if not bid:
            continue
        serial = _h(r[serial_col]) if serial_col is not None and serial_col < len(r) else ""
        out.append({
            "building_id": int(float(bid)),
            "building": _h(g("building")),
            "meter_id": _h(g("meter_id")),
            "model": clean_model(_h(g("model")), serial),
            "resource": _h(g("resource")),
            "type": _h(g("type")),
            "technical": "так" if _flag(g("technical")) else "",
            "transit": "так" if _flag(g("transit")) else "",
        })
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def load_meters(path: Path) -> dict[int, list[dict]]:
    """meters.csv → {id будівлі: [лічильники]}; файлу немає — порожній словник."""
    out: dict[int, list[dict]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                bid = int(r["building_id"])
            except (KeyError, ValueError):
                continue
            out.setdefault(bid, []).append(r)
    return out


def meters_view(lst: list[dict] | None) -> dict:
    """Зведення лічильників однієї будівлі для картки об'єкта."""
    lst = lst or []
    by: dict[str, int] = {}
    for m in lst:
        res = m.get("resource") or "Не вказано"
        by[res] = by.get(res, 0) + 1
    return {
        "total": len(lst),
        "electricity": by.get(ELECTRICITY, 0),
        "by_resource": dict(sorted(by.items(), key=lambda kv: -kv[1])),
        "technical": sum(1 for m in lst if m.get("technical")),
        "transit": sum(1 for m in lst if m.get("transit")),
    }


def meters_summary(by_bid: dict[int, list[dict]], building_ids: set[int]) -> dict:
    """Зведення по громаді для /api/summary."""
    allm = [m for lst in by_bid.values() for m in lst]
    v = meters_view(allm)
    v.update({
        "buildings_with_meters": len(set(by_bid) & building_ids),
        "buildings_with_electricity": sum(1 for b in building_ids if meters_view(by_bid.get(b))["electricity"]),
        "buildings_without_meters": len(building_ids - set(by_bid)),
        "meter_buildings_not_in_registry": len(set(by_bid) - building_ids),
    })
    return v
