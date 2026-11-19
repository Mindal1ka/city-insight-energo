"""Геокодування (мережа замокана) і публічна карта /api/map."""

import csv
import json
import math
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import geocode as gc
from app import map_api
from app.analytics import Store
from app.main import app

DATA = Path(__file__).resolve().parents[1] / "data"


# ---------------- розбір адрес ----------------
@pytest.mark.parametrize("addr,name,exp", [
    ("вул.Нагірна,1-Б", "", ("Полтава", "вулиця", "Нагірна", "1б")),
    ("пр..Хорольський,3", "", ("Полтава", "провулок", "Хорольський", "3")),
    ("просп.Першотравневий,20", "", ("Полтава", "проспект", "Першотравневий", "20")),
    ("вул.І.Мазепи 11", "", ("Полтава", "вулиця", "Мазепи", "11")),
    ("вул.К.Шосе,72", "", ("Полтава", "шосе", "Київське", "72")),
    ("вул.1100-річчя Полтави,9", "", ("Полтава", "вулиця", "1100-річчя Полтави", "9")),
    ("Соборний майдан,3", "", ("Полтава", "майдан", "Соборний", "3")),
    ("Монастирська вулиця, 7а", "", ("Полтава", "вулиця", "Монастирська", "7а")),
    ("36014, м. Полтава, вул. Івана Нечуя-Левицького, 4", "", ("Полтава", "вулиця", "Івана Нечуя-Левицького", "4")),
    ("Полтавська обл.,.Полтавський р-н, с.Валки, вул. Вишнева,14", "", ("Валок", "вулиця", "Вишнева", "14")),
    ("с. Чорноглазівка, вулиця Миру, 1д, Чорноглазівка, Полтавська область 38710", "",
     ("Чорноглазівка", "вулиця", "Миру", "1д")),
    ("Полтавська обл.,Полтавський р-н, Ковалівка, вул.Садова,2А", "", ("Ковалівка", "вулиця", "Садова", "2а")),
    ("С.Івонченці. Вул.М. Гаврилка74а", "", ("Івонченці", "вулиця", "Гаврилка", "74а")),
    ("с. Соснівка", "", ("Соснівка", "вулиця", None, None)),
])
def test_parse_address(addr, name, exp):
    p = gc.parse_address(addr, name)
    assert (p["settlement"], p["street_type"], p["street"], p["house"]) == exp


def test_query_plan_cascade_house_street_settlement():
    plan = gc.query_plan(gc.parse_address("вул.Центральна, буд.6а, с.Пальчиківка, Полтавський район"))
    qs = [q for q, _ in plan]
    assert qs == ["вулиця Центральна 6а, Пальчиківка", "вулиця Центральна 6, Пальчиківка",
                  "вулиця Центральна, Пальчиківка", "Пальчиківка, Полтавський район", "Пальчиківка"]
    assert [p for _, p in plan] == ["будинок", "будинок", "вулиця", "населений пункт", "населений пункт"]


def test_query_plan_village_from_name_first():
    plan = gc.query_plan(gc.parse_address("вул.Довга, буд.84а, м.Полтава", "Будинок культури с.Вакуленці"))
    assert plan[0][0] == "вулиця Довга 84а, Вакуленці"
    assert ("вулиця Довга 84а, Полтава", "будинок") in plan


# ---------------- Nominatim (замокано) ----------------
def _res(lat, lon, category="building", addresstype="building", house="1"):
    addr = {"road": "x"}
    if house:
        addr["house_number"] = house
    return {"lat": str(lat), "lon": str(lon), "category": category, "addresstype": addresstype, "address": addr}


class FakeNominatim:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, url):
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(url).query)
        assert qs["countrycodes"] == ["ua"] and qs["bounded"] == ["1"] and qs["format"] == ["jsonv2"]
        q = qs["q"][0]
        self.calls.append(q)
        return self.answers.get(q, [])


def test_geocode_house():
    f = FakeNominatim({"вулиця Соборності 36, Полтава": [_res(49.5893, 34.5537)]})
    r = gc.geocode("вул. Соборності, 36", fetch=f)
    assert r["precision"] == "будинок" and r["source"] == "nominatim" and r["lat"] == pytest.approx(49.5893)
    assert f.calls == ["вулиця Соборності 36, Полтава"]


def test_geocode_street_fallback_and_far_rejected():
    f = FakeNominatim({
        "вулиця Шкільна 4а, Абазівка": [_res(50.45, 30.52)],  # Київ — > 30 км, відкидаємо
        "вулиця Шкільна, Абазівка": [_res(49.52, 34.40, "highway", "road", house=None)],
    })
    r = gc.geocode("с.Абазівка, вул.Шкільна,4а", fetch=f)
    assert r["precision"] == "вулиця" and r["address_query"] == "вулиця Шкільна, Абазівка"
    assert "вулиця Шкільна 4, Абазівка" in f.calls  # спроба без літери


def test_geocode_house_query_returning_street_is_street_precision():
    f = FakeNominatim({"вулиця Довга 1, Полтава": [_res(49.6, 34.5, "highway", "road", house=None)]})
    assert gc.geocode("вул.Довга,1", fetch=f)["precision"] == "вулиця"


def test_geocode_settlement_and_none():
    f = FakeNominatim({"Терешки, Полтавський район": [_res(49.53, 34.42, "place", "village", house=None)]})
    r = gc.geocode("с. Терешки, вул. Невідома, 1", fetch=f)
    assert r["precision"] == "населений пункт"
    r = gc.geocode("вул. Невідома, 1", fetch=FakeNominatim({}))
    assert r["precision"] == "немає" and r["lat"] is None


def test_polite_client():
    assert gc.MIN_INTERVAL_S >= 1.0
    assert "@" not in gc.USER_AGENT


def test_run_is_resumable_and_keeps_umuni(tmp_path):
    path = tmp_path / "geocode_cache.csv"
    bs = [SimpleNamespace(id=1, name="А", address="вул. Соборності, 36", lat=None, lon=None),
          SimpleNamespace(id=2, name="Б", address="вул. Невідома, 5", lat=None, lon=None),
          SimpleNamespace(id=3, name="В", address="вул. Х, 1", lat=49.59, lon=34.55),
          SimpleNamespace(id=4, name="Г", address="вул. Соборності, 36", lat=34.56, lon=49.58)]  # переплутані
    f = FakeNominatim({"вулиця Соборності 36, Полтава": [_res(49.5893, 34.5537)]})
    rows = gc.run(bs, path, fetch=f)
    assert rows[3]["precision"] == "UMUNI" and rows[1]["precision"] == "будинок"
    assert rows[4]["precision"] == "будинок"  # хибні координати UMUNI → геокодуємо
    assert rows[2]["precision"] == "немає"
    assert gc.coverage(rows) == {"UMUNI": 1, "будинок": 2, "вулиця": 0, "населений пункт": 0, "немає": 1}
    with path.open(encoding="utf-8") as fh:
        rd = list(csv.DictReader(fh))
    assert list(rd[0]) == gc.FIELDS and len(rd) == 4
    f2 = FakeNominatim({})
    gc.run(bs, path, fetch=f2)
    assert f2.calls == []  # усе з кешу


# ---------------- карта ----------------
@pytest.fixture(scope="module")
def store(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    for p in DATA.glob("*.xlsx"):
        shutil.copy(p, d)
    base = Store(d)
    nogeo = [b for b in base.buildings if b.geo_source is None]
    rows = {nogeo[0].id: ("будинок", 49.60, 34.54), nogeo[1].id: ("вулиця", 49.58, 34.56),
            nogeo[2].id: ("населений пункт", 49.55, 34.45), nogeo[3].id: ("населений пункт", 49.55, 34.45)}
    with (d / "geocode_cache.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(gc.FIELDS)
        for bid, (prec, lat, lon) in rows.items():
            w.writerow([bid, "q", lat, lon, "nominatim", prec])
        w.writerow([nogeo[4].id, "q", "", "", "", "немає"])
    s = Store(d)
    s._test_ids = list(rows)
    return s


def test_store_fills_coords_but_has_coords_stays_umuni(store):
    by = {b.id: b for b in store.buildings}
    b = by[store._test_ids[0]]
    assert b.lat == 49.60 and b.geo_source == "nominatim" and b.geo_precision == "будинок"
    assert b.has_coords is False
    assert any(x.geo_source == "UMUNI" and x.has_coords for x in store.buildings)
    # координати UMUNI поза громадою (переплутані/інше місто) — дефект і не на карті як UMUNI
    bad = [x for x in store.buildings if x.has_coords and x.geo_source != "UMUNI"]
    assert bad and all(any("поза межами громади" in d["правило"] for d in x.defects) for x in bad)


def test_map_points_safe_fields_and_counts(store):
    m = map_api.build_map(store)
    assert m["counts"]["total"] == len(store.buildings)
    assert m["counts"]["on_map"] == len(m["points"]) == sum(
        v for k, v in m["counts"]["by_precision"].items() if k != "немає")
    assert sum(m["counts"]["by_precision"].values()) == m["counts"]["total"]
    assert m["counts"]["on_map"] + len(m["not_on_map"]) == m["counts"]["total"]
    for p in m["points"]:
        assert tuple(p) == map_api.POINT_FIELDS
    # БЕЗПЕКА: жодних полів про наявні станції / акумулятори / автономність
    banned = ("station", "battery", "batter", "autonom", "independ", "backup", "generator", "ses", "soc",
              "storage", "outage", "installed")
    keys = json.dumps([list(p) for p in m["points"]] + [list(x) for x in m["not_on_map"]])
    assert not any(w in keys.lower() for w in banned)
    assert "генератор" in m["note"] and "автономн" in m["note"]
    (s, w), (n, e) = m["bounds"]
    assert all(s <= p["lat"] <= n and w <= p["lon"] <= e for p in m["points"])


def test_map_jitter_settlement_points(store):
    m = map_api.build_map(store)
    pts = {p["id"]: p for p in m["points"]}
    a, b = pts[store._test_ids[2]], pts[store._test_ids[3]]
    assert a["approximate"] and b["approximate"] and (a["lat"], a["lon"]) != (b["lat"], b["lon"])
    for p in (a, b):
        dy = (p["lat"] - 49.55) * 111320
        dx = (p["lon"] - 34.45) * 111320 * math.cos(math.radians(49.55))
        assert 30 <= math.hypot(dx, dy) <= 150.5
    assert map_api.build_map(store)["points"] == m["points"]  # детерміновано
    assert not pts[store._test_ids[0]]["approximate"]


def test_map_values(store):
    m = map_api.build_map(store)
    with_kw = [p for p in m["points"] if p["solar_potential_kw"] is not None]
    assert all(p["solar_potential_kw"] >= 1 for p in with_kw)
    assert all(isinstance(p["data_ok"], bool) for p in m["points"])
    assert any(p["elec_kwh_2025"] for p in m["points"])


def test_api_map_endpoint(store):
    map_api.set_store(store)
    try:
        r = TestClient(app).get("/api/map")
    finally:
        map_api.set_store(None)
    assert r.status_code == 200
    j = r.json()
    assert set(j) >= {"points", "bounds", "counts", "note"}
    assert j["counts"]["on_map"] == len(j["points"])
