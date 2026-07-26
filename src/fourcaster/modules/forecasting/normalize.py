"""Нормализация сырых рядов → канонические посуточные снапшоты.

Реализует срезовое подмножество §10.2:
- валидация `valid_range` с отбрасыванием выбросов (FR-NORM-2);
- вероятность приводится из % (0..100) в канонические 0..1;
- отсутствующие значения осадков трактуются как 0 (accumulated, FR-NORM-3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from fourcaster.modules.consensus.models import BY_OPENMETEO_ID, ForecastModel
from fourcaster.modules.ingestion.ports import RawModelSeries
from fourcaster.shared_kernel.variables import PRECIP_PROBABILITY, PRECIP_TOTAL


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


def _clean_precip(value: float | None) -> float | None:
    if value is None:
        return None  # модель не даёт значения на этот день — не подменяем нулём
    lo, hi = PRECIP_TOTAL.valid_range
    if not (lo <= value <= hi):
        return None  # выброс отбрасывается (FR-NORM-2)
    return float(value)


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
    return ModelSnapshot(
        model=model,
        dates=series.dates,
        precip_total_mm=tuple(_clean_precip(v) for v in series.precip_total_mm),
        precip_probability=tuple(_norm_prob(v) for v in series.precip_probability_pct),
    )
