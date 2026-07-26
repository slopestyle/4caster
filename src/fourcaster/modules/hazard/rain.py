"""RainHazard: Hiking Impact Level (упрощённо, PRD §4.3, §10.4).

ВНИМАНИЕ: срезовая эвристика по суточной сумме осадков (p50). Полный HIL
(§10.4) учитывает интенсивность precip_rate, конвекцию showers, CAPE,
время суток и высоту, а также сухие окна — это Фаза 2 (задача 2.4).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Hil:
    level: int       # 0..5
    label: str
    icon: str
    upper_mm: float  # верхняя граница суточной суммы для уровня


# Пороги по суточной сумме осадков, мм (срезовая шкала).
HIL_LEVELS: tuple[Hil, ...] = (
    Hil(0, "Сухо", "☁️", 0.5),
    Hil(1, "Морось", "🌦", 2.0),
    Hil(2, "Слабый дождь", "🌧", 6.0),
    Hil(3, "Дождь", "🌧", 15.0),
    Hil(4, "Сильный дождь", "🌧", 30.0),
    Hil(5, "Ливень", "⛈", float("inf")),
)


def classify_hil(precip_mm: float) -> Hil:
    for level in HIL_LEVELS:
        if precip_mm < level.upper_mm:
            return level
    return HIL_LEVELS[-1]
