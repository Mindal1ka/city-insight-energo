"""Кеш відповідей, ETag/304, GZip, ковзне продовження токена."""

import time

import pytest
from fastapi.testclient import TestClient

from app import auth, httpcache, insight
from app.auth import User, make_token
from app.main import app, store


def _tok(role: str, **kw) -> str:
    return make_token(User(full_name="Т", position="Т", role=role, role_name=auth.ROLES[role]["name"], **kw))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("REQUIRE_LOGIN", "1")
    monkeypatch.setenv("RESPONSE_CACHE", "1")
    httpcache.bump()
    with TestClient(app) as c:
        yield c
    httpcache.bump()


def H(tok: str, **extra) -> dict:
    return {"Authorization": f"Bearer {tok}", **extra}


def test_gzip_and_cache_headers(client):
    r = client.get("/api/buildings", headers=H(_tok("energy_manager"), **{"Accept-Encoding": "gzip"}))
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert r.headers["cache-control"].startswith("private")
    assert "Authorization" in r.headers["vary"]
    assert r.headers["etag"]


def test_etag_304(client):
    tok = _tok("energy_manager")
    r = client.get("/api/summary", headers=H(tok))
    etag = r.headers["etag"]
    r2 = client.get("/api/summary", headers=H(tok, **{"If-None-Match": etag}))
    assert r2.status_code == 304 and r2.content == b""
    r3 = client.get("/api/summary", headers=H(tok, **{"If-None-Match": '"other"'}))
    assert r3.status_code == 200 and r3.json() == r.json()


def test_memo_hit_and_unauthenticated_never_served(client):
    tok = _tok("energy_manager")
    assert client.get("/api/sites", headers=H(tok)).headers["x-cache"] == "MISS"
    assert client.get("/api/sites", headers=H(tok)).headers["x-cache"] == "HIT"
    # кеш стоїть за перевіркою входу: без токена — 401, а не кешована відповідь
    assert client.get("/api/sites").status_code == 401
    assert client.get("/api/sites", headers=H("bad.token")).status_code == 401


def test_role_isolation(client):
    full = client.get("/api/sites", headers=H(_tok("energy_manager"))).json()
    assert client.get("/api/sites", headers=H(_tok("energy_manager"))).headers["x-cache"] == "HIT"
    own = store.buildings[0].id
    # facility_head не отримує повний список з кешу енергоменеджера
    fh = client.get("/api/sites", headers=H(_tok("facility_head", building_id=own)))
    assert fh.headers["x-cache"] == "MISS"
    assert all(i["id"] == own for i in fh.json()["items"])
    assert len(fh.json()["items"]) < len(full["items"])
    # ETag різний для різних скоупів навіть за однакового тіла
    a = client.get("/api/summary", headers=H(_tok("energy_manager"))).headers["etag"]
    b = client.get("/api/summary", headers=H(_tok("finance"))).headers["etag"]
    assert a != b


def test_write_invalidates(client, monkeypatch):
    mem: dict = {}
    monkeypatch.setattr(insight, "_read_limits", lambda: dict(mem))
    monkeypatch.setattr(insight, "_write_limits", lambda lim: mem.update(lim))
    tok = _tok("energy_manager")
    client.get("/api/summary", headers=H(tok))
    assert client.get("/api/summary", headers=H(tok)).headers["x-cache"] == "HIT"
    v = httpcache.version()
    r = client.put(f"/api/limits/{store.buildings[0].id}", headers=H(tok), json={"limit_uah_year": 1000})
    assert r.status_code == 200
    assert httpcache.version() == v + 1
    assert client.get("/api/summary", headers=H(tok)).headers["x-cache"] == "MISS"
    # невдалий запис кеш не чіпає
    v = httpcache.version()
    assert client.put("/api/limits/999999999", headers=H(tok), json={"limit_uah_year": 1}).status_code >= 400
    assert httpcache.version() == v


def test_spa_cache_headers(client):
    r = client.get("/")
    if r.status_code == 200 and r.headers.get("content-type", "").startswith("text/html"):
        assert r.headers["cache-control"] == "no-cache"


# --- /api/auth/refresh ---

def test_refresh_valid(client):
    tok = _tok("finance")
    r = client.post("/api/auth/refresh", headers=H(tok))
    assert r.status_code == 200
    body = r.json()
    assert auth.read_token(body["token"]).role == "finance"
    assert body["exp"] > time.time()
    assert auth.token_claims(body["token"])["iat"] == auth.token_claims(tok)["iat"]  # момент входу зберігається


def test_refresh_expired_and_tampered(client):
    u = User(full_name="Т", position="Т", role="finance", role_name="x")
    expired = make_token(u, ttl=-10)
    assert client.post("/api/auth/refresh", headers=H(expired)).status_code == 401
    tok = _tok("finance")
    body, sig = tok.split(".")
    tampered = body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + sig
    assert client.post("/api/auth/refresh", headers=H(tampered)).status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_respects_session_max(client):
    u = User(full_name="Т", position="Т", role="finance", role_name="x")
    old = make_token(u, auth_time=int(time.time()) - auth.SESSION_MAX + 5)
    assert auth.token_claims(old)["exp"] <= auth.token_claims(old)["iat"] + auth.SESSION_MAX
    ancient = make_token(u, auth_time=int(time.time()) - auth.SESSION_MAX - 100)
    assert auth.read_token(ancient) is None  # уже прострочений
    assert client.post("/api/auth/refresh", headers=H(ancient)).status_code == 401


def test_refresh_not_rate_limited(client):
    auth.reset_rate_limit()
    tok = _tok("energy_manager")
    for _ in range(auth.RATE_LIMIT + 5):
        assert client.post("/api/auth/refresh", headers=H(tok)).status_code == 200
    assert not auth._attempts  # продовження не торкається лічильника спроб входу
