"""Reliability Score (PRD §10.6): насколько прогнозу можно доверять.

Считаются компоненты A (согласие моделей), E (разброс ансамблей) и S
(устойчивость во времени) — посуточно, а затем сворачиваются в горизонты
1/3/7/14 суток (§10.6.3): наружу идёт надёжность на длину выхода, а не на
отдельные сутки. Компоненты H (историческая оправдываемость), G
(предсказуемость режима) и D (полнота данных) требуют Accuracy Engine и
верификации по факту — Фаза 3, §10.8.
"""

from fourcaster.modules.reliability.climatology import sigma_clim
from fourcaster.modules.reliability.score import (
    HORIZONS,
    HorizonReliability,
    Reliability,
    ReliabilityComponents,
    aggregate_by_horizon,
    compute_reliability,
)

__all__ = [
    "HORIZONS",
    "HorizonReliability",
    "Reliability",
    "ReliabilityComponents",
    "aggregate_by_horizon",
    "compute_reliability",
    "sigma_clim",
]
