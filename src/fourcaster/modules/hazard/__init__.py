"""Hazard (core domain, точка расширения PRD §11.3).

В MVP — `RainHazard`; зимние модули (снег, лавины) добавляются как новые
Hazard-модули без переработки ядра (принцип P7). В срезе реализован
упрощённый HIL по суточной сумме осадков.
"""

from fourcaster.modules.hazard.rain import HIL_LEVELS, classify_hil, Hil

__all__ = ["HIL_LEVELS", "classify_hil", "Hil"]
