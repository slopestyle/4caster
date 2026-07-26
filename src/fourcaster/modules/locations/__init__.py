"""Locations (supporting context, PRD §7).

В срезе — статический seed-каталог; в MVP это версионируемая
seed-миграция (FR-LOC-3), добавление локации без деплоя кода.
"""

from fourcaster.modules.locations.catalog import CATALOG, get_location

__all__ = ["CATALOG", "get_location"]
