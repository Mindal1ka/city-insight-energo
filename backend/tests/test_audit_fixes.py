"""Виправлення за аудитом: finance без акумуляторів, «немає даних» замість нулів, котельні поза мапою,
звернення за адресатом, network/zones за доступом до всіх об'єктів (матриця ролей, як у test_auth.py)."""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from app import auth, blackout, insight
from app import efficiency as eff
from app.main import app, sites, store
from app.map_api import hidden_on_map
from app.ses_api import PUBLIC, access_level

c = TestClient(app)
EDU = {"Заклади освіти", "Дошкільні заклади"}
HEALTH = {"Охорона здоров'я"}


def hdr(role, **kw):
    u = auth.User(full_name="Тест", position="тест", role=role, role_name=auth.ROLES[role]["name"], **kw)
    return {"Authorization": "Bearer " + auth.make_token(u)}


EM, DA, FIN = hdr("energy_manager"), hdr("data_admin"), hdr("finance")
OSV, ZDR = hdr("department", department="освіта"), hdr("department", department="здоров'я")


def _user(h):
    return auth.read_token(h["Authorization"][7:])


def _no_data():
    for b in store.buildings:
        if eff.elec_2025(b) <= 0:
            return b
    pytest.skip("немає об'єкта без даних 2025")


def _ses_battery():
    for b in store.buildings:
        s = sites.registry.get(b.id)
        if eff.has_station(s) and (s.get("battery_kwh") or 0) > 0 and eff.elec_2025(b) > 0:
            return b
    pytest.skip("немає об'єкта зі СЕС і акумулятором")


# --- A. finance без акумуляторів / автономності / резервного живлення ---

def test_insight_finance_no_battery():
    b = _ses_battery()
    full = c.get(f"/api/insight/{b.id}", headers=EM).json()
    assert full["sizing"]["current_battery_kwh"] is not None
    assert any(h["soc_pct"] is not None for h in full["distribution"]["hourly"])
    d = c.get(f"/api/insight/{b.id}", headers=FIN).json()
    for k in insight.SIZING_BATTERY_FIELDS:
        assert d["sizing"][k] is None, k
    assert all(h["soc_pct"] is None for h in d["distribution"]["hourly"])
    assert d["battery_capacity_kwh"] is None and all(m["battery_kwh"] is None for m in d["months"])
    assert d["live"] is None or (d["live"]["soc_pct"] is None and d["live"]["battery_kw"] is None)
    lv = c.get("/api/live", headers=FIN).json()
    assert lv["totals"]["battery_kwh_now"] is None
    assert all(i["soc_pct"] is None and i["battery_kw"] is None for i in lv["items"])
    assert c.get("/api/live", headers=EM).json()["totals"]["battery_kwh_now"] is not None


def test_independence_finance_no_battery_fields():
    d = c.get("/api/independence", headers=FIN).json()
    for i in d["items"]:
        for k in ("battery_kw", "has_battery", "autonomy_with_sun_capped", "battery_kwh", "autonomy_hours"):
            assert i.get(k) is None, k
    for k in ("battery_sites", "battery_kwh_total", "autonomy_hours_median", "critical_with_battery"):
        assert d["community"][k] is None, k
    assert all(x["with_battery"] is None and x["autonomy_hours_median"] is None for x in d["categories"])
    assert d["community"]["self_sufficiency_pct"] is not None  # гроші/енергія лишаються
    em = c.get("/api/independence", headers=EM).json()
    assert em["community"]["battery_sites"] is not None
    assert any(i["has_battery"] is not None for i in em["items"])


def test_generators_finance_aggregates_only(tmp_path, monkeypatch):
    monkeypatch.setattr(blackout, "DATA", tmp_path)
    monkeypatch.setattr(blackout, "GEN_FILE", tmp_path / "generators.csv")
    full = c.get("/api/generators", headers=EM).json()
    assert full["items"] and full["totals"]["kw"] is not None
    d = c.get("/api/generators", headers=FIN).json()
    assert d["items"] is None and d["aggregates_only"] is True
    assert "kw" not in d["totals"] and d["totals"]["capex_uah"] == full["totals"]["capex_uah"]
    assert d["totals"]["fuel_year_uah"] == full["totals"]["fuel_year_uah"]
    for dep in d["departments"]:
        assert set(dep) == {"department", "count", "capex_uah", "fuel_year_uah"}
    names = {b.name for b in store.buildings}
    assert not any(n in str(d) for n in names)  # жодної назви закладу
    assert c.get("/api/generators", headers=OSV).status_code == 403


# --- B. немає даних ≠ 0 ---

def test_insight_no_data_is_null():
    b = _no_data()
    d = c.get(f"/api/insight/{b.id}", headers=EM).json()
    assert d["has_data"] is False
    assert d["monthly_kwh"] == [None] * 12
    assert all(m["cons_kwh"] is None and m["grid_kwh"] is None for m in d["months"])
    bu = d["budget"]
    if bu["source"] == insight.MOCK:
        assert bu["limit_uah"]["year"] is None and bu["limit_uah"]["month"] is None
    assert bu["paid_uah"]["year"] is None and bu["used_pct"]["year"] is None


def test_report_no_data_null_and_excluded():
    b = _no_data()
    d = c.get("/api/report", headers=EM).json()
    row = next(r for r in d["items"] if r["id"] == b.id)
    for k in insight.REPORT_NODATA_NULL:
        assert row[k] is None, k
    t = d["totals"]
    n_nd = sum(1 for x in store.buildings if eff.elec_2025(x) <= 0)
    assert t["no_data_count"] == n_nd > 0
    with_data = [r for r in d["items"] if r["cons_kwh"] is not None]
    assert t["cons_kwh"] == pytest.approx(sum(r["cons_kwh"] for r in with_data), abs=len(with_data))
    txt = c.get("/api/report.csv", headers=EM).content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(txt), delimiter=";"))
    r = next(x for x in rows if x[0] == str(b.id))
    assert r[4] == "" and r[9] == "" and r[10] == ""  # спожито, вартість, ліміт — порожні клітинки


def test_departments_no_data_count():
    d = c.get("/api/departments", headers=EM).json()
    n_nd = sum(1 for x in store.buildings if eff.elec_2025(x) <= 0)
    assert d["totals"]["no_data_count"] == n_nd


# --- C. котельні не на мапі ---

def test_boiler_houses_not_on_maps():
    boilers = [b for b in store.buildings if hidden_on_map(b)]
    if not boilers:
        pytest.skip("немає котелень")
    ids = {b.id for b in boilers}
    m = c.get("/api/map").json()
    assert not ids & {p["id"] for p in m["points"]}
    assert ids <= {p["id"] for p in m["not_on_map"]}  # у таблицях лишаються
    s = c.get("/api/ses", headers=EM).json()
    got = [i for i in s["items"] if i["id"] in ids]
    assert len(got) == len(ids) and all(i["lat"] is None and i["lon"] is None for i in got)
    for bid in ids:
        assert c.get(f"/api/ses/{bid}", headers=EM).json()["building"]["lat"] is None
    z = c.get("/api/zones", headers=EM).json()
    assert not ids & {m_["id"] for zz in z["items"] for m_ in zz["members"]}


# --- E. звернення ---

@pytest.fixture
def tmp_appeals(tmp_path, monkeypatch):
    monkeypatch.setattr(insight, "DATA", tmp_path)
    monkeypatch.setattr(insight, "APPEALS_FILE", tmp_path / "appeals.json")
    return tmp_path


def _first(cats):
    return next(b for b in store.buildings if b.category_short in cats)


def test_appeals_department_scope(tmp_appeals):
    edu_b, hl_b = _first(EDU), _first(HEALTH)
    a_edu = c.post("/api/appeals", json={"building_id": edu_b.id, "type": "repair"}, headers=EM).json()
    a_hl = c.post("/api/appeals", json={"building_id": hl_b.id, "type": "repair"}, headers=EM).json()
    assert a_edu["to"] == insight.D_EDU and a_hl["to"] == insight.D_HEALTH
    ids = lambda h: {a["id"] for a in c.get("/api/appeals", headers=h).json()["items"]}
    assert ids(OSV) == {a_edu["id"]} and ids(ZDR) == {a_hl["id"]}
    assert ids(EM) == ids(DA) == ids(FIN) == {a_edu["id"], a_hl["id"]}
    fh = hdr("facility_head", building_id=edu_b.id)
    assert ids(fh) == {a_edu["id"]}
    # PATCH: лише своє управління; finance — 403
    assert c.patch(f"/api/appeals/{a_hl['id']}", json={"status": "в роботі"}, headers=OSV).status_code == 403
    assert c.patch(f"/api/appeals/{a_edu['id']}", json={"status": "в роботі"}, headers=OSV).status_code == 200
    assert c.patch(f"/api/appeals/{a_edu['id']}", json={"status": "виконано"}, headers=FIN).status_code == 403
    assert c.patch(f"/api/appeals/{a_hl['id']}", json={"status": "виконано"}, headers=EM).status_code == 200
    # POST управлінням — лише щодо об'єктів своїх категорій
    assert c.post("/api/appeals", json={"building_id": hl_b.id}, headers=OSV).status_code == 403
    assert c.post("/api/appeals", json={"building_id": edu_b.id}, headers=OSV).status_code == 200
    other = next(b for b in store.buildings if b.id != edu_b.id)
    assert c.post("/api/appeals", json={"building_id": other.id}, headers=fh).status_code == 403


# --- F. network / zones ---

def test_network_pairs_only_with_access_to_both():
    for h in (OSV, ZDR, hdr("facility_head", building_id=store.buildings[0].id)):
        u = _user(h)
        bmap = {b.id: b for b in store.buildings}
        for p in c.get("/api/network", headers=h).json()["pairs"]:
            assert access_level(u, bmap[p["from_id"]]) != PUBLIC
            assert access_level(u, bmap[p["to_id"]]) != PUBLIC
    em = c.get("/api/network", headers=EM).json()
    osv = c.get("/api/network", headers=OSV).json()
    skip = {"pairs", "move_kw"}  # кількість видимих пар залежить від ролі
    assert ({k: v for k, v in em["totals"].items() if k not in skip}
            == {k: v for k, v in osv["totals"].items() if k not in skip})  # зведення громади однакове
    assert len(osv["pairs"]) <= len(em["pairs"])


def test_zones_ses_totals_need_access_to_all_members():
    em = c.get("/api/zones", headers=EM).json()
    assert all(z["with_ses"] is not None for z in em["items"])
    for h in (OSV, ZDR):
        for z in c.get("/api/zones", headers=h).json()["items"]:
            hidden = any(m["has_ses"] is None for m in z["members"])
            if hidden:
                assert all(z[k] is None for k in insight.ZONE_SES_FIELDS), z["id"]
            else:
                assert z["with_ses"] is not None and z["gen_kwh"] is not None, z["id"]
    fin = c.get("/api/zones", headers=FIN).json()  # finance має непублічний доступ до всіх
    assert all(z["with_ses"] is not None for z in fin["items"])
