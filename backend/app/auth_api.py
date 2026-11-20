"""API входу: /api/auth/login, /api/auth/me, /api/auth/roles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from . import auth
from .auth import LoginIn, User, current_user

router = APIRouter(tags=["Вхід і ролі"])


@router.post("/api/auth/login")
def login(req: LoginIn, request: Request):
    from .main import store  # лінивий імпорт, щоб не було циклу з main.py

    ip = request.client.host if request.client else "?"
    who = req.login or req.full_name  # лічильник — за (IP, логін), а не лише за IP
    if auth.rate_limited(ip, login=who):
        raise HTTPException(429, "Забагато спроб входу. Спробуйте за хвилину")
    try:
        user = auth.authenticate(req, {b.id for b in store.buildings})
    except HTTPException:
        auth.note_failure(ip, login=who)
        raise
    auth.note_success(ip, login=who)
    return {"token": auth.make_token(user), "user": user.model_dump()}


@router.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    if user.role == "public":
        raise HTTPException(401, "Потрібен вхід")
    return user


@router.get("/api/auth/roles")
def roles():
    # гостьового режиму немає: внутрішня роль public (без токена) клієнтам не показується
    return [{"id": rid, **r} for rid, r in auth.ROLES.items() if rid != "public"]
