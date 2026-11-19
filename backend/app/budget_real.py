"""Реальний бюджет на електроенергію (КЕКВ 2273) з openbudget.gov.ua — data/openbudget_2273.csv.

Що реальне: план і касове виконання за програмами ТПКВКМБ бюджету Полтавської ТГ, помісячно.
Як прив'язуємо до будівель (ПРАВИЛО): тип / назва закладу → програма; ліміт будівлі = план програми ×
частка її кВт·год 2025 серед будівель цієї програми в UMUNI. Заклади охорони здоров'я (КНП) платять
з власних рахунків — у бюджеті їх немає, для них ліміт лишається МОК.
"""

from __future__ import annotations

import csv
import os
from functools import lru_cache
from pathlib import Path

from . import efficiency as eff

DATA = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
FILE = DATA / "openbudget_2273.csv"
SOURCE = "openbudget.gov.ua"
# Програму розподіляємо на будівлі, лише якщо будівлі UMUNI покривають її майже повністю:
# фактична ціна 2025 (факт програми ÷ кВт·год будівель групи) має бути правдоподібною.
PRICE_OK = (7.0, 18.0)


def program_of(b) -> str | None:
    cat = b.category_short or ""
    n = (b.name or "").lower()
    if any(w in n for w in ("мистецтв", "музичн", "художн")):
        return "1080"  # мистецькі школи
    if cat == "Заклади освіти":
        if "спеціальн" in n or "інклюзивн" in n:
            return "1022"
        return "1021"  # заклади загальної середньої освіти
    if cat == "Дошкільні заклади":
        return "1010"
    if cat == "Спортивні споруди" or "дюсш" in n or "спортив" in n:
        return "5031"
    if "бібліот" in n:
        return "4030"
    if "музей" in n:
        return "4040"
    if any(w in n for w in ("клуб", "будинок культури", "палац культури", "центр культури")):
        return "4060"
    if "староста" in n or "старостин" in n:
        return "0160"
    if any(w in n for w in ("міська рада", "виконавч")):
        return "0150"
    return None


@lru_cache(maxsize=1)
def _rows(mtime: float) -> list[dict]:
    if not FILE.exists():
        return []
    with FILE.open(encoding="utf-8") as f:
        return [{**r, "year": int(r["year"]), "month": int(r["month"]), "approved": float(r["approved"]),
                 "plan": float(r["plan"]), "fact_cum": float(r["fact_cum"])} for r in csv.DictReader(f)]


def rows() -> list[dict]:
    return _rows(FILE.stat().st_mtime if FILE.exists() else 0.0)


def programs(year: int) -> dict[str, dict]:
    """Програма → назва, план (останній місяць), факт наростаючим, останній місяць, платежі по місяцях."""
    out: dict[str, dict] = {}
    for r in rows():
        if r["year"] != year:
            continue
        p = out.setdefault(r["program"], {"program": r["program"], "name": r["name"], "cum": {}})
        p["cum"][r["month"]] = r["fact_cum"]
        if r["month"] >= max(p["cum"]):
            p["plan"], p["approved"] = r["plan"], r["approved"]
    for p in out.values():
        last = max(p["cum"])
        p["last_month"] = last
        p["fact"] = p["cum"][last]
        p["monthly"] = [max(0.0, p["cum"].get(m, p["cum"].get(m - 1, 0)) - p["cum"].get(m - 1, 0))
                        if m <= last else None for m in range(1, 13)]
    return out


def group_kwh(store) -> dict[str, float]:
    tot: dict[str, float] = {}
    for b in store.buildings:
        p = program_of(b)
        if p:
            tot[p] = tot.get(p, 0.0) + eff.elec_2025(b)
    return tot


def price_2025(program: str, store) -> float | None:
    a = programs(2025).get(program)
    k = group_kwh(store).get(program)
    return a["fact"] / k if a and k else None


def allocatable(program: str | None, store) -> bool:
    pr = price_2025(program, store) if program else None
    return bool(pr and PRICE_OK[0] <= pr <= PRICE_OK[1])


def limit_year(b, store, year: int = 2026) -> float | None:
    """Реальний ліміт будівлі: план програми × частка кВт·год будівлі в групі. None — програми немає
    або будівлі UMUNI покривають її не повністю (тоді ліміт — МОК)."""
    p = program_of(b)
    progs = programs(year)
    if not p or p not in progs or not allocatable(p, store):
        return None
    g = group_kwh(store).get(p) or 0.0
    e = eff.elec_2025(b)
    return progs[p]["plan"] * e / g if g and e else None


def summary(store) -> dict:
    """Програми: план/факт 2025 і 2026, фактична ціна кВт·год 2025 = факт 2025 ÷ кВт·год UMUNI групи."""
    p25, p26 = programs(2025), programs(2026)
    kwh = group_kwh(store)
    counts: dict[str, int] = {}
    for b in store.buildings:
        p = program_of(b)
        if p:
            counts[p] = counts.get(p, 0) + 1
    items = []
    for code in sorted(set(p25) | set(p26), key=lambda c: -(p26.get(c, p25.get(c, {})).get("plan") or 0)):
        a, z = p25.get(code), p26.get(code)
        k = kwh.get(code) or 0.0
        items.append({"program": code, "name": (z or a)["name"], "buildings": counts.get(code, 0),
                      "kwh_2025": round(k) if k else None,
                      "plan_2025": round(a["plan"]) if a else None, "fact_2025": round(a["fact"]) if a else None,
                      "plan_2026": round(z["plan"]) if z else None, "fact_2026": round(z["fact"]) if z else None,
                      "fact_2026_month": z["last_month"] if z else None,
                      "price_2025": round(a["fact"] / k, 2) if a and k else None,
                      "allocated": allocatable(code, store),
                      "monthly_2025": [None if v is None else round(v) for v in a["monthly"]] if a else None,
                      "monthly_2026": [None if v is None else round(v) for v in z["monthly"]] if z else None})
    tot = lambda key: round(sum(i[key] or 0 for i in items))
    matched = [i for i in items if i["allocated"]]
    return {"source": SOURCE, "budget_code": "1657010000", "kekv": "2273",
            "updated_month_2026": max((i["fact_2026_month"] or 0) for i in items) if items else None,
            "totals": {"plan_2025": tot("plan_2025"), "fact_2025": tot("fact_2025"), "plan_2026": tot("plan_2026"),
                       "fact_2026": tot("fact_2026"),
                       "price_2025": round(sum(i["fact_2025"] for i in matched) / sum(i["kwh_2025"] for i in matched), 2)
                       if matched else None},
            "items": items}
