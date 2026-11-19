"""Перевірки модуля СЕС (кейс 2.2)."""

from pathlib import Path

import pytest

from app import solar

E = solar.pvgis_monthly()


def test_pvgis_cache_offline():
    assert len(E) == 12
    assert 1000 < sum(E) < 1300  # Полтава: ~1150 кВт·год на 1 кВт за рік
    assert max(E) == E[6] or max(E) == E[7]  # пік — липень/серпень


def test_profiles_sum_to_one_and_schools_dip_in_summer():
    for cat in list(solar.SEASONAL_PROFILES) + ["Невідома"]:
        assert sum(solar.profile_shares(cat)) == pytest.approx(1.0)
    s = solar.profile_shares("Заклади освіти")
    assert s[6] < 0.5 * s[0]  # липень удвічі менше січня
    assert len(set(solar.profile_shares("Охорона здоров'я"))) == 1  # лікарні — рівний профіль


def test_hospital_by_hand():
    # лікарня: 120 000 кВт·год/рік, 3000 м², 3 поверхи
    r = solar.estimate(120000, 3000, 3, "Охорона здоров'я", tariff=8, capex_per_kw=30000, capex_fixed=60000)
    assert r.roof_area_m2 == pytest.approx(1000)
    assert r.kw_max_roof == pytest.approx(83.3)  # 1000 × 0,5 / 6 = 83,33 → вниз до 0,1
    # обмежує найсонячніший місяць: 10 000 × 0,6 / E_max
    kw = int(10000 * 0.6 / max(E) * 10) / 10
    assert r.kw_recommended == pytest.approx(kw)
    assert r.limited_by == "споживання"
    assert r.gen_kwh_year == pytest.approx(kw * sum(E))
    assert r.surplus_kwh_year == pytest.approx(0, abs=1e-6)
    assert r.self_consumed_kwh_year == pytest.approx(r.gen_kwh_year)
    assert r.capex_uah == pytest.approx(60000 + kw * 30000)
    assert r.payback_years == pytest.approx(r.capex_uah / (r.self_consumed_kwh_year * 8))


def test_never_exceeds_daytime_consumption():
    for cat in solar.SEASONAL_PROFILES:
        r = solar.estimate(50000, 2000, 2, cat)
        for g, c in zip(r.gen, r.cons):
            assert g <= solar.DAYTIME_SHARE * c + 1e-6


def test_school_smaller_than_hospital_with_same_annual():
    school = solar.estimate(100000, 5000, 2, "Заклади освіти")
    hosp = solar.estimate(100000, 5000, 2, "Охорона здоров'я")
    assert school.kw_recommended < hosp.kw_recommended  # літні канікули обмежують розмір
    assert school.coverage_pct < hosp.coverage_pct


def test_roof_cap_and_missing_floors():
    r = solar.estimate(10_000_000, 600, None, "Охорона здоров'я")
    assert r.floors_assumed and r.roof_area_m2 == pytest.approx(300)  # 2 поверхи за замовчуванням
    assert r.limited_by == "дах" and r.kw_recommended == pytest.approx(25.0)


def test_oversizing_creates_surplus():
    r = solar.estimate(100000, 5000, 2, "Заклади освіти", max_self_share=3.0)
    assert r.surplus_kwh_year > 0
    assert r.self_consumed_kwh_year + r.surplus_kwh_year == pytest.approx(r.gen_kwh_year)


@pytest.fixture(scope="module")
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app import solar_api
    from app.analytics import Store

    app = FastAPI()
    solar_api.set_store(Store(Path(__file__).resolve().parents[1] / "data"))
    app.include_router(solar_api.router)
    return TestClient(app)


def test_api_list_and_detail(client):
    d = client.get("/api/solar").json()
    assert d["params"]["tariff_uah_kwh"] == solar.TARIFF_UAH_KWH
    items, excluded = d["items"], d["excluded"]
    assert items and excluded
    ids = {i["id"] for i in items} | {e["id"] for e in excluded}
    assert len(ids) == len(items) + len(excluded)  # ніхто не загубився й не задвоївся
    pb = [i["payback_years"] for i in items]
    assert pb == sorted(pb) and [i["rank"] for i in items] == list(range(1, len(items) + 1))
    one = client.get(f"/api/solar/{items[0]['id']}").json()
    assert len(one["monthly"]) == 12 and one["assumptions"]
    assert sum(m["gen_kwh"] for m in one["monthly"]) == pytest.approx(one["item"]["gen_kwh_year"], abs=12)
    assert client.get(f"/api/solar/{excluded[0]['id']}").status_code == 404
    assert client.get("/api/solar/123456789").status_code == 404


def test_api_overrides_and_filter(client):
    a = client.get("/api/solar").json()["items"]
    b = client.get("/api/solar?tariff=16&capex=30000&category=Заклади освіти").json()["items"]
    assert b and all(i["category_short"] == "Заклади освіти" for i in b)
    a_by = {i["id"]: i for i in a}
    assert b[0]["payback_years"] < a_by[b[0]["id"]]["payback_years"]  # дорожчий тариф — швидша окупність


def test_no_backup_power_words(client):
    text = str(client.get("/api/solar").json()["params"]).lower()
    for w in ("генератор", "резервн"):
        assert w not in text
