"""Перевірки енергонезалежності: формула індексу, автономність, симуляція відключення, контракт API."""

import time

import pytest
from fastapi.testclient import TestClient

from app import independence as ind
from app import solar
from app.main import app

c = TestClient(app)
SUMMER = "?day=2026-06-05&hour=13"

ITEM_KEYS = {"id", "name", "address", "category_short", "critical", "has_ses", "ses_kw", "battery_kwh",
             "elec_kwh_year", "self_sufficiency_pct", "autonomy_hours", "autonomy_hours_with_sun", "index",
             "index_class", "potential_kw", "potential_self_sufficiency_pct"}
COMMUNITY_KEYS = {"sites", "ses_sites", "ses_kw_total", "battery_kwh_total", "elec_kwh_year_2025",
                  "solar_kwh_year_est", "self_sufficiency_pct", "autonomy_hours_median", "critical_sites_total",
                  "critical_with_ses", "critical_with_battery", "potential_kw", "potential_self_sufficiency_pct",
                  "potential_cost_uah"}


def test_index_formula_and_classes():
    assert ind.index_of(0, 0) == 0
    assert ind.index_of(ind.SELF_CAP_PCT, ind.AUTONOMY_CAP_H) == pytest.approx(100)
    assert ind.index_of(80, 100) == pytest.approx(100)  # обмеження зверху
    assert ind.index_of(20, 4) == pytest.approx(50)
    assert ind.class_of(0, False) == "відсутня"
    assert ind.class_of(1, True) == "низька"
    assert ind.class_of(40, True) == "середня"
    assert ind.class_of(70, True) == "висока"


def test_annual_self_no_station_and_battery_shift():
    assert ind.annual_self(100000, "Охорона здоров'я", 0, 0)["pct"] == 0
    big = ind.annual_self(100000, "Заклади освіти", 60, 0)
    with_bat = ind.annual_self(100000, "Заклади освіти", 60, 40)
    assert big["self_kwh"] <= 100000 * solar.DAYTIME_SHARE + 1e-6  # без акумулятора — лише денне споживання
    assert with_bat["self_kwh"] >= big["self_kwh"]
    assert with_bat["self_kwh"] + with_bat["lost_kwh"] == pytest.approx(with_bat["gen_kwh"])


def test_contract_list_fast():
    t = time.time()
    r = c.get("/api/independence")
    assert r.status_code == 200 and time.time() - t < 1.0
    d = r.json()
    assert d["demo"] is True and "now" in d
    assert COMMUNITY_KEYS <= set(d["community"])
    assert d["categories"] and {"category_short", "sites", "with_ses", "self_sufficiency_pct",
                                "autonomy_hours_median", "potential_kw"} <= set(d["categories"][0])
    assert d["community"]["sites"] == len(d["items"]) == 311
    for it in d["items"]:
        assert ITEM_KEYS <= set(it)
        assert 0 <= it["index"] <= 100
        assert it["index_class"] in {"висока", "середня", "низька", "відсутня"}
        assert it["critical"] == (it["category_short"] == "Охорона здоров'я")
        if it["autonomy_hours_with_sun"] is not None and it["autonomy_hours"] is not None:
            assert it["autonomy_hours_with_sun"] >= it["autonomy_hours"]
    # критичні — першими
    assert d["items"][0]["critical"]


def _items():
    return c.get("/api/independence" + SUMMER).json()["items"]


@pytest.mark.parametrize("pick", ["hospital_ses", "school_no_ses", "no_data"])
def test_detail_and_outage(pick):
    items = _items()
    sel = {
        "hospital_ses": lambda i: i["critical"] and i["has_ses"],
        "school_no_ses": lambda i: i["category_short"] == "Заклади освіти" and not i["has_ses"] and i["elec_kwh_year"],
        "no_data": lambda i: i["elec_kwh_year"] is None,
    }[pick]
    it = next(i for i in items if sel(i))
    d = c.get(f"/api/independence/{it['id']}" + SUMMER).json()
    assert d["demo"] is True and ITEM_KEYS <= set(d["item"])
    assert d["explain"] and 1 <= len(d["improve"]) <= 4
    assert {"text", "weights"} <= set(d["formula"])
    for imp in d["improve"]:
        assert {"action", "effect", "kw", "battery_kwh", "cost_uah", "payback_years", "priority"} <= set(imp)
        assert imp["priority"] in {"висока", "середня", "низька"}
    if pick == "no_data":
        assert d["item"]["index"] == 0 and d["item"]["autonomy_hours"] is None
    o = c.get(f"/api/sites/{it['id']}/outage?day=2026-06-05&start_hour=13&hours=6").json()
    assert o["demo"] is True and len(o["timeline"]) == 6 and o["timeline"][0]["hour"] == 13
    assert {"hour", "load_kwh", "solar_kwh", "battery_kwh_after", "from_battery_kwh", "covered"} <= set(o["timeline"][0])
    assert 0 <= o["survives_hours"] <= 6 and o["note"]
    if pick != "hospital_ses":
        assert o["survives_all"] is False


def test_outage_default_and_midnight_and_404():
    it = next(i for i in _items() if i["has_ses"])
    o = c.get(f"/api/sites/{it['id']}/outage").json()
    assert o["hours"] == 4 and len(o["timeline"]) == 4
    o = c.get(f"/api/sites/{it['id']}/outage?day=2026-06-05&start_hour=22&hours=4&soc=0").json()
    assert [t["hour"] for t in o["timeline"]] == [22, 23, 0, 1]
    assert o["survives_all"] is False  # порожній акумулятор уночі
    assert c.get("/api/sites/1/outage").status_code == 404
    assert c.get("/api/independence/1").status_code == 404
    assert c.get("/api/independence?day=bad").status_code == 400


def test_battery_recommendation_respects_connected_power():
    ev = {"work_load_kw": 40.0, "priority_rank": 1, "autonomy_hours": 1.0, "battery_kwh": 40.0, "connected_kw": 30}
    bo = ind._battery_offer(ev)
    assert bo["battery_kw"] <= 30 and bo["limited_by_connected"]
    assert bo["new_hours"] >= ind.TARGET_AUTONOMY_H[1]


def test_sites_contract_intact():
    d = c.get("/api/sites").json()
    assert {"demo", "now", "totals", "items"} <= set(d)
