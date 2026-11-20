"""Свіжість даних і журнал завантажень.

Для кожного джерела — дата, на яку дані актуальні, вік і статус за очікуваною періодичністю:
  fresh  — у межах періоду;
  due    — пора оновити (період минув, але запас ще є);
  stale  — застаріли (минуло більше, ніж період + запас).

Журнал: data/upload_log.json — справжні завантаження через /api/upload (успішні й відхилені).
Поки справжніх записів мало, історію доповнює ДЕМО-журнал (позначка demo: true): він збудований
з реальних дат вивантажень UMUNI і запусків скриптів, щоб показати, як виглядає регулярне оновлення.
"""

from __future__ import annotations

import csv
import json
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

KYIV = timezone(timedelta(hours=2))  # листопад: EET, UTC+2 (як у sites.py)
LOG_NAME = "upload_log.json"
LOG_LIMIT = 300
_lock = threading.Lock()

# Очікувана періодичність (днів) і запас до «застаріли»
CADENCE = {
    "annual": (35, 15),     # річний звіт поточного року — щомісяця
    "buildings": (100, 30),  # реєстр будівель — щокварталу
    "meters": (100, 30),     # лічильники — щокварталу
    "sem": (190, 60),        # стан СЕМ — раз на пів року
}
# Бюджет і платежі публікуються з відставанням: рахуємо в місяцях від останнього звітного місяця
MONTH_LAG = {"openbudget": (2, 3), "spending": (2, 3)}  # fresh ≤ 2, due ≤ 3, далі stale

KIND_LABEL = {
    "buildings": "Реєстр будівель",
    "annual": "Річне споживання",
    "meters": "Лічильники",
    "sem": "Стан енергоменеджменту (СЕМ)",
    "openbudget": "Бюджет на е/е (openbudget.gov.ua)",
    "spending": "Платежі за е/е (spending.gov.ua)",
    "unknown": "Невідомий файл",
}
HOW = {
    "buildings": "upload", "annual": "upload", "meters": "upload",
    "sem": "script", "openbudget": "script", "spending": "script",
}
HOW_HINT = {
    "upload": "Завантажити XLSX з UMUNI на сторінці «Оновити дані»",
    "script": "Оновлює адміністратор даних скриптом (кнопки поки немає)",
    "auto": "Оновлюється автоматично",
}


def now_kyiv() -> datetime:
    return datetime.now(KYIV)


# ---------- журнал ----------

def log_path(data_dir: Path) -> Path:
    return data_dir / LOG_NAME


def read_log(data_dir: Path) -> list[dict]:
    p = log_path(data_dir)
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
        return [r for r in rows if isinstance(r, dict) and r.get("at")]
    except (OSError, ValueError):
        return []


def record(data_dir: Path, *, file: str, kind: str, ok: bool, user: str, role: str,
           rows: int | None = None, year: int | None = None, error: str | None = None,
           at: datetime | None = None) -> dict:
    entry = {"at": (at or now_kyiv()).isoformat(timespec="seconds"), "file": file, "kind": kind,
             "year": year, "ok": ok, "rows": rows, "error": error, "user": user, "role": role,
             "channel": "upload", "demo": False}
    with _lock:
        rows_ = read_log(data_dir)
        rows_.append(entry)
        p = log_path(data_dir)
        tmp = p.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(rows_[-LOG_LIMIT:], ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(p)
        except OSError:
            pass  # журнал не має ламати завантаження
    return entry


def demo_log(store) -> list[dict]:
    """ДЕМО-історія: щомісячні вивантаження річного звіту + рідші файли та скрипти.

    Опорні дати — справжні (дата створення звітів UMUNI, дати пакета міста), решта — правдоподібний ритм.
    """
    EM = ("Провідний фахівець з енергозабезпечення", "energy_manager")
    DA = ("Адміністратор даних UMUNI", "data_admin")
    rep26 = store.reports.get(2026)
    rep25 = store.reports.get(2025)
    n26 = len(rep26.rows) if rep26 else None
    n25 = len(rep25.rows) if rep25 else None
    n_b = len(store.buildings) or None
    n_m = sum(len(v) for v in (store.meters or {}).values()) or None
    last26 = rep26.created if rep26 and rep26.created else datetime(2026, 11, 11, 10, 42)

    def e(at, file, kind, user, ok=True, rows=None, year=None, error=None, channel="upload"):
        return {"at": at.replace(tzinfo=KYIV).isoformat(timespec="seconds"), "file": file, "kind": kind,
                "year": year, "ok": ok, "rows": rows, "error": error, "user": user[0], "role": user[1],
                "channel": channel, "demo": True}

    out = [
        e(last26.replace(tzinfo=None) + timedelta(minutes=9), "Річне_використання_ресурсів_2026.xlsx",
          "annual", DA, rows=n26, year=2026),
        e(datetime(2026, 11, 11, 11, 5), "Лічильники.xlsx", "meters", DA, rows=n_m),
        e(datetime(2026, 11, 10, 16, 20), "Звіт_листопад.xls", "unknown", EM, ok=False,
          error="Потрібен файл XLSX з UMUNI"),
        e(datetime(2026, 11, 3, 9, 15), "spending_2273.csv", "spending", DA, rows=None, channel="script"),
        e(datetime(2026, 10, 14, 9, 30), "openbudget_2273.csv", "openbudget", DA, channel="script"),
        e(datetime(2026, 10, 9, 10, 12), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 9, 8, 14, 3), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 9, 8, 13, 58), "Споживання_вересень.xlsx", "unknown", EM, ok=False,
          error="Не розпізнано звіт UMUNI (очікується «Характеристики будівель», «Річний звіт» або «Лічильники»)"),
        e(datetime(2026, 8, 25, 11, 40), "Buildings_Info_Report.xlsx", "buildings", DA, rows=n_b),
        e(datetime(2026, 8, 7, 9, 50), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 7, 13, 15, 25), "sem_status.csv", "sem", DA, channel="script"),
        e(datetime(2026, 7, 9, 10, 5), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 6, 10, 9, 41), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 5, 12, 10, 30), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 4, 9, 11, 2), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 3, 11, 9, 20), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 2, 10, 10, 0), "Річне_використання_ресурсів_2026.xlsx", "annual", EM, rows=n26, year=2026),
        e(datetime(2026, 1, 15, 12, 10), "Річне_використання_ресурсів_2025.xlsx", "annual", DA, rows=n25, year=2025),
    ]
    return out


def history(store, data_dir: Path, limit: int = 50) -> dict:
    real = read_log(data_dir)
    demo = demo_log(store)
    rows = sorted(real + demo, key=lambda r: r["at"], reverse=True)[:limit]
    for r in rows:
        r["kind_label"] = KIND_LABEL.get(r["kind"], r["kind"]) + (f" {r['year']}" if r.get("year") else "")
    return {"items": rows, "real": len(real), "demo": len(demo)}


# ---------- свіжість ----------

def _status_days(age: int, kind: str) -> str:
    period, grace = CADENCE[kind]
    return "fresh" if age <= period else "due" if age <= period + grace else "stale"


def _last_month(path: Path) -> tuple[int, int] | None:
    try:
        with path.open(encoding="utf-8-sig") as f:
            ym = [(int(r["year"]), int(r["month"])) for r in csv.DictReader(f)]
        return max(ym) if ym else None
    except (OSError, ValueError, KeyError):
        return None


def _last_ok(entries: list[dict], kind: str, year: int | None = None) -> datetime | None:
    ts = [datetime.fromisoformat(e["at"]) for e in entries
          if e["kind"] == kind and e.get("ok") and (year is None or e.get("year") == year)]
    return max(ts) if ts else None


def freshness(store, data_dir: Path, today: date | None = None) -> dict:
    now = now_kyiv()
    today = today or now.date()
    entries = read_log(data_dir) + demo_log(store)
    out = []

    def add(key, kind, as_of: date | None, status: str, demo: bool, detail: str, period: str):
        out.append({"key": key, "kind": kind, "label": KIND_LABEL[kind] + (f" {key[-4:]}" if key.startswith("annual") else ""),
                    "as_of": as_of.isoformat() if as_of else None,
                    "age_days": (today - as_of).days if as_of else None, "status": status, "demo": demo,
                    "how": HOW[kind], "how_hint": HOW_HINT[HOW[kind]], "period": period, "detail": detail})

    # Річне споживання поточного року: дата створення звіту UMUNI (справжня)
    cur = today.year
    rep = store.reports.get(cur) or store.reports.get(cur - 1)
    if rep:
        created = rep.created.date() if rep.created else None
        up = _last_ok(entries, "annual", rep.year)
        as_of = created or (up.date() if up else None)
        st = _status_days((today - as_of).days, "annual") if as_of else "stale"
        if rep.year < cur and today.month > 1:
            st = "stale"  # за поточний рік звіту немає зовсім
        add(f"annual{rep.year}", "annual", as_of, st, demo=created is None,
            detail="Дата створення звіту в UMUNI" if created else "Дата завантаження", period="щомісяця")
    else:
        add(f"annual{cur}", "annual", None, "stale", False, "Звіту немає", "щомісяця")

    # Реєстр будівель і лічильники: дата останнього завантаження (справжнього або ДЕМО)
    for kind, have in (("buildings", bool(store.buildings)), ("meters", bool(store.meters))):
        real_up = _last_ok(read_log(data_dir), kind)
        up = real_up or _last_ok(entries, kind)
        as_of = up.date() if up else None
        st = _status_days((today - as_of).days, kind) if as_of and have else "stale"
        add(kind, kind, as_of, st, demo=real_up is None, detail="Дата завантаження", period="щокварталу")

    # СЕМ — скрипт знеособлення
    up = _last_ok(entries, "sem")
    as_of = up.date() if up else None
    add("sem", "sem", as_of, _status_days((today - as_of).days, "sem") if as_of else "stale", demo=True,
        detail="Дата запуску скрипта", period="раз на пів року")

    # Бюджет і платежі — останній звітний місяць у CSV (справжній)
    for kind, fname in (("openbudget", "openbudget_2273.csv"), ("spending", "spending_2273.csv")):
        ym = _last_month(data_dir / fname)
        if ym:
            y, m = ym
            lag = (today.year * 12 + today.month) - (y * 12 + m)
            fresh, due = MONTH_LAG[kind]
            st = "fresh" if lag <= fresh else "due" if lag <= due else "stale"
            nxt = date(y + (m == 12), m % 12 + 1, 1)
            as_of = nxt - timedelta(days=1)
            add(kind, kind, as_of, st, demo=False, detail=f"Дані по {m:02d}.{y} включно", period="щомісяця")
        else:
            add(kind, kind, None, "stale", False, "Файлу немає", "щомісяця")

    rank = {"fresh": 0, "due": 1, "stale": 2}
    overall = max((s["status"] for s in out), key=rank.get, default="stale")
    main = next((s for s in out if s["kind"] == "annual"), None)
    return {"checked_at": now.isoformat(timespec="seconds"), "overall": overall,
            "as_of": main["as_of"] if main else None,
            "counts": {k: sum(s["status"] == k for s in out) for k in rank},
            "sources": out}
