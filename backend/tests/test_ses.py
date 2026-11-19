"""Ефективність СЕС: класи K, баланс/дефіцит/надлишок, фінанси, PUT із збереженням у CSV, ролі."""

import csv
import time
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import auth, ses_api, solar
from app import efficiency as eff
from app import sites as sites_mod
from app.main import app, sites, store

c = TestClient(app)


def hdr(role, **kw):
    u = auth.User(full_name="Тест Тестович", position="тест", role=role, role_name=auth.ROLES[role]["name"], **kw)
    return {"Authorization": "Bearer " + auth.make_token(u)}


EM = hdr("energy_manager")
FIN = hdr("finance")

ITEM_KEYS = {"id", "name", "address", "category_short", "lat", "lon", "precision", "has_ses", "k", "k_class",
             "gen_kwh", "cons_kwh", "ses_kw", "battery_kwh", "capex_uah", "saved_uah_year", "payback_years"}
TOTAL_KEYS = {"objects", "with_ses", "effective", "deficit", "surplus", "no_ses", "no_data", "gen_kwh", "cons_kwh",
              "k", "capex_uah", "saved_uah_year", "grid_cost_uah_year"}
DETAIL_KEYS = {"demo", "building", "ses", "costs", "k", "k_class", "energy", "finance", "monthly", "meters", "sem",
               "can_edit"}


# ---------------- розрахунки ----------------

def test_k_class_thresholds():
    assert (eff.LOW, eff.HIGH) == (0.8, 1.2)
    assert eff.k_class(0.79, True) == "Не вистачає"
    assert eff.k_class(0.8, True) == "Ефективно"
    assert eff.k_class(0.7999, True) == "Ефективно"  # клас — за округленим K, який бачить користувач
    assert eff.k_class(1.0, True) == "Ефективно"
    assert eff.k_class(1.2, True) == "Ефективно"
    assert eff.k_class(1.21, True) == "Надлишок"
    assert eff.k_class(None, False) == "Без СЕС"
    assert eff.k_class(1.0, True, has_data=False) == "Немає даних"


def _bld(elec=100_000.0, cat="Охорона здоров'я", bid=900001):
    return SimpleNamespace(id=bid, category_short=cat, years={2025: SimpleNamespace(elec_kwh=elec)})


def _ses(k_year, elec=100_000.0, battery_kwh=0.0, launched="2025-01-01", total_uah=500_000.0):
    kw = k_year * elec / (sum(solar.pvgis_monthly()) * sites_mod.PV_DERATE)
    return {"total_kw": kw, "battery_kwh": battery_kwh, "battery_kw": battery_kwh / 2, "launched": launched,
            "costs": {"panels_uah": total_uah, "inverter_uah": 0, "batteries_uah": 0, "install_uah": 0,
                      "total_uah": total_uah}}


@pytest.mark.parametrize("k_year,cls", [(1.0, "Ефективно"), (0.5, "Не вистачає"), (1.5, "Надлишок")])
def test_balanced_deficit_surplus(k_year, cls):
    ev = eff.evaluate(_bld(), _ses(k_year), date(2025, 6, 15))
    assert ev["k"]["year"] == pytest.approx(k_year)
    assert ev["k_class"]["year"] == cls
    for p in ("day", "month", "year"):
        en = ev["energy"][p]
        assert en["gen_kwh"] == pytest.approx(en["self_kwh"] + en["surplus_kwh"])
        assert en["cons_kwh"] == pytest.approx(en["self_kwh"] + en["grid_kwh"])
        assert en["self_kwh"] <= min(en["gen_kwh"], en["cons_kwh"]) + 1e-6
    # рік = сума 12 місяців; місяць = червень
    assert ev["energy"]["year"]["gen_kwh"] == pytest.approx(sum(m["gen_kwh"] for m in ev["monthly"]))
    assert ev["energy"]["month"]["gen_kwh"] == pytest.approx(ev["monthly"][5]["gen_kwh"])
    assert len(ev["monthly"]) == 12


def test_battery_increases_self_consumption():
    d = date(2025, 6, 15)
    no_bat = eff.evaluate(_bld(), _ses(1.5), d)["energy"]["year"]["self_kwh"]
    bat = eff.evaluate(_bld(), _ses(1.5, battery_kwh=100), d)["energy"]["year"]["self_kwh"]
    assert bat > no_bat


def test_no_station_and_no_data():
    ev = eff.evaluate(_bld(), None, date(2025, 6, 15))
    assert ev["k_class"] == {"day": "Без СЕС", "month": "Без СЕС", "year": "Без СЕС"}
    assert ev["k"]["year"] is None and ev["finance"]["payback_years"] is None
    assert ev["finance"]["grid_cost_uah"]["year"] == pytest.approx(100_000 * eff.TARIFF_UAH_KWH)
    ev = eff.evaluate(_bld(elec=0.0), _ses(1.0), date(2025, 6, 15))
    assert ev["k_class"]["year"] == "Немає даних"


def test_finance_math():
    d = date(2025, 12, 31)
    ev = eff.evaluate(_bld(), _ses(1.0, launched="2025-01-01", total_uah=500_000), d, tariff=10.0)
    y, f = ev["energy"]["year"], ev["finance"]
    assert f["tariff_uah_kwh"] == 10.0
    assert f["saved_uah"]["year"] == pytest.approx(y["self_kwh"] * 10)
    assert f["grid_cost_uah"]["year"] == pytest.approx(y["grid_kwh"] * 10)
    assert f["saved_uah"]["since_launch"] == pytest.approx(f["saved_uah"]["year"])  # рівно рік роботи
    assert f["payback_years"] == pytest.approx(500_000 / f["saved_uah"]["year"])
    assert f["payback_progress_pct"] == pytest.approx(100 * f["saved_uah"]["since_launch"] / 500_000)
    # надлишок монетизується лише з явною ціною
    ev2 = eff.evaluate(_bld(), _ses(1.0), d, tariff=10.0, surplus_price=2.0)
    assert ev2["finance"]["saved_uah"]["year"] == pytest.approx(f["saved_uah"]["year"] + y["surplus_kwh"] * 2)
    # прогрес обмежено 999 %
    ev3 = eff.evaluate(_bld(), _ses(1.0, launched="2023-01-01", total_uah=100), d)
    assert ev3["finance"]["payback_progress_pct"] == 999
    # до запуску — нічого не заощаджено
    ev4 = eff.evaluate(_bld(), _ses(1.0, launched="2026-01-01"), d)
    assert ev4["finance"]["saved_uah"]["since_launch"] == 0


def test_demo_registry_shape():
    reg = sites.registry
    eligible = [b for b in store.buildings if eff.elec_2025(b) >= sites_mod.SES_MIN_KWH]
    demo = {bid: e for bid, e in reg.items() if e.get("source") == "ДЕМО"}
    assert 0.3 * len(eligible) <= len(demo) <= 0.5 * len(eligible)
    cats = {b.category_short for b in store.buildings if b.id in demo}
    assert len(cats) >= 3  # усі категорії, не лише освіта
    for e in demo.values():
        assert e["panel_w"] in sites_mod.PANEL_W_CHOICES
        assert e["total_kw"] == pytest.approx(e["panels_count"] * e["panel_w"] / 1000)
        assert e["inverter_kw"] >= e["total_kw"] / sites_mod.DC_AC_RATIO_MAX - 1e-9
        assert e["inverter_model"].split()[0] in ("Deye", "Huawei", "Growatt", "LuxPower") or "×" in e["inverter_model"]
        assert 0 <= e["battery_count"] <= 6
        assert e["battery_kwh"] == pytest.approx(e["battery_count"] * (e["battery_module_kwh"] or 0))
        assert "2023-01-01" <= e["launched"] <= "2025-12-31"
        co = e["costs"]
        assert co["total_uah"] == pytest.approx(co["panels_uah"] + co["inverter_uah"] + co["batteries_uah"]
                                                + co["install_uah"])
    ks = [eff.evaluate(b, reg[b.id], date(2025, 6, 1))["k"]["year"] for b in store.buildings if b.id in demo]
    assert min(ks) < 0.8 and max(ks) > 1.2 and any(0.8 <= k <= 1.2 for k in ks)


# ---------------- API ----------------

def test_list_contract_and_speed():
    for period in ("day", "month", "year"):
        r = c.get(f"/api/ses?period={period}", headers=EM)
        assert r.status_code == 200
        t = time.time()
        d = c.get(f"/api/ses?period={period}", headers=EM).json()
        assert time.time() - t < 0.3
        assert d["demo"] is True and d["period"] == period
        assert d["thresholds"] == {"low": 0.8, "high": 1.2}
        assert TOTAL_KEYS <= set(d["totals"])
        tt = d["totals"]
        assert tt["objects"] == len(d["items"]) == 311
        assert tt["effective"] + tt["deficit"] + tt["surplus"] + tt["no_ses"] + tt["no_data"] == 311
        for it in d["items"]:
            assert ITEM_KEYS <= set(it)
            assert it["k_class"] in eff.CLASSES
    assert c.get("/api/ses?period=week").status_code == 422
    assert c.get("/api/ses?day=bad").status_code == 400
    t = time.time()
    assert c.get("/api/ses?period=year&day=2026-07-01").status_code == 200  # без кешу
    assert time.time() - t < 0.5


def test_public_hides_per_object_ses():
    pub = c.get("/api/ses?period=year").json()
    em = c.get("/api/ses?period=year", headers=EM).json()
    assert pub["totals"] == em["totals"]
    assert em["totals"]["with_ses"] > 0
    for it in pub["items"]:
        for k in ("has_ses", "k", "k_class", "ses_kw", "battery_kwh", "capex_uah", "saved_uah_year", "payback_years"):
            assert it[k] is None
    bid = next(i["id"] for i in em["items"] if i["has_ses"] and i["battery_kwh"])
    d = c.get(f"/api/ses/{bid}").json()
    assert d["ses"] is None and d["costs"] is None and d["finance"] is None and d["can_edit"] is False
    assert d["k"] == {"day": None, "month": None, "year": None}
    assert d["energy"]["year"]["cons_kwh"] is not None and d["energy"]["year"]["gen_kwh"] is None


def test_finance_role_no_batteries():
    fin = c.get("/api/ses?period=year", headers=FIN).json()
    ses_items = [i for i in fin["items"] if i["has_ses"]]
    assert ses_items and all(i["battery_kwh"] is None and i["k"] is not None for i in ses_items)
    assert any(i["capex_uah"] for i in ses_items)
    bid = next(i["id"] for i in ses_items)
    d = c.get(f"/api/ses/{bid}", headers=FIN).json()
    assert DETAIL_KEYS <= set(d)
    assert d["ses"]["total_kw"] and all(d["ses"][k] is None for k in ses_api.BATTERY_FIELDS)
    assert d["finance"]["invested_uah"] and d["can_edit"] is False


def test_department_and_facility_head():
    em = {i["id"]: i for i in c.get("/api/ses?period=year", headers=EM).json()["items"]}
    edu = hdr("department", department="освіта")
    d = c.get("/api/ses?period=year", headers=edu).json()
    for it in d["items"]:
        if it["category_short"] in ("Заклади освіти", "Дошкільні заклади"):
            assert it["has_ses"] == em[it["id"]]["has_ses"] and it["battery_kwh"] == em[it["id"]]["battery_kwh"]
        else:
            assert it["has_ses"] is None and it["k"] is None
    own = next(i for i in em.values() if i["has_ses"])
    other = next(i for i in em.values() if i["has_ses"] and i["id"] != own["id"])
    fh = hdr("facility_head", building_id=own["id"])
    d = c.get(f"/api/ses/{own['id']}", headers=fh).json()
    assert d["ses"] is not None and d["can_edit"] is True and d["finance"] is not None
    d = c.get(f"/api/ses/{other['id']}", headers=fh).json()
    assert d["ses"] is None and d["can_edit"] is False
    assert c.get("/api/ses/1", headers=EM).status_code == 404


@pytest.fixture
def tmp_registry(tmp_path):
    old = sites_mod.REGISTRY_FILE
    sites_mod.REGISTRY_FILE = tmp_path / "ses_registry.csv"
    sites.reload()
    ses_api.invalidate()
    yield sites_mod.REGISTRY_FILE
    sites_mod.REGISTRY_FILE = old
    sites.reload()
    ses_api.invalidate()


PAYLOAD = {"panels_count": 40, "panel_w": 450, "inverter_model": "Deye SUN-20K-SG01HP3-EU-AM2", "inverter_kw": 20,
           "battery_count": 2, "battery_module_kwh": 10.24, "battery_kw": 10, "connected_kw": 50,
           "launched": "2024-05-01", "panels_uah": 180000, "inverter_uah": 70000, "batteries_uah": 330000,
           "install_uah": "", }


def test_put_roundtrip(tmp_registry):
    em = c.get("/api/ses?period=year", headers=EM).json()["items"]
    bid = next(i["id"] for i in em if not i["has_ses"] and i["cons_kwh"])
    assert c.put(f"/api/ses/{bid}", json=PAYLOAD).status_code == 401
    assert c.put(f"/api/ses/{bid}", json=PAYLOAD, headers=FIN).status_code == 403
    assert c.put(f"/api/ses/{bid}", json=PAYLOAD, headers=hdr("facility_head", building_id=bid + 1)).status_code == 403
    for bad in ({"panel_w": 50}, {"panels_count": -1}, {"inverter_kw": -5}, {"launched": "2099-01-01"},
                {"panels_uah": "abc"}):
        assert c.put(f"/api/ses/{bid}", json={**PAYLOAD, **bad}, headers=EM).status_code == 422, bad
    assert not tmp_registry.exists()

    r = c.put(f"/api/ses/{bid}", json=PAYLOAD, headers=hdr("facility_head", building_id=bid))
    assert r.status_code == 200
    d = r.json()
    assert d["ses"]["source"] == "введено" and d["ses"]["total_kw"] == 18.0 and d["ses"]["battery_kwh"] == 20.48
    assert d["costs"] == {"panels_uah": 180000, "inverter_uah": 70000, "batteries_uah": 330000,
                          "install_uah": None, "total_uah": 580000}
    assert d["k"]["year"] is not None and d["can_edit"] is True
    # CSV з українськими заголовками
    with tmp_registry.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["building_id"] == str(bid) and rows[0]["панелей_шт"] == "40"
    assert {"к-сть_акумуляторів", "ємність_модуля_кВт·год", "вартість_панелей_грн", "вартість_інвертора_грн",
            "вартість_акумуляторів_грн", "вартість_монтажу_грн"} <= set(rows[0])
    # перечитування з диска дає те саме; список оновився (кеш скинуто)
    reg = sites_mod.load_registry(store.buildings)
    assert reg[bid]["total_kw"] == 18.0 and reg[bid]["costs"]["total_uah"] == 580000
    it = next(i for i in c.get("/api/ses?period=year", headers=EM).json()["items"] if i["id"] == bid)
    assert it["has_ses"] and it["ses_kw"] == 18.0 and it["capex_uah"] == 580000
    # інші ендпоінти бачать нову станцію
    assert c.get(f"/api/sites/{bid}", headers=EM).json()["ses"]["total_kw"] == 18.0
    assert c.get(f"/api/independence/{bid}", headers=EM).status_code == 200
    # вкладений формат {ses, costs} теж приймається
    r = c.put(f"/api/ses/{bid}", json={"ses": {"panels_count": 10, "panel_w": 500}, "costs": {"install_uah": 1000}},
              headers=EM)
    assert r.status_code == 200 and r.json()["ses"]["total_kw"] == 5.0 and r.json()["costs"]["total_uah"] == 1000
    # порожні поля = станції немає → ДЕМО-станцію не повертаємо
    r = c.put(f"/api/ses/{bid}", json={}, headers=EM)
    assert r.status_code == 200 and r.json()["ses"] is None and r.json()["k_class"]["year"] == "Без СЕС"


def test_put_overrides_demo_station(tmp_registry):
    demo_id = next(bid for bid, e in sites.registry.items() if e.get("source") == "ДЕМО")
    r = c.put(f"/api/ses/{demo_id}", json={**PAYLOAD, "panels_count": 100}, headers=EM)
    assert r.status_code == 200 and r.json()["ses"]["source"] == "введено" and r.json()["ses"]["total_kw"] == 45.0
    other = next(bid for bid, e in sites.registry.items() if e.get("source") == "ДЕМО")
    assert other != demo_id  # решта ДЕМО-станцій на місці
