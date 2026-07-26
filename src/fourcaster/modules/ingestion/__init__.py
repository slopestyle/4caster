"""Ingestion (upstream, hexagonal ports & adapters, PRD §8.5, §11.3).

Порт `ForecastProvider` изолирует домен от конкретного транспорта;
замена Open-Meteo → GRIB (Фаза 2) не затрагивает домен (MB-3).
"""

from fourcaster.modules.ingestion.ports import ForecastProvider, RawModelSeries

__all__ = ["ForecastProvider", "RawModelSeries"]
