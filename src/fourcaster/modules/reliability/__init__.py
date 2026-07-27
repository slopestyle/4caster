"""Reliability Score (PRD §10.6): насколько прогнозу можно доверять.

Считаются компоненты A (согласие моделей), E (разброс ансамблей) и S
(устойчивость во времени). Компоненты H (историческая оправдываемость),
G (предсказуемость режима) и D (полнота данных) требуют Accuracy Engine и
верификации по факту — Фаза 3, §10.8.
"""

from fourcaster.modules.reliability.climatology import sigma_clim
from fourcaster.modules.reliability.score import (
    Reliability,
    ReliabilityComponents,
    compute_reliability,
)

__all__ = [
    "Reliability",
    "ReliabilityComponents",
    "compute_reliability",
    "sigma_clim",
]
