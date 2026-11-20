"""SPA-маршрут не віддає файли поза зібраним фронтендом."""

import pytest
from fastapi.testclient import TestClient

from app.main import FRONT, app

c = TestClient(app)


@pytest.mark.skipif(not FRONT.exists(), reason="фронтенд не зібрано")
@pytest.mark.parametrize("url", [
    "/..%2F..%2F.env",
    "/..%2F..%2Fbackend%2Fapp%2Fauth.py",
    "/%2e%2e%2f%2e%2e%2fbackend%2fdata%2fses_registry.csv",
    "/C:%2FWindows%2Fwin.ini",
    "/%2Fetc%2Fpasswd",
])
def test_no_file_outside_frontend(url):
    r = c.get(url)
    assert r.status_code == 200
    assert "<!doctype html" in r.text.lower()[:200]  # лише index.html
    assert "DEMO_PASSWORD" not in r.text and "SECRET_KEY" not in r.text


@pytest.mark.skipif(not FRONT.exists(), reason="фронтенд не зібрано")
def test_real_static_file_served():
    assert c.get("/favicon.svg").status_code == 200
