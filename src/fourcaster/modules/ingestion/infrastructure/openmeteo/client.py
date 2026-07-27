"""Адаптер Open-Meteo → порт `ForecastProvider` (PRD §8.3 T1).

Один запрос daily по нескольким моделям с явным `elevation` плюс отдельный
запрос к ансамблевому эндпоинту.

**Устойчивость (FR-SRC-3..5, задача 1.2).** Лимиты Open-Meteo считаются не по
запросам, а по объёму: один ансамблевый запрос тянет 82 члена, и минутный
лимит выбирается быстрее, чем кажется по числу вызовов — на выгрузке DEM это
случилось на седьмом запросе. Поэтому здесь: пауза между запросами, ретраи с
нарастающим ожиданием на 429/5xx/обрывах и предохранитель, который после серии
отказов перестаёт долбиться в стену (иначе 22 локации × 5 ретраев превращают
недоступность провайдера в получасовое зависание конвейера).

Raw storage в R2 (FR-SRC-7) — по-прежнему Фаза 1: хранить сырые ответы негде,
инфраструктура пересмотрена на serverless (ADR-0013).
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import date
from typing import Sequence

import httpx

from fourcaster.modules.ingestion.infrastructure.openmeteo.schemas import (
    OpenMeteoDailyResponse,
    OpenMeteoEnsembleResponse,
)
from fourcaster.modules.ingestion.ports import RawEnsembleSeries, RawModelSeries

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
# Атрибуция обязательна по лицензии CC BY 4.0 (FR-SRC-6): Open-Meteo и
# первоисточники (DWD, NOAA, ECMWF, ECCC, Météo-France).
USER_AGENT = "4CASTER/0.0.1 (contact@example.org)"


class ProviderUnavailable(RuntimeError):
    """Провайдер недоступен: лимит, отказ или сработавший предохранитель."""


class OpenMeteoProvider:
    """Транспорт T1. Синхронный клиент — достаточно для конвейера в Actions."""

    #: сколько подряд отказов терпим, прежде чем перестать пытаться
    BREAKER_THRESHOLD = 3
    #: минимальная пауза между запросами, с
    MIN_INTERVAL_S = 0.4
    #: паузы перед повторами (429 и 5xx), с
    BACKOFF_S = (5.0, 20.0, 60.0)

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._failures = 0
        self._last_call = 0.0

    def _get(self, url: str, params: dict) -> dict:
        """Запрос с паузой, ретраями и предохранителем (FR-SRC-3..5)."""
        if self._failures >= self.BREAKER_THRESHOLD:
            raise ProviderUnavailable(
                f"предохранитель разомкнут после {self._failures} отказов подряд"
            )
        headers = {"User-Agent": USER_AGENT}
        last: str = "неизвестно"
        for attempt in range(len(self.BACKOFF_S) + 1):
            pause = self.MIN_INTERVAL_S - (time.monotonic() - self._last_call)
            if pause > 0:
                time.sleep(pause)
            self._last_call = time.monotonic()
            try:
                with httpx.Client(timeout=self._timeout, headers=headers) as client:
                    resp = client.get(url, params=params)
            except httpx.TransportError as exc:
                last = f"обрыв связи: {exc}"
            else:
                if resp.status_code == 429:
                    last = "лимит запросов (429)"
                elif resp.status_code >= 500:
                    last = f"ошибка сервиса ({resp.status_code})"
                elif resp.is_error:
                    # 4xx кроме 429 — наша вина (неверные параметры), ретрай
                    # ничего не изменит и только жжёт квоту
                    self._failures += 1
                    raise ProviderUnavailable(
                        f"запрос отклонён ({resp.status_code}): {resp.text[:200]}"
                    )
                else:
                    self._failures = 0
                    return resp.json()
            if attempt < len(self.BACKOFF_S):
                time.sleep(self.BACKOFF_S[attempt])
        self._failures += 1
        raise ProviderUnavailable(f"не удалось получить данные — {last}")

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
            "daily": ("precipitation_sum,precipitation_probability_max,"
                      "temperature_2m_max,temperature_2m_min"),
            "models": ",".join(model_ids),
            "timezone": "UTC",
            "forecast_days": forecast_days,
            "cell_selection": "nearest",
        }
        return parse_daily_payload(self._get(FORECAST_URL, params), model_ids)


    def fetch_ensembles(
        self,
        *,
        lat: float,
        lon: float,
        elevation_m: int,
        ensemble_ids: Sequence[str],
        response_keys: Sequence[str],
        forecast_days: int,
    ) -> list[RawEnsembleSeries]:
        """Члены ансамблей E1–E2 (§8.2), приведённые к посуточным суммам.

        `ensemble_ids` — как ансамбль называется в параметре запроса,
        `response_keys` — как он назван в ключах ответа: у Open-Meteo это
        разные строки (`gfs025` → `ncep_gefs025`), и угадывать одну по другой
        нельзя. Обе живут в реестре моделей.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elevation_m,
            "hourly": "precipitation",   # ансамблевый эндпоинт даёт только часы
            "models": ",".join(ensemble_ids),
            "timezone": "UTC",
            "forecast_days": forecast_days,
            "cell_selection": "nearest",
        }
        return parse_ensemble_payload(self._get(ENSEMBLE_URL, params), response_keys)

    def fetch_hourly(
        self,
        *,
        lat: float,
        lon: float,
        elevation_m: int,
        model_ids: Sequence[str],
        forecast_days: int = 3,
    ) -> list[dict]:
        """Часовые ряды осадков по моделям (для метеограммы, US-FC-2).

        Open-Meteo отдаёт часы от 00:00 UTC текущих суток, поэтому для окна
        «48 часов от текущего часа» нужны трое суток: двух хватало бы только
        в полночь UTC. Обрезку до окна делает `compute_hourly`.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elevation_m,
            "hourly": "precipitation,precipitation_probability",
            "models": ",".join(model_ids),
            "timezone": "UTC",
            "forecast_days": forecast_days,
            "cell_selection": "nearest",
        }
        return parse_hourly_payload(self._get(FORECAST_URL, params), model_ids)


def parse_hourly_payload(payload: dict, model_ids: Sequence[str]) -> list[dict]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    out: list[dict] = []
    for mid in model_ids:
        precip = hourly.get(f"precipitation_{mid}") or hourly.get("precipitation")
        pop = hourly.get(f"precipitation_probability_{mid}") or hourly.get("precipitation_probability")
        if precip is None:
            continue
        out.append({
            "model_openmeteo_id": mid,
            "times": list(times),
            "precip": [float(v) if v is not None else 0.0 for v in precip],
            "pop": [(float(v) / 100.0 if v is not None else None) for v in (pop or [None] * len(times))],
        })
    return out


# Ключ часового ряда ансамбля: `precipitation`, `precipitation_member07`,
# и то же с суффиксом ансамбля, если запрошено несколько: `..._ncep_gefs025`.
_MEMBER_RE = re.compile(r"^precipitation(?:_member(\d+))?(?:_(.+))?$")


def _daily_sums(
    day_of_hour: list[str], values: list
) -> tuple[tuple[date, ...], tuple[float | None, ...]]:
    """Часовой ряд осадков → посуточные суммы (агрегация ACCUMULATED, §10.2).

    Неполные сутки (модель кончилась посреди дня, в ряду дырка) дают `None`, а
    не заниженную сумму: `None` означает «день не покрыт» и исключается из
    пула, тогда как 3 мм вместо 9 мм молча испортили бы консенсус.
    """
    totals: dict[str, float] = defaultdict(float)
    hours: dict[str, int] = defaultdict(int)
    for day, value in zip(day_of_hour, values):
        if value is None:
            continue
        totals[day] += float(value)
        hours[day] += 1
    days = sorted(set(day_of_hour))
    return (
        tuple(date.fromisoformat(d) for d in days),
        tuple(round(totals[d], 2) if hours[d] == 24 else None for d in days),
    )


def parse_ensemble_payload(
    payload: dict, response_keys: Sequence[str]
) -> list[RawEnsembleSeries]:
    """Разбор ответа ensemble-api на ряды «по одному на ансамбль»."""

    parsed = OpenMeteoEnsembleResponse.model_validate(payload)
    hourly = parsed.hourly
    times = hourly.get("time", [])
    if not times:
        return []
    day_of_hour = [t[:10] for t in times]     # ISO-метка вида 2026-07-27T13:00

    # члены по ансамблям: {суффикс ответа: {номер члена: часовой ряд}}
    grouped: dict[str | None, dict[str, list]] = defaultdict(dict)
    for key, values in hourly.items():
        match = _MEMBER_RE.match(key)
        if match is None:
            continue
        member, suffix = match.group(1) or "00", match.group(2)
        grouped[suffix][member] = values

    series: list[RawEnsembleSeries] = []
    for key in response_keys:
        # при запросе одного ансамбля Open-Meteo не суффиксирует ключи
        members = grouped.get(key) or (grouped.get(None) if len(response_keys) == 1 else None)
        if not members:
            continue  # ансамбль не ответил — деградированный режим
        dates: tuple[date, ...] = ()
        rows: list[tuple[float | None, ...]] = []
        for number in sorted(members):
            dates, sums = _daily_sums(day_of_hour, members[number])
            rows.append(sums)
        series.append(
            RawEnsembleSeries(
                ensemble_openmeteo_id=key, dates=dates, members=tuple(rows)
            )
        )
    return series


def parse_daily_payload(
    payload: dict, model_ids: Sequence[str]
) -> list[RawModelSeries]:
    """Разбор ответа (в т.ч. из записанной фикстуры) на ряды по моделям."""

    parsed = OpenMeteoDailyResponse.model_validate(payload)
    daily = parsed.daily
    dates = tuple(date.fromisoformat(t) for t in daily["time"])

    def column(name: str, model_id: str) -> list | None:
        # одиночный запрос идёт без суффикса модели — принимаем оба формата
        return daily.get(f"{name}_{model_id}") or daily.get(name)

    series: list[RawModelSeries] = []
    for model_id in model_ids:
        precip = column("precipitation_sum", model_id)
        if precip is None:
            continue  # модель не вернула данные — деградированный режим
        prob = column("precipitation_probability_max", model_id)
        t_max = column("temperature_2m_max", model_id)
        t_min = column("temperature_2m_min", model_id)
        empty: tuple[None, ...] = (None,) * len(dates)
        series.append(
            RawModelSeries(
                model_openmeteo_id=model_id,
                dates=dates,
                precip_total_mm=tuple(precip),
                precip_probability_pct=tuple(prob) if prob else empty,
                temp_max_c=tuple(t_max) if t_max else empty,
                temp_min_c=tuple(t_min) if t_min else empty,
                provider_elevation_m=parsed.elevation,
            )
        )
    return series
