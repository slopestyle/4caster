"""Каноническая схема переменных (PRD §10.2, §4.3).

Тип агрегации — часть схемы, а не соглашение: ошибка агрегации
накопленных величин (осадков) — самый частый дефект таких систем.
В срезе задействована только осадочная ветка; остальное — задел.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AggregationType(str, Enum):
    INSTANT = "instant"        # температура, CAPE
    ACCUMULATED = "accumulated"  # осадки
    MEAN = "mean"              # облачность
    MAX = "max"                # порывы


@dataclass(frozen=True, slots=True)
class CanonicalVariable:
    code: str
    unit: str
    aggregation: AggregationType
    valid_range: tuple[float, float]


# Первичные переменные MVP (подмножество §4.3, нужное срезу).
PRECIP_TOTAL = CanonicalVariable("precip_total", "mm", AggregationType.ACCUMULATED, (0.0, 500.0))
PRECIP_PROBABILITY = CanonicalVariable("precip_probability", "0..1", AggregationType.INSTANT, (0.0, 1.0))
