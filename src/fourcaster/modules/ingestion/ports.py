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
    """Посуточный ряд осадков одной модели для одной локации."""

    model_openmeteo_id: str
    dates: tuple[date, ...]
    precip_total_mm: tuple[float | None, ...]     # осадки за сутки, мм
    precip_probability_pct: tuple[float | None, ...]  # макс. вероятность за сутки, %


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
