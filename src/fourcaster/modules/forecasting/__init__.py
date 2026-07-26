"""Forecasting: нормализация к канонической схеме (PRD §10.2).

В срезе — приведение сырых рядов к валидированным посуточным снапшотам.
Downscaling (§10.3) и bias-correction опущены (Фаза 1/3); для суточных
сумм осадков в срезе используются значения провайдера как есть.
"""

from fourcaster.modules.forecasting.normalize import normalize, ModelSnapshot

__all__ = ["normalize", "ModelSnapshot"]
