"""Адаптер Open-Meteo → порт `ForecastProvider` (PRD §8.3 T1).

Реализует минимум, нужный срезу: один запрос daily по нескольким
моделям с явным `elevation`. Полный слой (rate limiter, circuit breaker,
ретраи, учёт квот, raw storage в R2) — FR-SRC-3..7, Фаза 1.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

import httpx

from fourcaster.modules.ingestion.infrastructure.openmeteo.schemas import (
    OpenMeteoDailyResponse,
)
from fourcaster.modules.ingestion.ports import RawModelSeries

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# Атрибуция обязательна по лицензии CC BY 4.0 (FR-SRC-6): Open-Meteo и
# первоисточники (DWD, NOAA, ECMWF, ECCC, Météo-France).
USER_AGENT = "4CASTER/0.0.1 (contact@example.org)"


class OpenMeteoProvider:
    """Транспорт T1. Синхронный клиент — достаточно для CLI-среза."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def fetch_daily(
        self,
        *,
        lat: float,
        lon: float,
        elevation_m: int,
        model_ids: Sequence[str],
        forecast_days: int,
    ) -> list[RawModelSeries]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elevation_m,  # критично для гор (FR-DS-2)
            "daily": "precipitation_sum,precipitation_probability_max",
            "models": ",".join(model_ids),
            "timezone": "UTC",
            "forecast_days": forecast_days,
            "cell_selection": "nearest",
        }
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(timeout=self._timeout, headers=headers) as client:
            resp = client.get(FORECAST_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
        return parse_daily_payload(payload, model_ids)


def parse_daily_payload(
    payload: dict, model_ids: Sequence[str]
) -> list[RawModelSeries]:
    """Разбор ответа (в т.ч. из записанной фикстуры) на ряды по моделям."""

    parsed = OpenMeteoDailyResponse.model_validate(payload)
    daily = parsed.daily
    dates = tuple(date.fromisoformat(t) for t in daily["time"])

    series: list[RawModelSeries] = []
    for model_id in model_ids:
        precip_key = f"precipitation_sum_{model_id}"
        prob_key = f"precipitation_probability_max_{model_id}"
        # одиночный запрос без суффикса (устойчивость к обоим форматам)
        precip = daily.get(precip_key) or daily.get("precipitation_sum")
        prob = daily.get(prob_key) or daily.get("precipitation_probability_max")
        if precip is None:
            continue  # модель не вернула данные — деградированный режим
        series.append(
            RawModelSeries(
                model_openmeteo_id=model_id,
                dates=dates,
                precip_total_mm=tuple(precip),
                precip_probability_pct=tuple(prob) if prob else (None,) * len(dates),
            )
        )
    return series
