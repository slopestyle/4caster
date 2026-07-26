"""Consensus (core domain, PRD §10.5).

Взвешенный вероятностный консенсус по осадкам. В срезе пул членов —
детерминированные модели (по одному значению на модель); ансамбли
(IFS ENS, GEFS) — Фаза 2. Перцентили по 5 моделям — грубая оценка
разброса (PRD это признаёт), полноценная — через ансамбли.
"""

from fourcaster.modules.consensus.models import MODELS, ForecastModel
from fourcaster.modules.consensus.calculator import compute_consensus, DayConsensus

__all__ = ["MODELS", "ForecastModel", "compute_consensus", "DayConsensus"]
