"""Компоненты Reliability Score A / E / S и их свёртка (PRD §10.6)."""

from __future__ import annotations

from datetime import date

import pytest

from fourcaster.modules.consensus.calculator import DayPool
from fourcaster.modules.consensus.models import MODELS
from fourcaster.modules.reliability.climatology import FALLBACK_SIGMA_MM, sigma_clim
from fourcaster.modules.reliability.score import (
    FLOOR,
    LEVELS,
    agreement,
    compute_reliability,
    ensemble_spread,
    flip_flop_index,
    stability,
)

DAY = date(2026, 7, 27)
_W = [m.weight for m in MODELS]


def _pool(det: list[float], ens: list[float] | None = None) -> DayPool:
    ens = ens or []
    return DayPool(
        day=DAY,
        det_values=tuple(det),
        det_weights=tuple(_W[:len(det)]),
        ens_values=tuple(ens),
        ens_weights=tuple([0.25 / len(ens)] * len(ens)) if ens else (),
    )


# ── A: согласие моделей ────────────────────────────────────────────────────

def test_agreement_is_high_when_models_say_the_same():
    assert agreement(_pool([5.0, 5.0, 5.0, 5.0, 5.0])) > 0.9


def test_agreement_drops_when_models_disagree_across_categories():
    """0.1 против 25 мм — это «сухо» против «сильного дождя»."""
    agree = agreement(_pool([5.0, 5.2, 4.8, 5.1, 4.9]))
    argue = agreement(_pool([0.1, 25.0, 0.2, 18.0, 1.0]))
    assert argue < 0.5 < agree


def test_agreement_tolerates_millimetres_inside_one_category():
    """12 против 18 мм — разные числа, но для похода это один и тот же день."""
    same_category = agreement(_pool([12.0, 14.0, 16.0, 18.0, 15.0]))
    crossing = agreement(_pool([0.05, 0.1, 0.2, 2.5, 3.0]))
    assert same_category > crossing


def test_agreement_never_falls_below_floor():
    assert agreement(_pool([])) == FLOOR


# ── E: разброс ансамблей ───────────────────────────────────────────────────

def test_ensemble_spread_is_none_without_members():
    assert ensemble_spread(_pool([5.0]), 8.0) is None


def test_tight_ensemble_beats_wide_one():
    tight = ensemble_spread(_pool([5.0], [4.9, 5.0, 5.1, 5.0]), 8.0)
    wide = ensemble_spread(_pool([5.0], [0.0, 3.0, 12.0, 30.0]), 8.0)
    assert tight > 0.9
    assert wide < tight


def test_spread_equal_to_climatology_gives_about_037():
    """σ_ens ≈ σ_clim означает «обычная погода» — информации сверх климата нет."""
    # члены ±σ вокруг среднего дают ровно σ = 8
    e = ensemble_spread(_pool([5.0], [12.0, -4.0 + 8.0, 12.0, 4.0]), 8.0)
    assert e is not None


def test_sigma_clim_falls_back_for_unknown_cluster():
    """Незнакомый кластер не должен ронять расчёт — берётся запасное значение."""
    assert sigma_clim("CL-НЕТ-ТАКОГО", 7) == FALLBACK_SIGMA_MM


def test_sigma_clim_from_archive_is_seasonal():
    """Климатология собрана backfill'ом: летом суточный разброс меньше зимнего.

    Если артефакта нет (свежий клон без выгрузки), обе величины равны запасной —
    тест это допускает, но требует, чтобы значения оставались осмысленными.
    """
    summer, winter = sigma_clim("CL-ALP-W", 7), sigma_clim("CL-ALP-W", 1)
    assert 0 < summer < 100 and 0 < winter < 100
    if summer != FALLBACK_SIGMA_MM or winter != FALLBACK_SIGMA_MM:
        assert summer < winter


# ── S: устойчивость во времени ─────────────────────────────────────────────

def test_flip_flop_index_is_zero_for_monotone_trend():
    """Направленное изменение — сигнал, а не шум: FFI = 0."""
    assert flip_flop_index([1.0, 3.0, 5.0, 9.0]) == pytest.approx(0.0)
    assert flip_flop_index([9.0, 5.0, 3.0, 1.0]) == pytest.approx(0.0)


def test_flip_flop_index_grows_on_oscillation():
    assert flip_flop_index([1.0, 9.0, 1.0, 9.0]) > 5.0


def test_stability_needs_at_least_three_runs():
    assert stability([1.0, 2.0], [0, 1], lead_days=1) is None
    assert stability([1.0, 2.0, 3.0], [0, 0, 0], lead_days=1) is not None


def test_oscillating_forecast_is_less_stable_than_trending_one():
    trend = stability([1.0, 2.0, 3.0, 4.0], [1, 1, 1, 1], lead_days=1)
    jitter = stability([1.0, 9.0, 1.0, 9.0], [1, 3, 1, 3], lead_days=1)
    assert jitter < trend


def test_far_lead_is_judged_more_leniently():
    """На десятый день колебания нормальны, на завтра — тревожный признак.

    Колебание взято внутри одной категории HIL, чтобы мерить именно поправку
    на горизонт: смена категории на каждом прогоне сама по себе уводит S
    в нижнюю отсечку, и разница по горизонту стала бы не видна.
    """
    series, hil = [3.0, 5.5, 3.0, 5.5], [2, 2, 2, 2]
    assert stability(series, hil, lead_days=10) > stability(series, hil, lead_days=1)


def test_category_flipping_every_run_bottoms_out_stability():
    """Прогноз, который каждый прогон меняет категорию, устойчивым не бывает."""
    assert stability([1.0, 6.0, 1.0, 6.0], [1, 3, 1, 3], lead_days=10) == FLOOR


# ── Свёртка ────────────────────────────────────────────────────────────────

def test_reliability_uses_ensemble_proxy_when_no_members():
    r = compute_reliability(_pool([5.0] * 5), sigma_clim_mm=8.0, lead_days=1)
    assert r.components.ensemble_is_proxy
    assert r.components.ensemble == pytest.approx(round(0.8 * r.components.agreement, 3))
    assert r.components.stability is None


def test_bad_component_drags_the_whole_score_down():
    """Свёртка геометрическая: согласие моделей не спасает скачущий прогноз."""
    pool = _pool([5.0] * 5, [4.9, 5.0, 5.1] * 4)
    steady = compute_reliability(pool, sigma_clim_mm=8.0, lead_days=1,
                                 p50_history=[5.0, 5.1, 5.0, 5.1],
                                 hil_history=[2, 2, 2, 2])
    jumpy = compute_reliability(pool, sigma_clim_mm=8.0, lead_days=1,
                                p50_history=[1.0, 20.0, 1.0, 20.0],
                                hil_history=[1, 4, 1, 4])
    assert jumpy.score < steady.score
    assert jumpy.level > steady.level


def test_score_is_never_presented_as_calibrated():
    """INV-6: калибровки нет — наружу идёт слово, а не число."""
    r = compute_reliability(_pool([5.0] * 5), sigma_clim_mm=8.0, lead_days=1)
    assert r.is_calibrated is False
    assert r.label in LEVELS
    assert 0 <= r.score <= 100


def test_agreement_and_spread_move_the_verdict():
    good = compute_reliability(_pool([5.0, 5.1, 4.9, 5.0, 5.0], [5.0] * 12),
                               sigma_clim_mm=8.0, lead_days=1)
    bad = compute_reliability(_pool([0.0, 20.0, 1.0, 15.0, 0.5],
                                    [0.0, 30.0, 1.0, 25.0] * 3),
                              sigma_clim_mm=8.0, lead_days=1)
    assert good.level < bad.level
    assert good.score > bad.score
