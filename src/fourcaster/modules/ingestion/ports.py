"""Порт слоя источников (PRD FR-SRC-2, §11.3).

`RawModelSeries` — сырой посуточный ряд одной модели по одной локации,
уже вынутый из ответа транспорта, но ещё не приведённый к канонической
схеме (это делает Normalization). Схемы внешних API не проникают сюда —
они живут в infrastructure/<provider>/schemas.py (MB-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class RawModelSeries:
    """Посуточный ряд одной модели для одной локации.

    `provider_elevation_m` — высота, которую провайдер **фактически** взял для
    точки (FR-DS-2). Он сам сглаживает температуру к этой высоте, поэтому знать
    её обязательно: без этого своя орографическая поправка легла бы поверх уже
    сделанной провайдером и удвоила коррекцию.
    """

    model_openmeteo_id: str
    dates: tuple[date, ...]
    precip_total_mm: tuple[float | None, ...]     # осадки за сутки, мм
    precip_probability_pct: tuple[float | None, ...]  # макс. вероятность за сутки, %
    temp_max_c: tuple[float | None, ...] = ()     # максимум за сутки, °C
    temp_min_c: tuple[float | None, ...] = ()     # минимум за сутки, °C
    provider_elevation_m: float | None = None


@dataclass(frozen=True, slots=True)
class RawEnsembleSeries:
    """Посуточные суммы осадков по всем членам одного ансамбля (§8.2 E1–E2).

    `members` — кортеж рядов «по одному на член», каждый выровнен по `dates`.
    Члены не усредняются на этом уровне: в консенсус они входят по отдельности
    как элементы общего пула (§10.5.1), а их разброс — сырьё для компоненты E
    надёжности (§10.6).
    """

    ensemble_openmeteo_id: str
    dates: tuple[date, ...]
    members: tuple[tuple[float | None, ...], ...]


class ForecastProvider(Protocol):
    """Единый порт получения прогнозов (FR-SRC-2)."""

    def fetch_daily(
        self,
        *,
        lat: float,
        lon: float,
        elevation_m: int,
        model_ids: Sequence[str],
        forecast_days: int,
    ) -> list[RawModelSeries]:
        ...

    def fetch_ensembles(
        self,
        *,
        lat: float,
        lon: float,
        elevation_m: int,
        ensemble_ids: Sequence[str],
        forecast_days: int,
    ) -> list[RawEnsembleSeries]:
        ...
