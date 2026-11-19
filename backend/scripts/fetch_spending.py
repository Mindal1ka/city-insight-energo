"""Реальні платежі за електроенергію (КЕКВ 2273) з spending.gov.ua (Є-Data, казначейські транзакції).

Публічне API без ключа: https://api.spending.gov.ua/api/v2/api/transactions/?payers_edrpous=…&startdate=…&enddate=…
Беремо помісячно, лишаємо КЕКВ 2273, ділимо за отримувачем:
  енергія       — постачальник (ТОВ «Гарантований постачальник» 44986633 або назва містить «постачальн»);
  розподіл      — оператор системи розподілу ПАТ «Полтаваобленерго» 00131819;
  внутрішні     — платник сам собі (переказ між рахунками) — у підсумки не входить;
  інше          — решта (відшкодування закладам тощо).
Результат: backend/data/spending_2273.csv

Запуск: python backend/scripts/fetch_spending.py 2025-01 2026-10
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from calendar import monthrange
from collections import defaultdict
from pathlib import Path

# Розпорядники, що платять за е/е закладів (ЄДРПОУ → назва). Школи й садки оплачуються централізовано Департаментом.
PAYERS = {"02145725": "Департамент освіти ПМР"}
ENERGY = {"44986633", "46000698", "42067041"}  # Гарантований постачальник (2025), Провідна енергетична компанія, Енерджи Трейдинг (2026)
DISTRIBUTION = {"00131819"}
URL = "https://api.spending.gov.ua/api/v2/api/transactions/?payers_edrpous={p}&startdate={a}&enddate={b}"
OUT = Path(__file__).resolve().parents[1] / "data" / "spending_2273.csv"


def kind(payer: str, r: dict) -> str:
    rec = str(r.get("recipt_edrpou") or "")
    name = str(r.get("recipt_name") or "").lower()
    if rec == payer:
        return "внутрішні"
    if rec in DISTRIBUTION or "обленерго" in name:
        return "розподіл"
    if rec in ENERGY or any(w in name for w in ("постачальн", "енергетичн", "енерджи", "трейдинг", "енергозбут")):
        return "енергія"
    return "інше"


def month_range(a: str, b: str):
    y, m = map(int, a.split("-"))
    y2, m2 = map(int, b.split("-"))
    while (y, m) <= (y2, m2):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def fetch(payer: str, y: int, m: int) -> list[dict]:
    url = URL.format(p=payer, a=f"{y}-{m:02d}-01", b=f"{y}-{m:02d}-{monthrange(y, m)[1]:02d}")
    req = urllib.request.Request(url, headers={"User-Agent": "insight-tool/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def main(a: str, b: str) -> None:
    agg: dict[tuple, list] = defaultdict(lambda: [0.0, 0])
    for payer, pname in PAYERS.items():
        for y, m in month_range(a, b):
            rows = [r for r in fetch(payer, y, m) if str(r.get("kekv")) == "2273"]
            for r in rows:
                k = (payer, pname, y, m, kind(payer, r))
                agg[k][0] += float(r.get("amount") or 0)
                agg[k][1] += 1
            print(f"{pname} {y}-{m:02d}: {len(rows)} платежів КЕКВ 2273")
            time.sleep(0.5)  # чемно до публічного API
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["payer_edrpou", "payer", "year", "month", "kind", "amount_uah", "payments"])
        for (p, pn, y, m, k), (s, n) in sorted(agg.items()):
            w.writerow([p, pn, y, m, k, round(s, 2), n])
    print(f"{OUT}: {len(agg)} рядків")


if __name__ == "__main__":
    args = sys.argv[1:] or ["2025-01", "2026-10"]
    main(args[0], args[1])
