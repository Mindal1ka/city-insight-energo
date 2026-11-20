"""HTTP-шар продуктивності: мемоізація важких GET /api/*, ETag/304, Cache-Control, кеш статики.

Кеш відповідей ключується (шлях+запит, «скоуп» користувача з токена, версія даних):
  • скоуп = роль + об'єкт + управління — різні ролі НІКОЛИ не отримують чужу відповідь
    (фільтрація за роллю відбувається в самому ендпоінті, ми кешуємо вже відфільтрований результат);
  • версія даних збільшується після будь-якого успішного запису (POST/PUT/PATCH/DELETE /api/*,
    зокрема завантаження UMUNI → store.reload) — тож після запису всі кеші недійсні;
  • TTL на шлях: «живі» дані (телеметрія за поточну годину) — 30 с, довідкові — 10 хв.
RESPONSE_CACHE=0 вимикає мемоізацію (тести, що підмінюють дані/час, роблять це за замовчуванням).
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict

from starlette.requests import Request
from starlette.responses import Response

_lock = threading.Lock()
_version = 0
_cache: "OrderedDict[tuple, tuple[float, bytes, str]]" = OrderedDict()
MAX_ENTRIES = 600

# не кешуємо: вхід/профіль, вивантаження CSV, журнал завантажень (короткий і чутливий до запису)
NO_MEMO_PREFIX = ("/api/auth/", "/api/uploads/")
NO_MEMO_SUFFIX = (".csv",)

# TTL мемоізації (с) і заголовки для браузера, за префіксом шляху; перший збіг перемагає
_STATIC = ("/api/map", "/api/buildings", "/api/defects", "/api/summary", "/api/zones", "/api/departments",
           "/api/solar", "/api/trend", "/api/budget-real", "/api/spending", "/api/network", "/api/freshness")
_LIVE = ("/api/live", "/api/sites", "/api/energy-now", "/api/forecast", "/api/blackout", "/api/outages",
         "/api/generators", "/api/independence", "/api/insight", "/api/ses", "/api/report", "/api/appeals")


def ttl_for(path: str) -> int:
    if path.startswith(_STATIC):
        return 600
    if path.startswith(_LIVE):
        return 30
    return 30


def cache_control(path: str) -> str:
    # private: відповіді залежать від ролі — спільні проксі/CDN їх не зберігають
    if path.startswith(_STATIC):
        return "private, max-age=60, stale-while-revalidate=600"
    return "private, max-age=0, stale-while-revalidate=60"


def enabled() -> bool:
    return os.getenv("RESPONSE_CACHE", "1") != "0"


def version() -> int:
    return _version


def bump() -> None:
    """Дані змінилися (запис, перезавантаження store) — усі мемоізовані відповіді застаріли."""
    global _version
    with _lock:
        _version += 1
        _cache.clear()


def clear() -> None:
    with _lock:
        _cache.clear()


def scope(request: Request) -> str:
    """Скоуп доступу з токена (а не ПІБ): відповіді однакові для однакових прав."""
    from .auth import _bearer, read_token

    tok = _bearer(request)
    u = read_token(tok) if tok else None
    if u is None:
        return "anon"
    return f"{u.role}|{u.building_id}|{u.department}"


def _get(key: tuple) -> tuple[bytes, str] | None:
    with _lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        exp, body, ctype = hit
        if exp < time.monotonic():
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return body, ctype


def _put(key: tuple, ttl: int, body: bytes, ctype: str) -> None:
    with _lock:
        if key[2] != _version:  # поки рахували, дані змінилися — не кешуємо застаріле
            return
        _cache[key] = (time.monotonic() + ttl, body, ctype)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)


def _etag(sc: str, body: bytes) -> str:
    return '"' + hashlib.sha1(sc.encode("utf-8") + b"\0" + body).hexdigest()[:20] + '"'


def _not_modified(request: Request, etag: str) -> bool:
    inm = request.headers.get("if-none-match")
    if not inm:
        return False
    return any(t.strip().removeprefix("W/") == etag for t in inm.split(","))


async def middleware(request: Request, call_next):
    path = request.url.path
    method = request.method

    if not path.startswith("/api/"):
        resp = await call_next(request)
        if path.startswith("/_app/immutable/") and resp.status_code == 200:
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif method == "GET" and (resp.headers.get("content-type") or "").startswith("text/html"):
            resp.headers["Cache-Control"] = "no-cache"  # index.html завжди перевіряємо — нові збірки одразу
        return resp

    if method not in ("GET", "HEAD"):
        resp = await call_next(request)
        if method != "OPTIONS" and resp.status_code < 400 and not path.startswith("/api/auth/"):
            bump()
        return resp

    sc = scope(request)
    memo = enabled() and not path.startswith(NO_MEMO_PREFIX) and not path.endswith(NO_MEMO_SUFFIX)
    key = (path, str(request.url.query), _version, sc)
    hit = _get(key) if memo else None
    if hit is not None:
        body, ctype = hit
        headers = {"X-Cache": "HIT"}
    else:
        resp = await call_next(request)
        ctype = resp.headers.get("content-type") or ""
        if resp.status_code != 200 or "json" not in ctype:
            return resp
        chunks = [c async for c in resp.body_iterator]
        body = b"".join(chunks)
        if memo:
            _put(key, ttl_for(path), body, ctype)
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in ("content-length", "content-type")}
        headers["X-Cache"] = "MISS" if memo else "BYPASS"

    etag = _etag(sc, body)
    headers.update({"ETag": etag, "Cache-Control": cache_control(path), "Vary": "Authorization, Accept-Encoding"})
    if _not_modified(request, etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, status_code=200, media_type=None, headers={**headers, "Content-Type": ctype})
