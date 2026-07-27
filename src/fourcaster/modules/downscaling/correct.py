"""Орографическая коррекция и фаза осадков (PRD §10.3).

Глобальные модели с шагом 7–25 км видят вместо Фишта (2867 м) сглаженную
возвышенность: DEM провайдера даёт там 2763 м, на Ачишхо — 2281 вместо 2391.
Без поправки все производные величины смещены на несколько градусов.

**Главная тонкость: провайдер уже вносит эту поправку сам.** Open-Meteo
пересчитывает температуру к переданному `elevation` с градиентом 0.0065 °C/м —
проверено замером: одна и та же точка при `elevation` 2391 и 1000 отличается на
9.0 °C, то есть ровно 0.00647 °C/м. Поэтому здесь считается **остаточная**
поправка: разница между высотой, которую провайдер реально взял (она приходит в
ответе, FR-DS-2), и истинной высотой точки. Когда провайдер послушался, она
равна нулю; когда он высоту проигнорировал или обрезал — мы это чиним.

Орографическое усиление осадков `k_oro` (§10.3 п.3) здесь сознательно
отсутствует: PRD требует не подбирать формулу, а обучать множитель по факту в
Accuracy Engine (§10.8.5) — Фаза 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from fourcaster.shared_kernel.variables import PrecipPhase

# Стандартный вертикальный градиент температуры, °C/м (§10.3). Фактический
# градиент из уровней 850/700 гПа — Фаза 2: он учитывает инверсии, а их в
# котловинах Красной Поляны зимой достаточно, чтобы стандартный градиент врал.
GAMMA_C_PER_M = 0.0065

# Слой таяния: снег засчитываем, только если точка выше нулевой изотермы на
# запас (§10.3 п.4) — падая сквозь тёплый слой, снег успевает растаять.
MELT_LAYER_M = 100.0


@dataclass(frozen=True, slots=True)
class DayProfile:
    """Термический профиль суток в точке после коррекции."""

    temp_max_c: float | None
    temp_min_c: float | None
    freezing_level_m: float | None
    phase: PrecipPhase | None
    correction_c: float          # величина остаточной поправки (FR-DS-1)


def residual_correction_c(
    provider_elevation_m: float | None, true_elevation_m: int
) -> float:
    """Поправка температуры на разницу «высота провайдера → истинная высота».

    Ноль, если провайдер уже посчитал для нужной высоты, — а это нормальный
    случай, и именно поэтому поправку нельзя применять вслепую.
    """
    if provider_elevation_m is None:
        return 0.0
    return GAMMA_C_PER_M * (provider_elevation_m - true_elevation_m)


def freezing_level_m(temp_c: float, elevation_m: int) -> float:
    """Высота нулевой изотермы по температуре в точке и градиенту.

    Пересчёт из скорректированного профиля (§10.3 п.2): если на 2391 м сейчас
    +5 °C, ноль лежит примерно на 770 м выше.
    """
    return elevation_m + temp_c / GAMMA_C_PER_M


def precip_phase(elevation_m: int, freezing_m: float) -> PrecipPhase:
    """Фаза осадков по §10.3 п.4.

    Точка заметно выше нулевой изотермы — снег; заметно ниже — дождь; в полосе
    слоя таяния честнее сказать «мокрый снег», чем выбрать одно из двух.
    """
    if elevation_m > freezing_m + MELT_LAYER_M:
        return PrecipPhase.SNOW
    if elevation_m < freezing_m - MELT_LAYER_M:
        return PrecipPhase.RAIN
    return PrecipPhase.SLEET


def build_profile(
    *,
    temp_max_c: float | None,
    temp_min_c: float | None,
    provider_elevation_m: float | None,
    true_elevation_m: int,
) -> DayProfile:
    """Профиль суток: скорректированные температуры, изотерма и фаза.

    Фаза определяется по **средней** температуре суток: по максимуму снег не
    выпал бы никогда, по минимуму — шёл бы каждую ночь, а в поход идут на весь
    день.
    """
    correction = residual_correction_c(provider_elevation_m, true_elevation_m)
    t_max = temp_max_c + correction if temp_max_c is not None else None
    t_min = temp_min_c + correction if temp_min_c is not None else None
    if t_max is None or t_min is None:
        return DayProfile(t_max, t_min, None, None, round(correction, 2))

    mean_c = (t_max + t_min) / 2
    zero_m = freezing_level_m(mean_c, true_elevation_m)
    return DayProfile(
        temp_max_c=round(t_max, 1),
        temp_min_c=round(t_min, 1),
        freezing_level_m=round(zero_m),
        phase=precip_phase(true_elevation_m, zero_m),
        correction_c=round(correction, 2),
    )
