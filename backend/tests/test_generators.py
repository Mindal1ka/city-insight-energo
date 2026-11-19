"""Облік генераторів: вартість, журнал пального, зведення витрат і права доступу."""

import pytest
from fastapi.testclient import TestClient

from app import auth, blackout
from app.main import app, store

c = TestClient(app)


def hdr(role, **kw):
    u = auth.User(full_name="Тест", position="тест", role=role, role_name=auth.ROLES[role]["name"], **kw)
    return {"Authorization": "Bearer " + auth.make_token(u)}


EM = hdr("energy_manager")
FIN = hdr("finance")


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(blackout, "DATA", tmp_path)
    monkeypatch.setattr(blackout, "GEN_FILE", tmp_path / "generators.csv")
    return tmp_path


def _with_generator() -> int:
    gens = blackout.read_generators()
    return next(b.id for b in store.buildings if blackout.generator_of(b, gens))


def test_capex_estimate_tiers():
    assert blackout.gen_capex_estimate(10) == round(10 * 18000 * 1.15, -3)
    assert blackout.gen_capex_estimate(30) == round(30 * 13000 * 1.15, -3)
    assert blackout.gen_capex_estimate(100) == round(100 * 9500 * 1.15, -3)


def test_summary_access_and_totals(tmp_data):
    assert c.get("/api/generators", headers=hdr("department", department="освіта")).status_code == 403
    assert c.get("/api/generators", headers=FIN).status_code == 200
    d = c.get("/api/generators", headers=EM).json()
    t = d["totals"]
    assert t["count"] == len(d["items"]) > 0
    assert t["capex_uah"] == round(sum(i["capex_uah"] for i in d["items"]))
    assert all(i["capex_source"] == blackout.MOCK and i["fuel_source"] == blackout.MOCK for i in d["items"])


def test_real_cost_and_fuel_log(tmp_data):
    bid = _with_generator()
    body = {"generator_kw": 30, "tank_l": 100, "cost_uah": 410000, "bought": "2025-11-03", "doc": "UA-2025-11-03-000001"}
    assert c.put(f"/api/generator/{bid}", json=body, headers=FIN).status_code == 403
    assert c.put(f"/api/generator/{bid}", json={**body, "bought": "03.11.2025"}, headers=EM).status_code == 422
    m = c.put(f"/api/generator/{bid}", json=body, headers=EM).json()["money"]
    assert m["capex_uah"] == 410000 and m["capex_source"] == "введено" and m["doc"] == body["doc"]

    year = blackout._now().year
    r = c.post(f"/api/generator/{bid}/fuel", json={"date": f"{year}-02-10", "liters": 200, "uah": 20400}, headers=EM)
    assert r.status_code == 200
    r = c.post(f"/api/generator/{bid}/fuel", json={"date": f"{year}-03-01", "liters": 100}, headers=EM).json()
    m = r["money"]
    assert m["fuel_source"] == "журнал" and m["fuel_year_l"] == 300
    assert m["fuel_year_uah"] == round(20400 + 100 * blackout.FUEL_PRICE_UAH_L)
    assert len(r["fuel_log"]) == 2

    assert c.post(f"/api/generator/{bid}/fuel", json={"date": "2099-01-01", "liters": 10}, headers=EM).status_code == 422
    assert c.post(f"/api/generator/{bid}/fuel", json={"date": f"{year}-03-01", "liters": 0}, headers=EM).status_code == 422

    eid = r["fuel_log"][0]["id"]
    r = c.delete(f"/api/generator/{bid}/fuel/{eid}", headers=EM).json()
    assert len(r["fuel_log"]) == 1
    assert c.delete(f"/api/generator/{bid}/fuel/{eid}", headers=EM).status_code == 404

    s = c.get("/api/generators", headers=EM).json()["totals"]
    assert s["capex_real"] == 1 and s["fuel_real"] == 1
