"""Перевірки прогнозу СЕС (Open-Meteo + запасний PVGIS). Мережа замокана."""

import json
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import forecast as fc
from app import forecast_api

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=fc.KYIV)


def fake_raw(start: date = T0.date(), n_days: int = 3, sunny_day: int = 0) -> dict:
    times, gti, cloud, temp = [], [], [], []
    for d in range(n_days):
        for h in range(24):
            day = start + timedelta(days=d)
            times.append(f"{day.isoformat()}T{h:02d}:00")
            sun = max(0.0, 1 - abs(h - 12) / 5)  # 7…17
            sunny = d == sunny_day
            gti.append(round((500 if sunny else 80) * sun, 1))
            cloud.append(10 if sunny else 100)
            temp.append(2.0)
    days = [(start + timedelta(days=d)).isoformat() for d in range(n_days)]
    return {"hourly": {"time": times, "global_tilted_irradiance": gti, "cloud_cover": cloud,
                       "temperature_2m": temp},
            "daily": {"time": days, "sunshine_duration": [25200.0 if d == sunny_day else 0.0
                                                          for d in range(n_days)]}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "CACHE_FILE", tmp_path / "forecast_cache.json")
    monkeypatch.setattr(fc, "_mem", None)
    monkeypatch.setattr(fc, "_last_fail", 0.0)
    clock = {"t": T0}
    monkeypatch.setattr(fc, "now", lambda: clock["t"])
    calls = {"n": 0, "fail": False}

    def fetch():
        calls["n"] += 1
        if calls["fail"]:
            raise OSError("мережа недоступна")
        return fake_raw(clock["t"].date())

    monkeypatch.setattr(fc, "fetch_open_meteo", fetch)
    return clock, calls


def test_model_constants_and_temperature():
    assert fc.gen_kwh_per_kwp(0, 10) == 0
    assert fc.gen_kwh_per_kwp(1000, None) == pytest.approx(0.8 * (1 - 0.004 * 31.25))
    cold, hot = fc.gen_kwh_per_kwp(500, -5), fc.gen_kwh_per_kwp(500, 35)
    assert cold > 0.4 > hot  # холод підсилює, спека знижує


def test_calibration_vs_pvgis_effective_pr():
    # Ефективний PR моделі на типовій полуденній годині місяця близький до PVGIS E_m / H(i)_m
    for month, gti, t_air in ((1, 300, -5), (7, 800, 27)):
        model_pr = fc.gen_kwh_per_kwp(gti, t_air) / (gti / 1000)
        assert model_pr == pytest.approx(fc.pvgis_effective_pr(month), abs=0.06)


def test_pvgis_avg_day():
    assert fc.pvgis_avg_day(date(2026, 11, 19)) == pytest.approx(fc.solar.pvgis_monthly()[10] / 30)


def test_live_contract_and_cache(env):
    clock, calls = env
    r = fc.get_forecast(3)
    assert r["source"] == "Open-Meteo" and r["stale"] is False
    assert r["location"] == {"name": "Полтава", "lat": 49.589, "lon": 34.551}
    assert [d["label"] for d in r["days"]] == ["сьогодні", "завтра", "післязавтра"]
    d0 = r["days"][0]
    assert d0["date"] == "2026-11-19" and len(d0["hourly"]) == 24
    assert set(d0["hourly"][12]) >= {"hour", "gti_wm2", "cloud_pct", "temp_c", "gen_kwh_per_kwp"}
    assert d0["gen_kwh_per_kwp_day"] == pytest.approx(sum(h["gen_kwh_per_kwp"] for h in d0["hourly"]), abs=0.01)
    assert d0["ratio_to_normal"] == pytest.approx(d0["gen_kwh_per_kwp_day"] / d0["pvgis_avg_kwh_per_kwp_day"],
                                                  abs=0.02)
    assert d0["weather"] == "сонячно" and d0["sun_hours"] == 7.0
    assert r["days"][1]["weather"] == "похмуро"
    assert d0["gen_kwh_per_kwp_day"] > r["days"][1]["gen_kwh_per_kwp_day"]
    assert fc.CACHE_FILE.exists() and calls["n"] == 1
    # у межах години — з кешу, без мережі
    clock["t"] = T0 + timedelta(minutes=59)
    fc._mem = None  # навіть після перезапуску — з файлу
    fc.get_forecast(3)
    assert calls["n"] == 1
    clock["t"] = T0 + timedelta(minutes=61)
    fc.get_forecast(3)
    assert calls["n"] == 2


def test_network_fail_serves_stale_cache(env):
    clock, calls = env
    fc.get_forecast(3)
    calls["fail"] = True
    clock["t"] = T0 + timedelta(hours=26)  # наступного дня: «сьогодні» = 20.11
    r = fc.get_forecast(3)
    assert r["stale"] is True and r["source"] == "Open-Meteo" and r["error"]
    assert r["fetched_at"].startswith("2026-11-19T12:00")
    assert [d["date"] for d in r["days"]] == ["2026-11-20", "2026-11-21", "2026-11-22"]
    assert [d["source"] for d in r["days"]] == ["Open-Meteo", "Open-Meteo", "PVGIS (середнє)"]
    assert r["days"][0]["label"] == "сьогодні"


def test_no_cache_no_network_pvgis_fallback(env):
    _, calls = env
    calls["fail"] = True
    r = fc.get_forecast(3)
    assert r["source"] == "PVGIS (середнє)" and r["stale"] is False
    for d in r["days"]:
        assert d["gen_kwh_per_kwp_day"] == pytest.approx(d["pvgis_avg_kwh_per_kwp_day"], abs=0.02)
        assert d["ratio_to_normal"] == pytest.approx(1.0, abs=0.02)
        assert d["weather"] in ("сонячно", "мінлива хмарність", "похмуро")
        assert d["hourly"][0]["gen_kwh_per_kwp"] == 0  # уночі нуль
    # повторний запит одразу після збою не б'ється в мережу
    fc.get_forecast(3)
    assert calls["n"] == 1


def test_corrupt_cache_falls_back(env):
    _, calls = env
    calls["fail"] = True
    fc.CACHE_FILE.write_text("{не json", encoding="utf-8")
    r = fc.get_forecast(2)
    assert r["source"] == "PVGIS (середнє)" and len(r["days"]) == 2


def test_committed_sample_cache_is_valid():
    c = json.loads((fc.Path(__file__).resolve().parents[1] / "data" / "forecast_cache.json")
                   .read_text(encoding="utf-8"))
    days = fc.days_from_open_meteo(c["raw"], date.fromisoformat(c["raw"]["hourly"]["time"][0][:10]))
    assert len(days) >= 3 and all(d["source"] == "Open-Meteo" for d in days)


def test_endpoint(env):
    app = FastAPI()
    app.include_router(forecast_api.router)
    c = TestClient(app)
    r = c.get("/api/forecast?days=3")
    assert r.status_code == 200 and len(r.json()["days"]) == 3
    assert c.get("/api/forecast?days=0").status_code == 422
