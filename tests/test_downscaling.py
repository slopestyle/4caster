"""Орографическая коррекция, нулевая изотерма и фаза осадков (PRD §10.3)."""

from __future__ import annotations

import pytest

from fourcaster.modules.downscaling import (
    GAMMA_C_PER_M,
    build_profile,
    freezing_level_m,
    precip_phase,
    residual_correction_c,
)
from fourcaster.shared_kernel.variables import PrecipPhase


def test_no_correction_when_provider_used_our_elevation():
    """Главный случай: провайдер уже сгладил температуру к нашей высоте.

    Повторная коррекция здесь удвоила бы поправку — на Ачишхо это 0.7 °C
    из ниоткуда, а на границе фазы осадков столько решают.
    """
    assert residual_correction_c(2391.0, 2391) == 0.0


def test_correction_compensates_provider_elevation_gap():
    """Если провайдер посчитал для 2281 м, а точка на 2391 — вычитаем разницу."""
    correction = residual_correction_c(2281.0, 2391)
    assert correction == pytest.approx(-110 * GAMMA_C_PER_M)
    assert correction < 0, "выше — холоднее"


def test_correction_is_zero_when_provider_elevation_unknown():
    """Не знаем высоту провайдера — не выдумываем поправку."""
    assert residual_correction_c(None, 2391) == 0.0


def test_freezing_level_rises_with_temperature():
    assert freezing_level_m(0.0, 2391) == pytest.approx(2391)
    assert freezing_level_m(5.0, 2391) == pytest.approx(2391 + 5 / GAMMA_C_PER_M)
    assert freezing_level_m(-2.0, 2391) < 2391


def test_phase_snow_above_freezing_level_with_melt_margin():
    # точка на 300 м выше нуля — снег
    assert precip_phase(2400, 2100.0) is PrecipPhase.SNOW
    # на 300 м ниже — дождь
    assert precip_phase(1800, 2100.0) is PrecipPhase.RAIN
    # в слое таяния — мокрый снег, а не выбор одного из двух наугад
    assert precip_phase(2100, 2100.0) is PrecipPhase.SLEET


def test_profile_marks_summer_snow_on_high_peaks():
    """Цахвоа, 3345 м: при −3 °C в среднем за сутки это снег, а не дождь."""
    profile = build_profile(temp_max_c=0.0, temp_min_c=-6.0,
                            provider_elevation_m=3345.0, true_elevation_m=3345)
    assert profile.phase is PrecipPhase.SNOW
    assert profile.freezing_level_m < 3345


def test_profile_is_rain_in_a_warm_valley():
    profile = build_profile(temp_max_c=26.0, temp_min_c=16.0,
                            provider_elevation_m=570.0, true_elevation_m=570)
    assert profile.phase is PrecipPhase.RAIN


def test_profile_without_temperature_has_no_phase():
    """Модель не дала температуру — фазу не выдумываем."""
    profile = build_profile(temp_max_c=None, temp_min_c=None,
                            provider_elevation_m=2391.0, true_elevation_m=2391)
    assert profile.phase is None
    assert profile.freezing_level_m is None


def test_profile_applies_correction_to_both_temperatures():
    profile = build_profile(temp_max_c=10.0, temp_min_c=2.0,
                            provider_elevation_m=2281.0, true_elevation_m=2391)
    assert profile.correction_c == pytest.approx(-110 * GAMMA_C_PER_M, abs=0.01)
    assert profile.temp_max_c == pytest.approx(9.3, abs=0.05)
    assert profile.temp_min_c == pytest.approx(1.3, abs=0.05)
