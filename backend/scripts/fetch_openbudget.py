"""Завантажити з openbudget.gov.ua витрати бюджету Полтавської ТГ на електроенергію (КЕКВ 2273) за програмами.

Публічне API, без ключа: https://api.openbudget.gov.ua/api/public/localBudgetData
Результат: backend/data/openbudget_2273.csv (рік, місяць, програма ТПКВКМБ, назва, затверджено, план, факт наростаючим).

Запуск: python backend/scripts/fetch_openbudget.py [2025 2026]
"""

from __future__ import annotations

import csv
import io
import sys
import urllib.request
from pathlib import Path

BUDGET = "1657010000"  # бюджет Полтавської міської ТГ
URL = ("https://api.openbudget.gov.ua/api/public/localBudgetData?budgetCode={b}&budgetItem=EXPENSES"
       "&classificationType=PROGRAM&period=MONTH&year={y}")
OUT = Path(__file__).resolve().parents[1] / "data" / "openbudget_2273.csv"


def fetch(year: int) -> list[dict]:
    req = urllib.request.Request(URL.format(b=BUDGET, y=year), headers={"User-Agent": "insight-tool/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        text = r.read().decode("utf-8-sig")
    rows = []
    for x in csv.DictReader(io.StringIO(text), delimiter=";"):
        if x.get("COD_CONS_EK") != "2273" or x.get("FUND_TYP") != "T":
            continue
        mm, yy = x["REP_PERIOD"].split(".")
        num = lambda k: round(float(x.get(k) or 0), 2)
        rows.append({"year": int(yy), "month": int(mm), "program": x["COD_CONS_MB_PK"],
                     "name": x["COD_CONS_MB_PK_NAME"], "approved": num("ZAT_AMT"), "plan": num("PLANS_AMT"),
                     "fact_cum": num("FAKT_AMT")})
    return rows


def main(years: list[int]) -> None:
    rows = [r for y in years for r in fetch(y)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["year", "month", "program", "name", "approved", "plan", "fact_cum"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["year"], r["program"], r["month"])))
    print(f"{OUT}: {len(rows)} рядків")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2025, 2026])
