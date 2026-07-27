"""Ансамбли: разбор ответа, агрегация в сутки и пул членов (PRD §8.2, §10.5.1)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from fourcaster.modules.consensus.calculator import (
    POP_THRESHOLD_MM,
    build_pools,
    consensus_from_pool,
)
from fourcaster.modules.consensus.models import ENSEMBLES, MODELS, EnsembleModel
from fourcaster.modules.forecasting.normalize import (
    EnsembleSnapshot,
    ModelSnapshot,
    normalize_ensemble,
)
from fourcaster.modules.ingestion.infrastructure.openmeteo.client import (
    _daily_sums,
    parse_ensemble_payload,
)

_FIXTURES = Path(__file__).parent / "fixtures"
_KEYS = [e.response_key for e in ENSEMBLES]


def _payload() -> dict:
    return json.loads((_FIXTURES / "ensemble_achishkho.json").read_text("utf-8"))


# ── ACL: разбор ответа ensemble-api ────────────────────────────────────────

def test_parse_splits_response_by_ensemble_and_keeps_all_members():
    series = {s.ensemble_openmeteo_id: s for s in parse_ensemble_payload(_payload(), _KEYS)}
    assert set(series) == set(_KEYS)
    for ens in ENSEMBLES:
        # контрольный член + возмущённые: столько, сколько заявлено в реестре
        assert len(series[ens.response_key].members) == ens.n_members, ens.id


def test_daily_sums_aggregate_hours_and_reject_incomplete_day():
    """Осадки — ACCUMULATED: сутки = сумма часов, неполные сутки → None."""
    full = ["2026-07-27"] * 24 + ["2026-07-28"] * 24
    values = [0.5] * 24 + [1.0] * 12 + [None] * 12
    days, sums = _daily_sums(full, values)
    assert days == (date(2026, 7, 27), date(2026, 7, 28))
    assert sums[0] == pytest.approx(12.0)
    assert sums[1] is None, "12 часов из 24 — это не «12 мм за сутки», а «нет данных»"


def test_parse_ignores_unknown_ensemble_key():
    assert parse_ensemble_payload(_payload(), ["neizvestny_ansambl"]) == []


# ── Пул членов §10.5.1 ─────────────────────────────────────────────────────

def _det(model, values: list[float | None], day0=date(2026, 7, 27)) -> ModelSnapshot:
    days = tuple(date.fromordinal(day0.toordinal() + i) for i in range(len(values)))
    return ModelSnapshot(model=model, dates=days,
                         precip_total_mm=tuple(values),
                         precip_probability=tuple(None for _ in values))


def _ens(ensemble: EnsembleModel, members: list[list[float | None]],
         day0=date(2026, 7, 27)) -> EnsembleSnapshot:
    n = len(members[0])
    days = tuple(date.fromordinal(day0.toordinal() + i) for i in range(n))
    return EnsembleSnapshot(ensemble=ensemble, dates=days,
                            members=tuple(tuple(m) for m in members))


def test_ensemble_weight_is_split_between_members():
    """Ансамбль из N членов весит столько же, сколько весит сам, а не в N раз больше."""
    ens = ENSEMBLES[0]
    pool = build_pools([_det(MODELS[0], [5.0])],
                       [_ens(ens, [[1.0], [2.0], [3.0], [4.0]])],
                       max_days=1)[0]
    assert pool.n_models == 1
    assert pool.n_members == 5
    raw_total = sum(pool.det_weights) + sum(pool.ens_weights)
    assert sum(pool.ens_weights) == pytest.approx(ens.weight)
    assert float(pool.weights.sum()) == pytest.approx(1.0)   # INV-3
    assert pool.weights[0] == pytest.approx(MODELS[0].weight / raw_total)


def test_uncovered_members_do_not_shrink_ensemble_weight():
    """Если день покрыла половина членов, ансамбль сохраняет свой вес целиком."""
    ens = ENSEMBLES[0]
    pools = build_pools([_det(MODELS[0], [5.0, 5.0])],
                        [_ens(ens, [[1.0, 2.0], [3.0, None]])],
                        max_days=2)
    assert [p.n_members for p in pools] == [3, 2]
    for pool in pools:
        assert sum(pool.ens_weights) == pytest.approx(ens.weight)


def test_pool_is_keyed_by_date_not_by_position():
    """Ряды из разных эндпоинтов могут начинаться с разных суток — сдвиг на
    день означал бы прогноз не на тот день."""
    ens = ENSEMBLES[0]
    pools = build_pools(
        [_det(MODELS[0], [1.0, 2.0], day0=date(2026, 7, 27))],
        [_ens(ens, [[9.0, 9.0]], day0=date(2026, 7, 28))],
        max_days=3,
    )
    by_day = {p.day: p for p in pools}
    assert by_day[date(2026, 7, 27)].ens_values == ()
    assert by_day[date(2026, 7, 28)].ens_values == (9.0,)
    assert by_day[date(2026, 7, 29)].det_values == ()


def test_pooled_pop_counts_weight_above_threshold():
    """POP по пулу (§10.5.1): доля веса членов, давших больше порога."""
    ens = ENSEMBLES[0]
    wet = [[1.0]] * 6                       # шесть мокрых членов
    dry = [[0.0]] * 6                       # шесть сухих
    pool = build_pools([], [_ens(ens, wet + dry)], max_days=1)[0]
    assert pool.n_members == 12
    assert consensus_from_pool(pool).pop == pytest.approx(0.5)


def test_small_pool_falls_back_to_provider_probability():
    """Пять детерминированных значений дают вероятность с шагом ~0.2 —
    для такого дня берём вероятность провайдера."""
    days = (date(2026, 7, 27),)
    snapshots = [
        ModelSnapshot(model=m, dates=days, precip_total_mm=(5.0,),
                      precip_probability=(0.9,))
        for m in MODELS
    ]
    pool = build_pools(snapshots, [], max_days=1)[0]
    assert pool.n_members == len(MODELS)
    assert consensus_from_pool(pool).pop == pytest.approx(0.9)


def test_threshold_matches_prd():
    assert POP_THRESHOLD_MM == 0.2


# ── Ограничители весов §10.5.3 ─────────────────────────────────────────────

def test_weight_guardrails_hold_for_registry():
    from fourcaster.modules.consensus.models import _check_guardrails
    _check_guardrails()          # не должен бросить на текущем реестре
    total = sum(m.weight for m in MODELS) + sum(e.weight for e in ENSEMBLES)
    assert total == pytest.approx(1.0)
    assert sum(e.weight for e in ENSEMBLES) <= 0.45
    for ens in ENSEMBLES:
        sibling = next((m for m in MODELS if m.id == ens.sibling_id), None)
        if sibling is not None:
            # ансамбль и его детерминированный «брат» — одна система (§10.5.3)
            assert ens.weight + sibling.weight <= 0.50, ens.id
