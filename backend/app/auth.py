"""Ролі та вхід: підписаний токен (stdlib: hmac + hashlib + base64 + json), перевірка прав на бекенді.

Токен: base64url(json-корисне навантаження) + "." + base64url(HMAC-SHA256), термін дії — 12 год.
SECRET_KEY і DEMO_PASSWORD беруться з оточення або з backend/.env (без нових залежностей).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable, Container

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

log = logging.getLogger("energo.auth")

ROOT = Path(__file__).resolve().parents[1]
TOKEN_TTL = 12 * 3600  # 12 год

ROLES: dict[str, dict] = {
    "public": {"name": "Мешканець / журналіст / депутат",
               "description": "Без входу: мапа, зведені цифри громади, ефект інвестицій у СЕС (агреговано)",
               "needs_building": False, "needs_department": False},
    "energy_manager": {"name": "Енергоменеджер міста",
                       "description": "Усі дані; редагує дані СЕС і вартість будь-якого об'єкта; завантажує UMUNI",
                       "needs_building": False, "needs_department": False},
    "data_admin": {"name": "Адміністратор даних UMUNI",
                   "description": "Усе на перегляд; завантаження UMUNI; якість даних",
                   "needs_building": False, "needs_department": False},
    "department": {"name": "Управління освіти / охорони здоров'я",
                   "description": "Повні дані своїх категорій (освіта+садочки або охорона здоров'я), решта — як public",
                   "needs_building": False, "needs_department": True},
    "facility_head": {"name": "Керівник закладу",
                      "description": "Повні дані свого об'єкта, редагує дані СЕС свого об'єкта; решта — як public",
                      "needs_building": True, "needs_department": False},
    "finance": {"name": "Фінансовий орган",
                "description": "Фінанси/окупність/витрати всіх об'єктів, без акумуляторів і автономності",
                "needs_building": False, "needs_department": False},
}

FULL_ACCESS = {"energy_manager", "data_admin"}

DEPARTMENT_CATEGORIES: dict[str, set[str]] = {
    "освіта": {"Заклади освіти", "Дошкільні заклади"},
    "здоров'я": {"Охорона здоров'я"},
}


# --- налаштування з оточення / backend/.env ---

def _read_dotenv(path: Path = ROOT / ".env") -> dict[str, str]:
    """Простий розбір KEY=VALUE (коментарі #, лапки навколо значення)."""
    out: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip().removeprefix("export ").strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k] = v
    return out


# backend/.env має пріоритет над .env у корені репозиторію; змінні оточення — над обома
_DOTENV = {**_read_dotenv(ROOT.parent / ".env"), **_read_dotenv(ROOT / ".env")}


def _env(name: str) -> str | None:
    v = os.environ.get(name)
    if v is None:
        v = _DOTENV.get(name)
    return v or None


_SECRET = _env("SECRET_KEY")
if not _SECRET:
    _SECRET = secrets.token_hex(32)
    log.warning("SECRET_KEY не задано — згенеровано випадковий ключ (токени зникнуть після перезапуску)")
SECRET_KEY: bytes = _SECRET.encode("utf-8")

_warned_pw = False


def demo_password() -> str | None:
    """Спільний демо-пароль лише з оточення / .env. Пароля в коді немає: без DEMO_PASSWORD вхід вимкнено."""
    global _warned_pw
    pw = _env("DEMO_PASSWORD")
    if pw:
        return pw
    if not _warned_pw:
        log.warning("DEMO_PASSWORD не задано — вхід вимкнено (працює лише публічний режим). Задайте його в .env")
        _warned_pw = True
    return None


def check_password(given: str) -> bool:
    pw = demo_password()
    if not pw:
        return False
    return hmac.compare_digest(given.encode("utf-8"), pw.encode("utf-8"))


# --- користувач ---

class User(BaseModel):
    full_name: str
    position: str
    role: str
    role_name: str
    building_id: int | None = None
    department: str | None = None  # 'освіта' | "здоров'я"


def public_user() -> User:
    return User(full_name="", position="", role="public", role_name=ROLES["public"]["name"])


def norm_department(dep: str | None) -> str | None:
    """Приводимо апостроф (’ ʼ `) до ' і регістр до нижнього."""
    if dep is None:
        return None
    d = dep.strip().lower()
    for ch in ("’", "ʼ", "`", "‘"):
        d = d.replace(ch, "'")
    return d


# --- токени ---

def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(body: str) -> str:
    return _b64e(hmac.new(SECRET_KEY, body.encode("ascii"), hashlib.sha256).digest())


def make_token(user: User, ttl: int = TOKEN_TTL) -> str:
    payload = user.model_dump()
    payload["exp"] = int(time.time()) + ttl
    body = _b64e(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def read_token(token: str) -> User | None:
    """Перевіряє підпис і термін дії; None — якщо токен підроблений/прострочений/битий."""
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        data = json.loads(_b64d(body))
        if int(data.pop("exp")) < time.time():
            return None
        user = User(**data)
        if user.role not in ROLES or user.role == "public":
            return None
        user.role_name = ROLES[user.role]["name"]
        return user
    except Exception:
        return None


def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or ""
    if h[:7].lower() == "bearer ":
        return h[7:].strip() or None
    return None


# --- залежності FastAPI ---

def current_user(request: Request) -> User:
    """Поточний користувач; без токена або з невалідним — public (ніколи не кидає)."""
    tok = _bearer(request)
    return (read_token(tok) if tok else None) or public_user()


def require(*roles: str) -> Callable[..., User]:
    """Depends(require('energy_manager', ...)): public → 401, інша роль → 403."""
    allowed = set(roles)

    def dep(user: User = Depends(current_user)) -> User:
        if user.role == "public":
            raise HTTPException(401, "Потрібен вхід")
        if allowed and user.role not in allowed:
            raise HTTPException(403, "Недостатньо прав для цієї дії")
        return user

    return dep


require_login = require()  # будь-яка роль, крім public


# --- правила доступу по об'єкту ---

def _dept_has(user: User, category_short: str | None) -> bool:
    return bool(category_short) and category_short in DEPARTMENT_CATEGORIES.get(user.department or "", set())


def _own(user: User, building_id: int | None) -> bool:
    return user.building_id is not None and building_id is not None and int(building_id) == user.building_id


def can_see_sensitive(user: User, category_short: str | None, building_id: int | None) -> bool:
    """Акумулятори, автономність, відключення, СЕС по конкретному об'єкту."""
    if user.role in FULL_ACCESS:
        return True
    if user.role == "department":
        return _dept_has(user, category_short)
    if user.role == "facility_head":
        return _own(user, building_id)
    return False  # finance, public


def can_see_ses(user: User, category_short: str | None, building_id: int | None) -> bool:
    """Наявність СЕС, K, капвитрати по об'єкту (без акумуляторів/автономності): + finance."""
    return user.role == "finance" or can_see_sensitive(user, category_short, building_id)


def can_see_finance(user: User, category_short: str | None, building_id: int | None) -> bool:
    if user.role in FULL_ACCESS or user.role == "finance":
        return True
    if user.role == "department":
        return _dept_has(user, category_short)
    if user.role == "facility_head":
        return _own(user, building_id)
    return False


def can_edit_ses(user: User, building_id: int | None) -> bool:
    if user.role == "energy_manager":
        return True
    return user.role == "facility_head" and _own(user, building_id)


# --- вхід ---

class LoginIn(BaseModel):
    full_name: str
    position: str
    role: str
    building_id: int | None = None
    department: str | None = None
    password: str


def authenticate(req: LoginIn, building_ids: Container[int]) -> User:
    """Перевіряє пароль і поля входу; повертає User або кидає HTTPException (401/422)."""
    if not check_password(req.password):
        raise HTTPException(401, "Невірний пароль")
    full_name, position = req.full_name.strip(), req.position.strip()
    if not full_name or len(full_name) > 200:
        raise HTTPException(422, "Вкажіть ПІБ")
    if not position or len(position) > 200:
        raise HTTPException(422, "Вкажіть посаду")
    role = ROLES.get(req.role)
    if role is None or req.role == "public":
        raise HTTPException(422, "Невідома роль")
    building_id = department = None
    if role["needs_building"]:
        if req.building_id is None or req.building_id not in building_ids:
            raise HTTPException(422, "Оберіть об'єкт зі списку")
        building_id = int(req.building_id)
    if role["needs_department"]:
        department = norm_department(req.department)
        if department not in DEPARTMENT_CATEGORIES:
            raise HTTPException(422, "Оберіть управління: «освіта» або «здоров'я»")
    return User(full_name=full_name, position=position, role=req.role, role_name=role["name"],
                building_id=building_id, department=department)


# --- наївний ліміт спроб входу (у пам'яті процесу) ---

RATE_LIMIT = 10
RATE_WINDOW = 60.0
_attempts: dict[str, deque] = defaultdict(deque)


def rate_limited(ip: str, now: float | None = None) -> bool:
    """True, якщо з цієї IP за хвилину вже було ≥10 невдалих спроб."""
    now = time.time() if now is None else now
    q = _attempts[ip]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    return len(q) >= RATE_LIMIT


def note_failure(ip: str, now: float | None = None) -> None:
    _attempts[ip].append(time.time() if now is None else now)


def reset_rate_limit() -> None:
    _attempts.clear()
