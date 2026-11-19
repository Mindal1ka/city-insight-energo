"""Вхід, токени та матриця доступу ролей."""

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app, store

c = TestClient(app)
PW = "test-demo-pass"
EDU = {"Заклади освіти", "Дошкільні заклади"}
HEALTH = {"Охорона здоров'я"}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("DEMO_PASSWORD", PW)
    auth.reset_rate_limit()
    yield
    auth.reset_rate_limit()


def _first(cats=None, exclude=None):
    for b in store.buildings:
        if (cats is None or b.category_short in cats) and (exclude is None or b.category_short not in exclude):
            return b
    pytest.skip("немає об'єкта потрібної категорії")


def _login(role, **kw):
    body = {"full_name": "Іваненко Іван", "position": "Посада", "role": role, "password": PW, **kw}
    return c.post("/api/auth/login", json=body)


def _hdr(role, **kw):
    r = _login(role, **kw)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# --- вхід / me / roles ---

def test_roles_list():
    r = c.get("/api/auth/roles")
    assert r.status_code == 200
    ids = {x["id"] for x in r.json()}
    assert {"public", "energy_manager", "data_admin", "department", "facility_head", "finance"} <= ids
    for x in r.json():
        assert set(x) == {"id", "name", "description", "needs_building", "needs_department"}


def test_login_ok_and_me():
    r = _login("energy_manager")
    assert r.status_code == 200
    d = r.json()
    assert d["user"] == {"full_name": "Іваненко Іван", "position": "Посада", "role": "energy_manager",
                         "role_name": "Енергоменеджер міста", "building_id": None, "department": None}
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {d['token']}"})
    assert me.status_code == 200 and me.json() == d["user"]


def test_login_bad_password():
    r = c.post("/api/auth/login", json={"full_name": "А", "position": "Б", "role": "finance", "password": "x"})
    assert r.status_code == 401


def test_login_validation():
    assert _login("god").status_code == 422
    assert _login("public").status_code == 422
    assert _login("facility_head").status_code == 422                      # без об'єкта
    assert _login("facility_head", building_id=-999).status_code == 422    # неіснуючий об'єкт
    assert _login("department").status_code == 422
    assert _login("department", department="поліція").status_code == 422
    r = _login("department", department="Здоров’я")                   # типографський апостроф
    assert r.status_code == 200 and r.json()["user"]["department"] == "здоров'я"
    b = _first()
    r = _login("facility_head", building_id=b.id)
    assert r.status_code == 200 and r.json()["user"]["building_id"] == b.id


def test_me_without_token_and_tampered():
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/auth/me", headers={"Authorization": "Bearer abc.def"}).status_code == 401
    tok = _login("finance").json()["token"]
    body, sig = tok.split(".")
    payload = auth._b64d(body).replace(b'"finance"', b'"energy_manager"')
    forged = auth._b64e(payload) + "." + sig
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert c.get("/api/sites", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}x"}).status_code == 401


def test_token_expiry():
    u = auth.User(full_name="А", position="Б", role="energy_manager", role_name="x")
    assert auth.read_token(auth.make_token(u)) is not None
    expired = auth.make_token(u, ttl=-1)
    assert auth.read_token(expired) is None
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_rate_limit():
    for _ in range(auth.RATE_LIMIT):
        assert c.post("/api/auth/login", json={"full_name": "А", "position": "Б", "role": "finance",
                                               "password": "bad"}).status_code == 401
    assert _login("finance").status_code == 429  # навіть правильний пароль блокується на хвилину


# --- чисті правила ---

def _u(role, **kw):
    return auth.User(full_name="А", position="Б", role=role, role_name="x", **kw)


def test_rules_matrix():
    em, da, fin, pub = _u("energy_manager"), _u("data_admin"), _u("finance"), _u("public")
    edu, hl = _u("department", department="освіта"), _u("department", department="здоров'я")
    fh = _u("facility_head", building_id=7)
    for u in (em, da):
        assert auth.can_see_sensitive(u, "Інше", 1) and auth.can_see_finance(u, "Інше", 1)
    assert auth.can_see_sensitive(edu, "Дошкільні заклади", 1) and not auth.can_see_sensitive(edu, "Охорона здоров'я", 1)
    assert auth.can_see_sensitive(hl, "Охорона здоров'я", 1) and not auth.can_see_sensitive(hl, "Заклади освіти", 1)
    assert auth.can_see_sensitive(fh, "Інше", 7) and not auth.can_see_sensitive(fh, "Інше", 8)
    assert not auth.can_see_sensitive(fin, "Інше", 1) and auth.can_see_finance(fin, "Інше", 1)
    assert auth.can_see_ses(fin, "Інше", 1)
    assert not any(f(pub, "Заклади освіти", 1) for f in (auth.can_see_sensitive, auth.can_see_finance, auth.can_see_ses))
    assert auth.can_edit_ses(em, 1) and auth.can_edit_ses(fh, 7)
    assert not any(auth.can_edit_ses(u, 7) for u in (da, fin, edu, pub)) and not auth.can_edit_ses(fh, 8)
    # навіть без токена current_user не кидає
    assert auth.public_user().role == "public"


# --- ендпоінти ---

PROTECTED = ["/api/sites"]


def test_public_gets_401():
    b = _first()
    for url in PROTECTED + [f"/api/sites/{b.id}", f"/api/independence/{b.id}", f"/api/sites/{b.id}/outage"]:
        r = c.get(url)
        assert r.status_code == 401, url
        assert r.json() == {"detail": "Потрібен вхід"}
    assert c.get("/api/map").status_code == 200  # мапа лишається публічною


def test_public_independence_only_aggregates():
    r = c.get("/api/independence")
    assert r.status_code == 200
    d = r.json()
    assert d["items"] == []  # жодного об'єкта — лише громада й категорії
    assert d["community"]["self_sufficiency_pct"] is not None


def test_full_roles_see_everything():
    n = len(store.buildings)
    for role in ("energy_manager", "data_admin"):
        h = _hdr(role)
        assert len(c.get("/api/independence", headers=h).json()["items"]) == n
        assert len(c.get("/api/sites", headers=h).json()["items"]) == n


def test_department_filters():
    edu_b, other_b = _first(EDU), _first(exclude=EDU)
    h = _hdr("department", department="освіта")
    items = c.get("/api/independence", headers=h).json()["items"]
    assert items and all(i["category_short"] in EDU for i in items)
    assert all(i["category_short"] in EDU for i in c.get("/api/sites", headers=h).json()["items"])
    assert c.get(f"/api/independence/{edu_b.id}", headers=h).status_code == 200
    assert c.get(f"/api/sites/{edu_b.id}/outage", headers=h).status_code == 200
    assert c.get(f"/api/sites/{edu_b.id}", headers=h).status_code == 200
    assert c.get(f"/api/independence/{other_b.id}", headers=h).status_code == 403
    assert c.get(f"/api/sites/{other_b.id}/outage", headers=h).status_code == 403
    assert c.get(f"/api/sites/{other_b.id}", headers=h).status_code == 403


def test_facility_head_only_own():
    own, other = store.buildings[0], store.buildings[1]
    h = _hdr("facility_head", building_id=own.id)
    items = c.get("/api/independence", headers=h).json()["items"]
    assert [i["id"] for i in items] == [own.id]
    assert all(i["id"] == own.id for i in c.get("/api/sites", headers=h).json()["items"])
    assert c.get(f"/api/independence/{own.id}", headers=h).status_code == 200
    assert c.get(f"/api/independence/{other.id}", headers=h).status_code == 403
    assert c.get(f"/api/sites/{other.id}/outage", headers=h).status_code == 403


def test_finance_no_batteries():
    b = _first()
    h = _hdr("finance")
    items = c.get("/api/independence", headers=h).json()["items"]
    assert len(items) == len(store.buildings)
    assert all(i["battery_kwh"] is None and i["autonomy_hours"] is None for i in items)
    assert len(c.get("/api/sites", headers=h).json()["items"]) == len(store.buildings)
    assert c.get(f"/api/independence/{b.id}", headers=h).status_code == 403
    assert c.get(f"/api/sites/{b.id}/outage", headers=h).status_code == 403


def test_upload_roles():
    files = {"file": ("x.txt", b"hello", "text/plain")}
    assert c.post("/api/upload", files=files).status_code == 401
    for role, kw in (("finance", {}), ("department", {"department": "освіта"})):
        assert c.post("/api/upload", files=files, headers=_hdr(role, **kw)).status_code == 403
    for role in ("energy_manager", "data_admin"):
        # пройшли перевірку ролі → валідація файлу дає 400 (не XLSX)
        assert c.post("/api/upload", files=files, headers=_hdr(role)).status_code == 400


def test_login_by_account_and_no_guest(monkeypatch):
    from fastapi.testclient import TestClient

    from app import auth
    from app.main import app

    monkeypatch.setenv("REQUIRE_LOGIN", "1")
    monkeypatch.setattr(auth, "demo_password", lambda: "pw")
    c = TestClient(app)
    assert c.get("/api/ses").status_code == 401
    assert c.post("/api/auth/login", json={"login": "energo", "password": "bad"}).status_code == 401
    assert c.post("/api/auth/login", json={"login": "nobody", "password": "pw"}).status_code == 401
    r = c.post("/api/auth/login", json={"login": "energo", "password": "pw"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "energy_manager"
    h = {"Authorization": "Bearer " + r.json()["token"]}
    assert c.get("/api/zones", headers=h).status_code == 200
    assert c.get("/api/blackout", headers=h).status_code == 200
