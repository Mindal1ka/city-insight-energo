"""Свіжість даних і журнал завантажень."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import freshness, main
from app.auth import User, current_user
from app.main import app, store

EM = User(full_name="Тест", position="Тест", role="energy_manager", role_name="Провідний фахівець з енергозабезпечення")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # журнал пишемо в тимчасову теку, щоб не засмічувати data/
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    for f in ("openbudget_2273.csv", "spending_2273.csv"):
        (tmp_path / f).write_bytes((Path(store.data_dir) / f).read_bytes())
    app.dependency_overrides[current_user] = lambda: EM
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_freshness_shape(client):
    r = client.get("/api/freshness").json()
    keys = {s["key"] for s in r["sources"]}
    assert {"buildings", "meters", "sem", "openbudget", "spending"} <= keys
    assert any(k.startswith("annual") for k in keys)
    assert r["overall"] in ("fresh", "due", "stale")
    for s in r["sources"]:
        assert s["status"] in ("fresh", "due", "stale")
        assert s["how"] in ("upload", "script")


def test_status_by_age():
    today = date(2026, 11, 20)
    f = freshness.freshness(store, Path(store.data_dir), today=today)
    annual = next(s for s in f["sources"] if s["kind"] == "annual")
    assert annual["status"] == "fresh"
    late = freshness.freshness(store, Path(store.data_dir), today=date(2027, 3, 1))
    annual_late = next(s for s in late["sources"] if s["kind"] == "annual")
    assert annual_late["status"] == "stale"  # за 2027 звіту немає
    assert late["overall"] == "stale"


def test_history_has_demo_and_logs_rejected_upload(client):
    h = client.get("/api/uploads/history").json()
    assert h["demo"] > 0 and h["real"] == 0
    assert all(i["demo"] for i in h["items"])

    r = client.post("/api/upload", files={"file": ("нотатки.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    h = client.get("/api/uploads/history").json()
    assert h["real"] == 1
    top = h["items"][0]
    assert top["demo"] is False and top["ok"] is False and top["file"] == "нотатки.txt"
    assert "XLSX" in top["error"]


def test_history_forbidden_for_public_roles(client):
    app.dependency_overrides[current_user] = lambda: User(
        full_name="Ф", position="Ф", role="finance", role_name="Фінансовий орган")
    assert client.get("/api/uploads/history").status_code == 403
    assert client.get("/api/freshness").status_code == 200
