"""Нормализация сырых рядов → канонические посуточные снапшоты.

Реализует срезовое подмножество §10.2:
- валидация `valid_range` с отбрасыванием выбросов (FR-NORM-2);
- вероятность приводится из % (0..100) в канонические 0..1;
- отсутствующие значения осадков трактуются как 0 (accumulated, FR-NORM-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fourcaster.modules.consensus.models import (
    BY_OPENMETEO_ID,
    BY_RESPONSE_KEY,
    EnsembleModel,
    ForecastModel,
)
from fourcaster.modules.ingestion.ports import RawEnsembleSeries, RawModelSeries
from fourcaster.shared_kernel.variables import (
    PRECIP_PROBABILITY,
    PRECIP_TOTAL,
    TEMP_2M,
)


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    """Нормализованный посуточный прогноз одной модели (упрощённый
    ForecastSnapshot, §9.1). Иммутабелен (INV-1).

    `None` в осадках означает «модель не покрывает этот день» (за горизонтом
    выпуска) — это НЕ ноль. Такой день исключается из консенсуса модели."""

    model: ForecastModel
    dates: tuple[date, ...]
    precip_total_mm: tuple[float | None, ...]     # осадки за сутки, мм (accumulated)
    precip_probability: tuple[float | None, ...]  # 0..1 (instant)
    temp_max_c: tuple[float | None, ...] = ()     # °C (instant, §10.2)
    temp_min_c: tuple[float | None, ...] = ()
    provider_elevation_m: float | None = None     # FR-DS-2: что взял провайдер


@dataclass(frozen=True, slots=True)
class EnsembleSnapshot:
    """Нормализованный посуточный прогноз одного ансамбля: все члены как есть.

    Члены не сворачиваются в среднее — среднее по осадкам методологически
    неверно (§10.5.1), а разброс членов нужен компоненте E надёжности (§10.6).
    `members[k][i]` — сумма осадков k-го члена за i-е сутки; `None` = день не
    покрыт.
    """

    ensemble: EnsembleModel
    dates: tuple[date, ...]
    members: tuple[tuple[float | None, ...], ...]

    @property
    def n_members(self) -> int:
        return len(self.members)


def _clean_precip(value: float | None) -> float | None:
    if value is None:
        return None  # модель не даёт значения на этот день — не подменяем нулём
    lo, hi = PRECIP_TOTAL.valid_range
    if not (lo <= value <= hi):
        return None  # выброс отбрасывается (FR-NORM-2)
    return float(value)


def _clean_temp(value: float | None) -> float | None:
    if value is None:
        return None
    lo, hi = TEMP_2M.valid_range
    return float(value) if lo <= value <= hi else None


def _norm_prob(value: float | None) -> float | None:
    if value is None:
        return None
    lo, hi = PRECIP_PROBABILITY.valid_range
    p = value / 100.0
    return p if lo <= p <= hi else None


def normalize(series: RawModelSeries) -> ModelSnapshot | None:
    model = BY_OPENMETEO_ID.get(series.model_openmeteo_id)
    if model is None:
        return None  # неизвестная модель не попадает в домен
    empty: tuple[None, ...] = (None,) * len(series.dates)
    return ModelSnapshot(
        model=model,
        dates=series.dates,
        precip_total_mm=tuple(_clean_precip(v) for v in series.precip_total_mm),
        precip_probability=tuple(_norm_prob(v) for v in series.precip_probability_pct),
        temp_max_c=tuple(_clean_temp(v) for v in series.temp_max_c) or empty,
        temp_min_c=tuple(_clean_temp(v) for v in series.temp_min_c) or empty,
        provider_elevation_m=series.provider_elevation_m,
    )


def normalize_ensemble(series: RawEnsembleSeries) -> EnsembleSnapshot | None:
    ensemble = BY_RESPONSE_KEY.get(series.ensemble_openmeteo_id)
    if ensemble is None:
        return None  # неизвестный ансамбль не попадает в домен
    return EnsembleSnapshot(
        ensemble=ensemble,
        dates=series.dates,
        members=tuple(
            tuple(_clean_precip(v) for v in member) for member in series.members
        ),
    )
