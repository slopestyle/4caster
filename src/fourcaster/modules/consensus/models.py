"""Реестр численных моделей и стартовых весов (PRD §8.2).

`ForecastModel` — носитель метеорологической независимости; только он
получает вес в консенсусе (INV-4: одна модель учитывается не более
одного раза). `openmeteo_id` — идентификатор транспорта Open-Meteo (T1),
не путать с доменной моделью (разделение «Модель»/«Транспорт», §8.1.2).

Веса — стартовые (§8.2); в MVP пересчитываются Accuracy Engine (Фаза 3).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForecastModel:
    id: str
    name: str
    center: str
    weight: float          # стартовый вес консенсуса (§8.2)
    openmeteo_id: str      # идентификатор модели в Open-Meteo API


MODELS: tuple[ForecastModel, ...] = (
    ForecastModel("ifs", "ECMWF IFS", "ECMWF", 0.30, "ecmwf_ifs025"),
    ForecastModel("icon", "DWD ICON", "DWD", 0.28, "icon_global"),
    ForecastModel("gfs", "NOAA GFS", "NCEP", 0.20, "gfs_global"),
    ForecastModel("gem", "ECCC GEM", "ECCC", 0.14, "gem_global"),
    ForecastModel("arpege", "MF ARPEGE", "Météo-France", 0.08, "meteofrance_arpege_world"),
)

BY_OPENMETEO_ID: dict[str, ForecastModel] = {m.openmeteo_id: m for m in MODELS}
