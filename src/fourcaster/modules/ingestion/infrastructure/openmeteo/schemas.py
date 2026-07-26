"""ACL: схемы ответа Open-Meteo (PRD §8.3 T1, MB-3).

Anticorruption Layer — Pydantic-валидация внешнего JSON. При запросе
нескольких моделей Open-Meteo возвращает единый блок `daily`, где ключи
переменных суффиксированы идентификатором модели, например
`precipitation_sum_ecmwf_ifs025`. Эти схемы не покидают infrastructure.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OpenMeteoDailyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    latitude: float
    longitude: float
    elevation: float | None = None
    # ключи вида "time", "precipitation_sum_<model>", "precipitation_probability_max_<model>"
    daily: dict[str, list]
