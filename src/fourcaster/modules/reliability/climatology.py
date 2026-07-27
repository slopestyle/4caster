"""Климатический разброс осадков σ_clim для компоненты E (PRD §10.6).

E сравнивает разброс членов ансамбля с **обычным** разбросом для этого места и
месяца: разброс в 10 мм на Ачишхо в мае и в Кодорском ущелье в августе значат
разное. Эталон берётся из архива реанализа — его накапливает backfill
(`scripts/backfill_archive.py`, задача 1.7) и складывает в `data/sigma_clim.json`
в разрезе «кластер × месяц».

Пока файла нет, работает запасное значение: компонента E тогда меряет разброс
не относительно климата, а относительно правдоподобной константы. Это честнее,
чем выключать E совсем, но именно поэтому скор помечен `is_calibrated = false`
(INV-6) и наружу идёт качественной шкалой.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# Запасное σ_clim, мм/сут: порядок величины летнего суточного разброса осадков
# на Западном Кавказе. Заменяется данными backfill, как только он отработает.
FALLBACK_SIGMA_MM = 8.0

_DATA_PATH = Path(__file__).with_name("data") / "sigma_clim.json"


@lru_cache(maxsize=1)
def _table() -> dict[str, float]:
    """{"CL-ALP-W:7": 9.4, ...} — кластер и номер месяца."""
    if not _DATA_PATH.exists():
        return {}
    try:
        return {k: float(v) for k, v in json.loads(_DATA_PATH.read_text("utf-8")).items()}
    except (ValueError, OSError):
        return {}      # битый артефакт не должен ронять конвейер


def sigma_clim(cluster: str, month: int) -> float:
    """Климатический разброс суточных осадков, мм."""
    table = _table()
    value = table.get(f"{cluster}:{month}")
    if value is None:                       # нет месяца — пробуем кластер целиком
        value = table.get(cluster)
    return value if value and value > 0 else FALLBACK_SIGMA_MM


def is_calibrated_climatology() -> bool:
    """Есть ли под σ_clim реальные данные архива (для честной подписи в UI)."""
    return bool(_table())
