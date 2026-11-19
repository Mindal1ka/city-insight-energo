"""Оцінка 2026 року з реальних даних UMUNI: «з 1 січня до дати вивантаження» → повний рік і помісячно.

Реальне: е/е 2025 (повний рік) і е/е 2026 з 1 січня до дати вивантаження (11.11.2026) — UMUNI.
Розрахунок: частка сезонного профілю категорії, що припадає на період до дати вивантаження
(повні місяці + частина поточного), → рік 2026 = факт до дати ÷ ця частка.
Помісячно: рік 2026 × профіль; місяці до дати вивантаження — «оцінка факту», після — «прогноз».
Якість: якщо відношення 2026/2025 поза 0,4…2,5 — ймовірна помилка даних, оцінка не довіряється.
"""

from __future__ import annotations

import calendar
from datetime import date

from . import efficiency as eff
from . import solar

RATIO_OK = (0.4, 2.5)
TOP_MIN_KWH = 1000  # у топ зростання — лише об'єкти від 1 000 кВт·год/рік


def report_date(store, year: int = 2026) -> date | None:
    rep = getattr(store, "reports", {}).get(year)
    if rep is None or not rep.created or rep.created.year != year:
        return None
    return rep.created.date()


def share_to(category_short: str | None, d: date) -> float:
    """Частка річного споживання категорії з 1 січня до дня d (не включно)."""
    sh = solar.profile_shares(category_short)
    m = d.month - 1
    dim = calendar.monthrange(d.year, d.month)[1]
    return sum(sh[:m]) + sh[m] * (d.day - 1) / dim


def estimate(b, store) -> dict:
    """Оцінка 2026 для будівлі: рік, тренд до 2025, помісячно (факт-оцінка / прогноз)."""
    e25 = eff.elec_2025(b)
    y26 = b.years.get(2026)
    d = report_date(store)
    to_date = float(y26.elec_kwh) if y26 and y26.elec_kwh else 0.0
    out = {"kwh_2025": e25 or None, "kwh_2026_to_date": to_date or None,
           "to_date": d.isoformat() if d else None, "kwh_2026_est": None, "trend_pct": None,
           "quality": "немає даних", "months_2026": None}
    if not d or not to_date:
        out["quality"] = "немає даних 2026" if e25 else "немає даних"
        return out
    sh = share_to(b.category_short, d)
    if sh <= 0.05:
        return out
    est = to_date / sh
    out["kwh_2026_est"] = est
    if e25:
        ratio = est / e25
        out["trend_pct"] = 100 * (ratio - 1)
        out["quality"] = "ок" if RATIO_OK[0] <= ratio <= RATIO_OK[1] else "ймовірна помилка даних"
    else:
        out["quality"] = "немає 2025"
    shares = solar.profile_shares(b.category_short)
    out["months_2026"] = [{"month": i + 1, "kwh": est * s,
                           "kind": "оцінка факту" if i + 1 < d.month else "прогноз"} for i, s in enumerate(shares)]
    return out


def estimate_out(e: dict) -> dict:
    r = lambda v: None if v is None else round(v)
    return {**e, "kwh_2025": r(e["kwh_2025"]), "kwh_2026_to_date": r(e["kwh_2026_to_date"]),
            "kwh_2026_est": r(e["kwh_2026_est"]),
            "trend_pct": None if e["trend_pct"] is None else round(e["trend_pct"], 1),
            "months_2026": [{**m, "kwh": round(m["kwh"])} for m in e["months_2026"]] if e["months_2026"] else None}


def city(store) -> dict:
    """Зведення по громаді: 2025 vs оцінка 2026, скільки об'єктів ростуть / падають."""
    tot25 = tot26 = 0.0
    up = down = bad = n = 0
    rows = []
    for b in store.buildings:
        e = estimate(b, store)
        if e["quality"] != "ок":
            bad += e["quality"] == "ймовірна помилка даних"
            continue
        n += 1
        tot25 += e["kwh_2025"]
        tot26 += e["kwh_2026_est"]
        up += e["trend_pct"] > 10
        down += e["trend_pct"] < -10
        rows.append((b, e))
    rows = [r for r in rows if r[1]["kwh_2025"] >= TOP_MIN_KWH]  # дрібні споживачі — шум у відсотках
    rows.sort(key=lambda x: -x[1]["trend_pct"])
    top = [{"id": b.id, "name": b.name, "trend_pct": round(e["trend_pct"], 1),
            "kwh_2025": round(e["kwh_2025"]), "kwh_2026_est": round(e["kwh_2026_est"])} for b, e in rows[:10]]
    d = report_date(store)
    return {"to_date": d.isoformat() if d else None, "objects": n, "kwh_2025": round(tot25),
            "kwh_2026_est": round(tot26), "trend_pct": round(100 * (tot26 / tot25 - 1), 1) if tot25 else None,
            "growing": up, "falling": down, "suspicious": bad, "top_growth": top}
