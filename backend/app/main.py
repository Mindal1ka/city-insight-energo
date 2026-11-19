"""FastAPI: API + роздача зібраного фронтенду."""

from __future__ import annotations

import csv
import io
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .analytics import Store
from .auth import User, can_see_ses, can_see_sensitive, require, require_login
from .import_umuni import detect_kind

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
FRONT = Path(os.getenv("FRONTEND_DIR", ROOT.parent / "frontend" / "build"))

app = FastAPI(title="City Insight Map · Енергія", version="0.1.0")
store = Store(DATA_DIR)


@app.get("/api/summary")
def summary():
    return store.summary()


@app.get("/api/buildings")
def buildings(category: str | None = None):
    lst = [b for b in store.buildings if not category or b.category_short == category]
    return [store.view(b) for b in lst]


@app.get("/api/buildings/{bid}")
def building(bid: int):
    for b in store.buildings:
        if b.id == bid:
            d = store.view(b, full=True)
            d["median_kwh_m2"] = store.medians.get(b.category_short)
            return d
    raise HTTPException(404, "Будівлю не знайдено")


@app.get("/api/defects")
def defects():
    return store.defects


@app.get("/api/defects.csv")
def defects_csv():
    buf = io.StringIO()
    cols = ["тип", "набір", "будівля_id", "будівля", "поле", "значення", "правило", "що_робити"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    w.writerows(store.defects)
    data = "﻿" + buf.getvalue()  # BOM, щоб Excel відкрив кирилицю
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=data-defects.csv"})


@app.post("/api/upload")
async def upload(file: UploadFile, user: User = Depends(require("energy_manager", "data_admin"))):
    """Нове вивантаження UMUNI → перерахунок без участі розробника."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(400, "Потрібен файл XLSX з UMUNI")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        try:
            kind = detect_kind(tmp_path)
        except Exception:
            raise HTTPException(400, "Файл пошкоджений або не є звітом UMUNI у форматі XLSX")
        if kind == "meters":
            # Реєстр лічильників: сирий файл НЕ зберігаємо (там заводські номери) —
            # лише знеособлений data/meters.csv
            from .meters import METERS_CSV, sanitize_meters, write_csv
            try:
                rows = sanitize_meters(tmp_path)
            except Exception as e:
                raise HTTPException(400, f"Не вдалося прочитати реєстр лічильників: {e}")
            if not rows:
                raise HTTPException(400, "У файлі лічильників немає рядків")
            target = DATA_DIR / METERS_CSV
            backup = target.with_suffix(".bak") if target.exists() else None
            if backup:
                shutil.copy2(target, backup)
            write_csv(rows, target)
            try:
                store.reload()
            except Exception as e:
                if backup:
                    shutil.move(backup, target)
                store.reload()
                raise HTTPException(400, f"Не вдалося обробити реєстр лічильників: {e}")
            if backup:
                backup.unlink(missing_ok=True)
            return {"ok": True, "kind": kind, "summary": store.summary()}
        if kind not in ("buildings", "annual"):
            raise HTTPException(400, "Не розпізнано звіт UMUNI (очікується «Характеристики будівель», «Річний звіт» або «Лічильники»)")
        target = DATA_DIR / Path(file.filename).name
        backup = target.with_suffix(".bak") if target.exists() else None
        if backup:
            shutil.copy2(target, backup)
        shutil.move(tmp_path, target)
        try:
            store.reload()
        except Exception as e:  # некоректний звіт — повертаємо попередній файл
            if backup:
                shutil.move(backup, target)
            else:
                target.unlink(missing_ok=True)
            store.reload()
            raise HTTPException(400, f"Не вдалося обробити звіт: {e}")
        if backup:
            backup.unlink(missing_ok=True)
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"ok": True, "kind": kind, "summary": store.summary()}


# --- об'єкти з СЕС і добова телеметрія (ДЕМО) ---
from datetime import date, datetime  # noqa: E402

from .sites import KYIV, Sites  # noqa: E402

sites = Sites(store)


def _when(day: str | None, hour: int | None):
    """?day=YYYY-MM-DD&hour=H — подивитися інший день (наприклад, літній) замість поточного моменту."""
    if day is None and hour is None:
        return None
    try:
        now = sites._now()
        d = date.fromisoformat(day) if day else now.date()
        h = now.hour if hour is None else max(0, min(23, int(hour)))
        return datetime(d.year, d.month, d.day, h, 0, tzinfo=KYIV)
    except ValueError:
        raise HTTPException(400, "Невірна дата (формат РРРР-ММ-ДД)")


@app.get("/api/sites")
def sites_list(day: str | None = None, hour: int | None = None, user: User = Depends(require_login)):
    data = sites.listing(_when(day, hour))
    # наявність СЕС по об'єктах — лише дозволеним ролям (finance теж бачить СЕС, але не акумулятори)
    data["items"] = [i for i in data["items"] if can_see_ses(user, i["category_short"], i["id"])]
    return data


@app.get("/api/sites/{bid}")
def site(bid: int, day: str | None = None, hour: int | None = None, user: User = Depends(require_login)):
    for b in store.buildings:
        if b.id == bid:
            if not can_see_sensitive(user, b.category_short, b.id):
                raise HTTPException(403, "Немає доступу до даних цього об'єкта")
            return sites.detail(b, _when(day, hour))
    raise HTTPException(404, "Об'єкт не знайдено")


# --- енергонезалежність і прогноз сонця (підключаються, щойно модулі існують) ---
import importlib  # noqa: E402

for _mod in ("auth_api", "ses_api", "independence_api", "forecast_api", "map_api"):
    try:
        app.include_router(importlib.import_module(f".{_mod}", __package__).router)
    except ModuleNotFoundError as _e:
        if _e.name != f"{__package__}.{_mod}":
            raise

# --- модуль СЕС (до SPA-маршруту, інакше catch-all перехопить /api/solar) ---
from .solar_api import router as solar_router  # noqa: E402

app.include_router(solar_router)

# --- фронтенд (SPA) ---
if FRONT.exists():
    app.mount("/_app", StaticFiles(directory=FRONT / "_app"), name="app")

    @app.get("/{path:path}")
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Невідомий метод API")
        f = FRONT / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(FRONT / "index.html")
