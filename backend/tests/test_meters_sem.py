"""Лічильники (D2-04) і стан СЕнМ (D2-05): знеособлення, зіставлення, правила валідатора Ф2.3-01."""

import csv
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import meters, sem
from app.analytics import Store
from app.main import app

DATA = Path(__file__).resolve().parents[1] / "data"
SRC = Path(__file__).resolve().parents[3] / "drive" / "Трек 2 Енергетичний менеджмент"
RULE_METER_NO_USE = "Лічильник електроенергії є, а споживання е/е за"
RULE_USE_NO_METER = "а лічильника електроенергії немає"

client = TestClient(app)


def _header(p: Path) -> list[str]:
    with p.open(encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


# ---------------- знеособлення ----------------
def test_csv_have_no_personal_columns():
    for name in (meters.METERS_CSV, sem.SEM_CSV):
        h = " ".join(_header(DATA / name)).lower()
        for bad in ("номер", "serial", "піб", "телефон", "phone", "email", "e-mail", "користувач", "посилання"):
            assert bad not in h, f"{name}: колонка «{bad}»"


def test_sem_csv_has_no_phones_or_emails():
    txt = (DATA / sem.SEM_CSV).read_text(encoding="utf-8")
    assert not re.search(r"\d{10,}", txt), "схоже на номер телефону"
    assert not re.search(r"\+380|\(0\d\d\)\s?\d", txt)
    assert "@" not in txt
    for r in sem.load_sem(DATA / sem.SEM_CSV):
        assert not r["edrpou"] or re.fullmatch(r"\d{8}", r["edrpou"])


def test_meters_csv_has_no_emails_and_no_long_numbers():
    txt = (DATA / meters.METERS_CSV).read_text(encoding="utf-8")
    assert "@" not in txt
    assert not re.search(r"\d{7,}", txt), "схоже на заводський номер"


def test_clean_model_drops_serial():
    assert meters.clean_model("ARATOR (С75205645)") == "ARATOR"
    assert meters.clean_model("calmex-u44115077-00") == "calmex"
    assert meters.clean_model("Apator 123456", "№ 123456") == "Apator"
    assert meters.clean_model("NIK 2303 ART T.1800.МС.21") == "NIK 2303 ART T.1800.МС.21"


@pytest.mark.skipif(not (SRC / "Лічильники.xlsx").exists(), reason="немає вихідного XLSX")
def test_no_serial_from_source_in_csv():
    import openpyxl

    ws = openpyxl.load_workbook(SRC / "Лічильники.xlsx", read_only=True, data_only=True)["Лічильники"]
    rows = list(ws.iter_rows(values_only=True))
    col = [re.sub(r"\s+", " ", str(c or "")).strip() for c in rows[0]].index("Номер лічильника")
    flat = re.sub(r"[^\w]", "", (DATA / meters.METERS_CSV).read_text(encoding="utf-8"))
    serials = {re.sub(r"[^\w]", "", str(r[col] or "")).lstrip("№") for r in rows[1:]}
    leaks = [s for s in serials if len(re.sub(r"\D", "", s)) >= 5 and s in flat]
    assert not leaks


@pytest.mark.skipif(not SRC.exists(), reason="немає вихідних XLSX")
def test_sanitize_script_reproduces_csv(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sanitize", DATA.parent / "scripts" / "sanitize_sources.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.main(["--src", str(SRC), "--out", str(tmp_path)]) == 0
    for name in (meters.METERS_CSV, sem.SEM_CSV):
        assert (tmp_path / name).read_text(encoding="utf-8") == (DATA / name).read_text(encoding="utf-8")


# ---------------- лічильники ----------------
def test_meters_ids_overlap_registry():
    s = client.get("/api/summary").json()
    ms = s["meters_summary"]
    assert ms["total"] > 1000 and ms["electricity"] > 400
    assert ms["by_resource"]["Електроенергія"] == ms["electricity"]
    assert ms["meter_buildings_not_in_registry"] == 0
    assert ms["buildings_with_meters"] > 290


def test_building_card_shows_meters():
    d = client.get("/api/buildings/9591").json()
    m = d["meters"]
    assert m["total"] >= 1 and m["electricity"] >= 1
    assert sum(m["by_resource"].values()) == m["total"]
    assert {"technical", "transit"} <= m.keys()
    lst = client.get("/api/buildings").json()
    assert "meters" not in lst[0]  # у списку — лише в повній картці


def test_meter_rules_in_defects():
    d = client.get("/api/defects").json()
    new = [x for x in d if x["набір"] == "Лічильники"]
    assert new, "немає дефектів за лічильниками"
    for x in new:
        assert x["тип"] == "дефект даних" and x["що_робити"] and x["будівля_id"]
    assert any(x["правило"].startswith(RULE_METER_NO_USE) for x in new)


def _store(tmp_path, meter_rows):
    for p in DATA.glob("*.xlsx"):
        shutil.copy(p, tmp_path / p.name)
    meters.write_csv(meter_rows, tmp_path / meters.METERS_CSV)
    return Store(tmp_path)


def test_meter_rules_both_directions(tmp_path):
    base = Store(DATA)
    y = base.base_year
    with_el = next(b for b in base.buildings if y in b.years and b.years[y].elec_kwh)
    no_el = next(b for b in base.buildings if not (y in b.years and b.years[y].elec_kwh))
    row = lambda bid, res: {"building_id": bid, "building": "", "meter_id": "1", "model": "", "resource": res,
                            "type": "Зростаючий", "technical": "", "transit": ""}
    st = _store(tmp_path, [row(with_el.id, "Холодна вода"), row(no_el.id, meters.ELECTRICITY)])
    rules = {(d["будівля_id"], d["правило"]) for d in st.defects if d["набір"] == "Лічильники"}
    assert (with_el.id, f"Споживання е/е за {y} є, а лічильника електроенергії немає") in rules
    assert (no_el.id, f"Лічильник електроенергії є, а споживання е/е за {y} немає") in rules


def test_no_meter_rules_without_csv(tmp_path):
    for p in DATA.glob("*.xlsx"):
        shutil.copy(p, tmp_path / p.name)
    st = Store(tmp_path)
    assert not [d for d in st.defects if d["набір"] == "Лічильники"]
    assert st.summary()["meters_summary"] is None and st.summary()["sem_summary"] is None
    assert st.view(st.buildings[0], full=True)["meters"] is None


# ---------------- СЕнМ ----------------
def test_sem_summary_no_subject_has_order_plan_declaration():
    ss = client.get("/api/summary").json()["sem_summary"]
    assert ss["subjects"] > 100
    assert ss["order_approved"] == ss["plan"] == ss["declaration"] == ss["certified"] == 0  # як і в ТЗ
    assert 0 < ss["match_rate_rows"] <= 1 and ss["matched_rows"] == sum(ss["match_by"].values())


def test_sem_on_building_card():
    st = Store(DATA)
    bid = next(iter(st.sem_by_bid))
    s = client.get(f"/api/buildings/{bid}").json()["sem"]
    assert s["order_approved"] is False and s["plan"] is False and s["declaration"] is False
    assert s["edrpou"] and s["monitoring_method"] and s["match"]
    for k in s:
        assert "піб" not in k.lower() and "phone" not in k.lower()


def test_sem_matching_rules():
    B = lambda i, name, area: SimpleNamespace(id=i, name=name, heated_area=area)
    blds = [B(1, "Гімназія №12 Полтавської міської ради", 1976.1),
            B(2, "Бібліотека-філіал №1", 399.8),
            B(3, "Бібліотека-філіал №10", 417.3),
            B(4, "Ліцей №5", 1000.0)]
    R = lambda name, area: {"row": name, "subject": name, "heated_area": str(area)}
    m = sem.match_sem([R("Гімназія №12", 1976.1), R("Бібліотека-філіал №1", 431.6),
                       R("Ліцей №6", 1000.0), R("Невідомий заклад", 50)], blds)
    assert m[1]["match"] == "назва без хвостів + площа"
    assert m[2]["match"] == "назва" and 3 not in m
    assert 4 not in m  # інший номер закладу — не зіставляємо, навіть за однакової площі
    assert len(m) == 2
