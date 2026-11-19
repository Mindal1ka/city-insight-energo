"""Стан впровадження системи енергоменеджменту (СЕнМ), набір D2-05.

У репозиторії — лише знеособлений `data/sem_status.csv`: без ПІБ, телефонів, email
і без посилань (ТЗ: «ПІБ і телефони … не показуйте в рішенні»). Готує `scripts/sanitize_sources.py`.

Рядок вихідного файлу = суб'єкт надання інформації (організація з ЄДРПОУ) / його будівля.
Зв'язок з будівлями UMUNI — лише там, де впевнені (див. match_sem); решта лишається
не зіставленою, без вгадування.
"""

from __future__ import annotations

import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

SEM_CSV = "sem_status.csv"
FIELDS = ["row", "settlement", "subject", "function", "edrpou", "order_approved", "implementation",
          "certification", "plan", "plan_period", "declaration", "buildings", "heated_area",
          "monitoring_none", "monitoring_manual", "monitoring_auto", "monitoring_software", "mep"]

# індекси колонок аркуша «Лист1» (шапка у 2–3 рядках). 8 — ПІБ, 9 — телефон, 11/15/18/42 — посилання: НЕ читаємо
_COL = {"row": 0, "settlement": 4, "subject": 5, "function": 6, "edrpou": 7, "order_approved": 10,
        "implementation": 12, "certification": 13, "plan": 14, "plan_period": 16, "declaration": 17,
        "buildings": 24, "heated_area": 25, "monitoring_none": 30, "monitoring_manual": 31,
        "monitoring_auto": 32, "monitoring_software": 33, "mep": 41}
# перевірка, що структура файлу та сама (за фрагментами заголовків)
_EXPECT = {5: "назва суб'єкта", 7: "єдрпоу", 10: "наказ", 14: "план діяльності", 17: "декларацію",
           33: "програмний продукт"}
YES_NO = ("order_approved", "plan", "declaration", "mep")
NUM = ("buildings", "heated_area", "monitoring_none", "monitoring_manual", "monitoring_auto")


def _s(v) -> str:
    return re.sub(r"\s+", " ", "" if v is None else str(v)).strip()


def _yn(v) -> str:
    s = _s(v).lower()
    return "так" if s in ("так", "+", "yes") else "ні" if s in ("ні", "-", "no") else ""


def _num(v) -> str:
    if isinstance(v, (int, float)):
        return f"{v:g}"
    s = _s(v).replace(",", ".").replace(" ", "")
    return s if re.fullmatch(r"\d+(\.\d+)?", s) else ""  # дати/сміття → «немає даних»


def _edrpou(v) -> str:
    s = re.sub(r"\D", "", _s(v).split(".")[0])
    return s.zfill(8) if 5 <= len(s) <= 8 else ""  # ЄДРПОУ — 8 цифр; інше не зберігаємо


def sanitize_sem(xlsx: Path) -> list[dict]:
    """XLSX «Інформація щодо впровадження СЕМ» → рядки sem_status.csv без персональних даних."""
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["Лист1"] if "Лист1" in wb.sheetnames else wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    head = [" ".join(_s(rows[i][c]) if c < len(rows[i]) else "" for i in (1, 2)).lower() for c in range(43)]
    bad = [f"{c}: {t}" for c, t in _EXPECT.items() if t not in head[c]]
    if bad:
        raise ValueError(f"Невідома структура файлу СЕнМ (колонки {', '.join(bad)})")
    out = []
    for r in rows[4:]:
        r = list(r) + [None] * (43 - len(r))
        if not _s(r[_COL["subject"]]):
            continue
        d = {k: _s(r[i]) for k, i in _COL.items()}
        n = _num(r[0])
        d["row"] = str(int(float(n))) if n else ""
        d["edrpou"] = _edrpou(r[_COL["edrpou"]])
        for k in YES_NO:
            d[k] = _yn(r[_COL[k]])
        for k in NUM:
            d[k] = _num(r[_COL[k]])
        out.append(d)
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def load_sem(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------- зіставлення з будівлями UMUNI ----------
_BOILER = [
    r"полтавської міської ради", r"полтавської міської територіальної громади", r"полтавської області",
    r"полтавського району", r"комунальн\w* заклад\w*", r"комунальн\w* підприємств\w*", r"пмр",
]


def norm(s: str) -> str:
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[’'`ʼ\"«»„“”]", "", s)
    s = re.sub(r"№\s*", "№", s)
    s = re.sub(r"[^\w№]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def core(s: str) -> str:
    """Назва без типових «хвостів» (… Полтавської міської ради, Комунальний заклад …)."""
    n = norm(s)
    for p in _BOILER:
        n = re.sub(p, " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _f(v) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def _area_close(a: float | None, b: float | None, tol: float = 0.02) -> bool:
    return bool(a and b and a > 1 and b > 1 and abs(a - b) <= max(0.5, tol * max(a, b)))


def _numbers(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def match_sem(rows: list[dict], buildings: list) -> dict[int, dict]:
    """Повертає {id будівлі: рядок СЕнМ + match}. Правила (від найнадійнішого):
    1) «назва» — нормалізована назва збігається повністю (якщо таких будівель кілька — обираємо за площею);
    2) «назва без хвостів + площа» — збіг назви без типових хвостів і опалювана площа в межах 2%;
    2б) «назва без хвостів» — такий самий збіг, єдиний у реєстрі, але площа відрізняється;
    3) «схожа назва + площа» — схожість назв ≥ 0,75, однакові номери в назві (№ закладу) і площа в межах 2%.
    Кожна будівля і кожен рядок — не більше одного зіставлення; неоднозначні випадки не зіставляються.
    """
    bl = [(b, norm(b.name), core(b.name), b.heated_area) for b in buildings]
    by_norm: dict[str, list] = {}
    by_core: dict[str, list] = {}
    for t in bl:
        by_norm.setdefault(t[1], []).append(t)
        by_core.setdefault(t[2], []).append(t)
    used: set[int] = set()
    out: dict[int, dict] = {}

    def take(b, r, how):
        used.add(b.id)
        out[b.id] = {**r, "match": how}

    pending = []
    for r in rows:
        n, c, area = norm(r["subject"]), core(r["subject"]), _f(r.get("heated_area"))
        cand = [t for t in by_norm.get(n, []) if t[0].id not in used]
        if len(cand) > 1:
            cand = [t for t in cand if _area_close(area, t[3])]
        if len(cand) == 1:
            take(cand[0][0], r, "назва")
            continue
        pending.append((r, n, c, area))
    rest = []
    for r, n, c, area in pending:
        cand = [t for t in by_core.get(c, []) if t[0].id not in used and _area_close(area, t[3])]
        if c and len(cand) == 1:
            take(cand[0][0], r, "назва без хвостів + площа")
        else:
            rest.append((r, n, c, area))
    pending, rest = rest, []
    for r, n, c, area in pending:
        cand = [t for t in by_core.get(c, []) if t[0].id not in used]
        if c and len(cand) == 1 and len(by_core.get(c, [])) == 1:
            take(cand[0][0], r, "назва без хвостів")  # площа відрізняється — це окреме розходження даних
        else:
            rest.append((r, n, c, area))
    for r, n, c, area in rest:
        nums = _numbers(c)
        cand = []
        for t in bl:
            if t[0].id in used or not _area_close(area, t[3]) or _numbers(t[2]) != nums:
                continue
            sim = SequenceMatcher(None, c, t[2]).ratio()
            if sim >= 0.75:
                cand.append((sim, t))
        cand.sort(key=lambda x: -x[0])
        if len(cand) == 1 or (len(cand) > 1 and cand[0][0] - cand[1][0] >= 0.1):
            take(cand[0][1][0], r, "схожа назва + площа")
    return out


def sem_view(r: dict | None) -> dict | None:
    """Стан СЕнМ для картки будівлі (лише знеособлені поля)."""
    if not r:
        return None
    method = ("автоматично" if _f(r.get("monitoring_auto")) else "вручну" if _f(r.get("monitoring_manual"))
              else "не ведеться" if _f(r.get("monitoring_none")) else "")
    yn = lambda k: {"так": True, "ні": False}.get(r.get(k) or "")
    return {
        "subject": r.get("subject"), "edrpou": r.get("edrpou") or None, "function": r.get("function") or None,
        "settlement": r.get("settlement") or None,
        "order_approved": yn("order_approved"), "plan": yn("plan"), "plan_period": r.get("plan_period") or None,
        "declaration": yn("declaration"), "implementation": r.get("implementation") or None,
        "certification": r.get("certification") or None,
        "monitoring_method": method or None, "monitoring_software": r.get("monitoring_software") or None,
        "mep": yn("mep"), "heated_area_sem": _f(r.get("heated_area")), "match": r.get("match"),
    }


def sem_summary(rows: list[dict], matched: dict[int, dict], n_buildings: int) -> dict:
    """Зведення по громаді: скільки суб'єктів мають наказ / план / декларацію / сертифікацію."""
    subj: dict[str, list[dict]] = {}
    for r in rows:
        subj.setdefault(r.get("edrpou") or f"row{r.get('row')}", []).append(r)
    anyv = lambda lst, k: any(x.get(k) == "так" for x in lst)
    cnt = lambda k: sum(1 for lst in subj.values() if anyv(lst, k))
    software: dict[str, int] = {}
    for r in rows:
        if r.get("monitoring_software"):
            software[r["monitoring_software"]] = software.get(r["monitoring_software"], 0) + 1
    certified = sum(1 for lst in subj.values() if any(x.get("certification") and "не " not in x["certification"].lower()
                                                      for x in lst))
    return {
        "rows": len(rows), "subjects": len(subj),
        "order_approved": cnt("order_approved"), "plan": cnt("plan"), "declaration": cnt("declaration"),
        "certified": certified, "mep_rows": sum(1 for r in rows if r.get("mep") == "так"),
        "monitoring_software": software,
        "matched_rows": len(matched), "match_rate_rows": round(len(matched) / len(rows), 3) if rows else 0,
        "matched_buildings": len(matched), "buildings": n_buildings,
        "match_rate_buildings": round(len(matched) / n_buildings, 3) if n_buildings else 0,
        "match_by": {k: sum(1 for m in matched.values() if m.get("match") == k)
                     for k in ("назва", "назва без хвостів + площа", "назва без хвостів", "схожа назва + площа")},
        "note": "Зіставлення з будівлями UMUNI — за назвою (і площею); не зіставлені рядки не вгадуються. "
                "ПІБ, телефони й email вихідного файлу не зберігаються.",
    }
