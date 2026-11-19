"""API прогнозу генерації СЕС (Open-Meteo + запасний PVGIS)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from . import forecast

router = APIRouter()


@router.get("/api/forecast")
def get_forecast(days: int = Query(3, ge=1, le=forecast.MAX_DAYS), refresh: bool = False):
    """Прогноз на 1 кВт піку по годинах на `days` днів. refresh=true — оминути кеш (1 год)."""
    return forecast.get_forecast(days, force=refresh)
