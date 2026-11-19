"""Графіки погодинних відключень Полтаваобленерго (ГПВ) і реальні платежі за е/е (spending.gov.ua).

Відключення: неофіційне дзеркало сторінки poe.pl.ua/disconnection/power-outages — репозиторій
pragmatrans/poe-data (schedule.json, оновлюється кілька разів на день). 48 півгодинних клітинок на добу:
1 — світло є, 2 — відключення, 3 — можливе відключення. Кешуємо на 15 хв у data/poe_schedule.json;
якщо мережа недоступна — віддаємо останній кеш (з позначкою часу).
Черга кожної будівлі в даних міста не вказана → порівнюємо автономію об'єктів із найдовшим
безперервним відключенням серед черг (найгірший випадок).
"""

from __future__ import annotations

import csv
import json
import os
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends

from .auth import User, current_user

router = APIRouter(tags=["Відключення, платежі"])

DATA = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[1] / "data")
POE_URL = "https://raw.githubusercontent.com/pragmatrans/poe-data/HEAD/schedule.json"
POE_CACHE = DATA / "poe_schedule.json"
POE_TTL = 15 * 60
SPENDING = DATA / "spending_2273.csv"
_mem = {"t": 0.0, "data": None}


def _load_poe() -> tuple[dict | None, str]:
    now = time.time()
    if _mem["data"] is not None and now - _mem["t"] < POE_TTL:
        return _mem["data"], "кеш"
    try:
        req = urllib.request.Request(POE_URL, headers={"User-Agent": "insight-tool/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        _mem.update(t=now, data=data)
        try:
            POE_CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return data, "онлайн"
    except Exception:  # мережа / формат — повертаємо останній збережений
        if POE_CACHE.exists():
            try:
                data = json.loads(POE_CACHE.read_text(encoding="utf-8"))
                _mem.update(t=now, data=data)
                return data, "збережений кеш"
            except ValueError:
                pass
        return None, "недоступно"


def _longest(cells: list[int], codes=(2,)) -> float:
    best = cur = 0
    for c in cells:
        cur = cur + 1 if c in codes else 0
        best = max(best, cur)
    return best / 2


def schedule() -> dict:
    data, status = _load_poe()
    if not data:
        return {"status": status, "queues": [], "days": []}
    days: set[str] = set()
    queues = []
    for q, v in sorted((data.get("queues") or {}).items()):
        dd = []
        for day, x in (v.get("days") or {}).items():
            cells = [int(c) for c in x.get("cells") or []]
            if len(cells) != 48:
                continue
            days.add(day)
            dd.append({"day": day, "hours_off": cells.count(2) / 2, "hours_maybe": cells.count(3) / 2,
                       "longest_off_h": _longest(cells), "longest_with_maybe_h": _longest(cells, (2, 3)),
                       "off": x.get("off") or [], "cells": cells, "updated": x.get("updated")})
        queues.append({"queue": q, "now": v.get("now"), "days": dd})
    return {"status": status, "source": "Полтаваобленерго (poe.pl.ua) через github.com/pragmatrans/poe-data",
            "updated": data.get("updated") or data.get("generated"), "days": sorted(days), "queues": queues}


@router.get("/api/outages")
def outages(user: User = Depends(current_user)):
    s = schedule()
    first = lambda q: q["days"][0] if q["days"] else None
    worst = max((first(q)["longest_with_maybe_h"] for q in s["queues"] if first(q)), default=None)
    total = max((first(q)["hours_off"] for q in s["queues"] if first(q)), default=None)
    return {**s, "worst_longest_h": worst, "worst_hours_off": total}


# ---------------- реальні платежі (spending.gov.ua) ----------------

def spending() -> dict:
    if not SPENDING.exists():
        return {"source": "spending.gov.ua", "items": [], "payers": []}
    by: dict[tuple, dict] = defaultdict(lambda: {"енергія": 0.0, "розподіл": 0.0, "інше": 0.0})
    payers = {}
    with SPENDING.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["kind"] == "внутрішні":
                continue
            payers[r["payer_edrpou"]] = r["payer"]
            by[(r["payer_edrpou"], int(r["year"]), int(r["month"]))][r["kind"]] += float(r["amount_uah"])
    items = [{"payer_edrpou": p, "payer": payers[p], "year": y, "month": m,
              **{k: round(v) for k, v in d.items()}, "total": round(sum(d.values()))}
             for (p, y, m), d in sorted(by.items())]
    yt: dict[int, dict] = defaultdict(lambda: {"енергія": 0.0, "розподіл": 0.0, "інше": 0.0})
    for i in items:
        for k in ("енергія", "розподіл", "інше"):
            yt[i["year"]][k] += i[k]
    years = {y: {**{k: round(v) for k, v in d.items()}, "total": round(sum(d.values())),
                 "distribution_share_pct": round(100 * d["розподіл"] / sum(d.values()), 1) if sum(d.values()) else None}
             for y, d in sorted(yt.items())}
    return {"source": "spending.gov.ua", "kekv": "2273",
            "payers": [{"edrpou": k, "name": v} for k, v in payers.items()], "years": years, "items": items}


@router.get("/api/spending")
def spending_api(user: User = Depends(current_user)):
    return spending()
