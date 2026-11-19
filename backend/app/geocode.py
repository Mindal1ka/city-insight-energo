"""Геокодування адрес будівель без координат у UMUNI (OSM Nominatim) → data/geocode_cache.csv.

Запуск один раз офлайн:  python -m app.geocode            (дозапис: вже оброблені id пропускаються)
                         python -m app.geocode --redo-missing   (повторити лише ті, що «немає»)

Правила Nominatim: не частіше 1 запиту/с, власний User-Agent, результати кешуються одразу (скрипт можна
перервати й запустити знову). Каскад: точний будинок → лише вулиця → центр населеного пункту.
Точність: 'UMUNI' | 'будинок' | 'вулиця' | 'населений пункт' | 'немає'.
Санітарна перевірка: результат далі 30 км від центру Полтави відкидаємо.
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "data" / "geocode_cache.csv"
FIELDS = ["id", "address_query", "lat", "lon", "source", "precision"]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "city-insight-energo-hackathon/0.1"
VIEWBOX = "34.15,49.8,34.9,49.4"  # Полтавська міська громада з запасом (Пальчиківка, Валок — західніше 34,3) (lon1,lat1,lon2,lat2)
MIN_INTERVAL_S = 1.1  # ≥ 1 с між запитами (політика Nominatim)
CENTER = (49.589, 34.551)  # центр Полтави
MAX_KM = 30.0

PRECISIONS = ("UMUNI", "будинок", "вулиця", "населений пункт", "немає")
CITY = "Полтава"

# Села Полтавської міської громади (і частини міста, що в адресах пишуть як «с.»)
VILLAGES = {
    "Абазівка", "Андрушки", "Біологічне", "Бричківка", "Бугаївка", "Валок", "Вакуленці", "Верхоли", "Гожули",
    "Залізничне", "Івашки", "Івонченці", "Ковалівка", "Крутий Берег", "Макухівка", "Мильці", "Пальчиківка",
    "Розсошенці", "Сем'янівка", "Соснівка", "Супрунівка", "Тахтаулове", "Терешки", "Чорноглазівка", "Щербані",
    "Яківці",
}
VILLAGE_ALIASES = {"Валки": "Валок", "Тахтаулово": "Тахтаулове"}
POLTAVA_PARTS = {"Яківці", "Рибці"}  # якщо в селі не знайшли — шукаємо вулицю в самій Полтаві

# Відомі скорочення/описки в назвах вулиць UMUNI
STREET_FIXES = [
    (r"В\.\s*Тирнівськ", "Великотирнівськ"),
    (r"(?:вул\.?\s*)?К\.\s*Шосе", "Київське шосе"),
    (r"Г\.\s*Сталінграда", "Героїв Сталінграда"),
    (r"Европейськ", "Європейськ"),
    (r"Шевченко(?![^\W\d])", "Шевченка"),
    (r"Кучеренко(?![^\W\d])", "Кучеренка"),
    (r"Духова Миколи", "Генерала Духова"),
]

_last_request = 0.0


# ---------------- нормалізація адрес ----------------
def _apos(s: str) -> str:
    return re.sub(r"[’ʼ`‘]", "'", s)


def parse_address(address: str, name: str = "") -> dict:
    """Розбір адреси UMUNI → {settlement, name_village, street_type, street, house, type_explicit}."""
    s = _apos(address or "")
    s = re.sub(r"\([^)]*\)", " ", s)  # старі назви в дужках
    s = re.sub(r"[«»\"“”„]", " ", s)
    s = re.sub(r"\b3\d{4}\b", " ", s)  # поштові індекси
    s = re.sub(r"Полтавськ\w*\s+обл(?:асть|\.)?", " ", s, flags=re.I)
    s = re.sub(r"Полтавськ\w*\s+(?:р-н|район)\.?", " ", s, flags=re.I)

    settlement = None
    m = re.search(r"(?<![\w])[сС]\.\s*([А-ЯІЇЄҐ][\w'-]+(?:\s+Берег)?)", s)
    if m:
        settlement = m.group(1)
        s = s.replace(m.group(0), " ")
    settlement = VILLAGE_ALIASES.get(settlement, settlement)
    if not settlement:
        for v in VILLAGES:
            if re.search(rf"(?<![\w]){re.escape(v)}(?![\w])", s):
                settlement = v
                break
    if settlement:  # прибрати повтори назви села («…, Чорноглазівка, …»)
        for alias in [settlement] + [a for a, t in VILLAGE_ALIASES.items() if t == settlement]:
            s = re.sub(rf"(?:[сС]\.\s*)?(?<![\w]){re.escape(alias)}(?![\w])", " ", s)
    s = re.sub(r"(?:м\.\s*)?Полтав[аі](?![\w])", " ", s)
    s = re.sub(r"(?<![\w])Рибці(?![\w])", " ", s)

    name_village = None
    m = re.search(r"(?<![\w])с\.\s*([А-ЯІЇЄҐ][\w'-]+(?:\s+Берег)?)", _apos(name or ""))
    if m:
        name_village = VILLAGE_ALIASES.get(m.group(1), m.group(1))

    for pat, rep in STREET_FIXES:
        s = re.sub(pat, rep, s)

    street_type, explicit = "вулиця", False
    types = [  # (шаблон, тип, прапорці) — «в.» лише малою, бо «В.» — ініціал
        (r"(?<![\w])(?:проспект|просп\.)", "проспект", re.I),
        (r"(?<![\w])(?:провулок|провул\.|пров\.|пров(?![\w])|пр\.+)", "провулок", re.I),
        (r"(?<![\w])(?:бульвар|б-р\.?)", "бульвар", re.I),
        (r"(?<![\w])майдан(?![\w])", "майдан", re.I),
        (r"(?<![\w])площа(?![\w])", "площа", re.I),
        (r"(?<![\w])шосе(?![\w])", "шосе", re.I),
        (r"(?<![\w])(?:вулиця|вул\.?)(?![\w])", "вулиця", re.I),
        (r"(?<![\w])в\.", "вулиця", 0),
    ]
    for pat, t, fl in types:
        m = re.search(pat, s, flags=fl)
        if m:
            street_type, explicit = t, True
            s = s[: m.start()] + " " + s[m.end():]
            break
    s = re.sub(r"(?<![\w])(?:буд|б)\.?\s*(?=\d)", " ", s)

    # номер будинку — останнє число (з дробом і літерою)
    s = s.strip(" ,.;")
    house = None
    m = re.search(r"(\d+(?:\s*/\s*\d+)?(?:\s*-?\s*[А-ЯІЇЄҐа-яіїєґ](?![\w']))?)[\s,.;]*$", s)
    if m and not re.match(r"\d+-[^\W\d]{2,}", s[m.start():]):  # «1100-річчя Полтави» — частина назви
        house = re.sub(r"[\s-]", "", m.group(1)).lower()
        s = s[: m.start()]
    street = re.sub(r"(?<![\w])[А-ЯІЇЄҐ](?:\.\s*|\s+)", "", s)  # ініціали: «І.Мазепи» → «Мазепи»
    street = re.sub(r"[,.;]+", " ", street)
    street = re.sub(r"\s+", " ", street).strip()
    return {"settlement": settlement or CITY, "name_village": name_village, "street_type": street_type,
            "type_explicit": explicit, "street": street or None, "house": house or None}


def house_variants(house: str | None) -> list[str]:
    if not house:
        return []
    out = [house]
    digits = re.match(r"\d+", house).group(0)
    if digits != house:
        out.append(digits)  # без літери/дробу
    return out


def settlement_query(settlement: str) -> list[str]:
    if settlement == CITY:
        return [CITY]
    return [f"{settlement}, Полтавський район", settlement]


def query_plan(p: dict) -> list[tuple[str, str]]:
    """Список (запит, очікувана точність) у порядку спроб."""
    places = []
    if p["name_village"] and p["settlement"] == CITY:
        places.append(p["name_village"])  # «Будинок культури с.Івонченці», а в адресі «м.Полтава»
    places.append(p["settlement"])
    if p["settlement"] in POLTAVA_PARTS:
        places.append(CITY)
    plan: list[tuple[str, str]] = []
    if p["street"]:
        streets = [f"{p['street_type']} {p['street']}"]
        if not p["type_explicit"]:
            streets.append(p["street"])
        for place in places:
            for st in streets:
                for h in house_variants(p["house"]):
                    plan.append((f"{st} {h}, {place}", "будинок"))
        for place in places:
            for st in streets:
                plan.append((f"{st}, {place}", "вулиця"))
    for place in places:
        for q in settlement_query(place):
            plan.append((q, "населений пункт"))
    seen, out = set(), []
    for q, pr in plan:
        if q not in seen:
            seen.add(q)
            out.append((q, pr))
    return out


# ---------------- Nominatim ----------------
def km_from_center(lat: float, lon: float) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (CENTER[0], CENTER[1], lat, lon))
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _http_get(url: str) -> list[dict]:
    global _last_request
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "uk"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    finally:
        _last_request = time.monotonic()


def search(q: str, fetch=_http_get) -> list[dict]:
    params = {"q": q, "format": "jsonv2", "countrycodes": "ua", "viewbox": VIEWBOX, "bounded": 1,
              "accept-language": "uk", "addressdetails": 1, "limit": 3}
    return fetch(f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}")


def classify(res: dict, wanted: str) -> str:
    """Фактична точність результату (не краща за очікувану від запиту)."""
    addr = res.get("address") or {}
    cat, at = res.get("category"), res.get("addresstype")
    if addr.get("house_number") or at in ("building", "house") or cat == "building":
        got = "будинок"
    elif cat == "highway" or at in ("road", "street"):
        got = "вулиця"
    elif cat in ("place", "boundary"):
        got = "населений пункт"
    else:
        got = "вулиця" if addr.get("road") else "населений пункт"
    order = ["будинок", "вулиця", "населений пункт"]
    return order[max(order.index(got), order.index(wanted))]


def geocode(address: str, name: str = "", fetch=_http_get, memo: dict | None = None) -> dict:
    """→ {address_query, lat, lon, source, precision}. memo — кеш запитів у межах прогону."""
    memo = {} if memo is None else memo
    last_q = ""
    for q, wanted in query_plan(parse_address(address, name)):
        last_q = q
        if q not in memo:
            try:
                memo[q] = search(q, fetch)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                print(f"  ! помилка запиту «{q}»: {e}; пауза 10 с і повтор", file=sys.stderr)
                time.sleep(10)
                memo[q] = search(q, fetch)  # друга помилка — виняток, рядок не кешується
        for res in memo[q]:
            lat, lon = float(res["lat"]), float(res["lon"])
            if km_from_center(lat, lon) > MAX_KM:
                continue
            return {"address_query": q, "lat": round(lat, 6), "lon": round(lon, 6), "source": "nominatim",
                    "precision": classify(res, wanted)}
    return {"address_query": last_q, "lat": None, "lon": None, "source": "", "precision": "немає"}


# ---------------- кеш ----------------
def load_cache(path: Path = CACHE_FILE) -> dict[int, dict]:
    if not path.exists():
        return {}
    out = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                bid = int(r["id"])
            except (KeyError, ValueError):
                continue
            lat = float(r["lat"]) if r.get("lat") else None
            lon = float(r["lon"]) if r.get("lon") else None
            out[bid] = {"id": bid, "address_query": r.get("address_query", ""), "lat": lat, "lon": lon,
                        "source": r.get("source", ""), "precision": r.get("precision") or "немає"}
    return out


def _write_all(rows: dict[int, dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for bid in sorted(rows):
            w.writerow({k: ("" if rows[bid].get(k) is None else rows[bid][k]) for k in FIELDS})


def umuni_ok(lat, lon) -> bool:
    return bool(lat and lon) and km_from_center(lat, lon) <= MAX_KM


def run(buildings, path: Path = CACHE_FILE, fetch=_http_get, redo_missing: bool = False) -> dict[int, dict]:
    """buildings: об'єкти з id, name, address, lat, lon (координати UMUNI або None)."""
    rows = load_cache(path)
    if redo_missing:
        rows = {k: v for k, v in rows.items() if v["precision"] != "немає"}
    memo: dict[str, list] = {}
    todo = []
    for b in buildings:
        if umuni_ok(b.lat, b.lon):
            rows[b.id] = {"id": b.id, "address_query": "", "lat": b.lat, "lon": b.lon, "source": "UMUNI",
                          "precision": "UMUNI"}
        elif b.id not in rows or rows[b.id]["source"] == "UMUNI":
            todo.append(b)
    _write_all(rows, path)
    for i, b in enumerate(todo, 1):
        r = geocode(b.address, b.name, fetch, memo)
        rows[b.id] = {"id": b.id, **r}
        with path.open("a", encoding="utf-8", newline="") as f:  # одразу на диск — можна перервати
            csv.DictWriter(f, fieldnames=FIELDS).writerow(
                {k: ("" if rows[b.id].get(k) is None else rows[b.id][k]) for k in FIELDS})
        print(f"[{i}/{len(todo)}] {b.id} {r['precision']:<16} {r['address_query']}  ← {b.address}", flush=True)
    _write_all(rows, path)  # прибрати можливі дублікати після --redo-missing
    return rows


def coverage(rows: dict[int, dict]) -> dict[str, int]:
    c = {p: 0 for p in PRECISIONS}
    for r in rows.values():
        c[r["precision"]] = c.get(r["precision"], 0) + 1
    return c


def _registry_buildings():
    """Будівлі з реєстру/річних звітів з первинними координатами UMUNI."""
    from types import SimpleNamespace

    from .analytics import Store
    from .import_umuni import detect_kind, read_buildings

    store = Store(ROOT / "data")
    reg = {}
    for p in sorted((ROOT / "data").glob("*.xlsx")):
        if detect_kind(p) == "buildings":
            reg = {b.id: b for b in read_buildings(p)}
    return [SimpleNamespace(id=b.id, name=b.name, address=b.address,
                            lat=reg[b.id].lat if b.id in reg else None,
                            lon=reg[b.id].lon if b.id in reg else None) for b in store.buildings]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rows = run(_registry_buildings(), redo_missing="--redo-missing" in sys.argv)
    print("Покриття:", json.dumps(coverage(rows), ensure_ascii=False))
