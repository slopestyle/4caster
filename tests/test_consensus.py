"""Юнит-тесты ядра консенсуса (INV-3, INV-4) и взвешенных перцентилей."""

from __future__ import annotations

from datetime import date

import numpy as np

from fourcaster.modules.consensus.calculator import (
    compute_consensus,
    weighted_percentile,
)
from fourcaster.modules.consensus.models import MODELS
from fourcaster.modules.forecasting.normalize import ModelSnapshot


def _snapshot(model, precip: list[float], prob: list[float | None]):
    days = tuple(date(2026, 7, 25 + i) for i in range(len(precip)))
    return ModelSnapshot(model=model, dates=days,
                         precip_total_mm=tuple(precip),
                         precip_probability=tuple(prob))


def test_weighted_percentile_equal_weights_matches_numpy():
    values = np.array([0.0, 2.0, 5.0, 10.0, 20.0])
    weights = np.full(5, 0.2)
    # медиана при равных весах ≈ обычная медиана
    assert abs(weighted_percentile(values, weights, 0.5) - 5.0) < 1e-9


def test_p50_between_p10_and_p90():
    snaps = [
        _snapshot(MODELS[0], [10.0], [0.9]),
        _snapshot(MODELS[1], [2.0], [0.4]),
        _snapshot(MODELS[2], [0.0], [0.1]),
    ]
    day = compute_consensus(snaps, max_days=1)[0]
    assert day.p10 <= day.p50 <= day.p90
    assert day.n_models == 3


def test_pop_is_weighted_average_of_probabilities():
    # две модели: веса 0.30 (IFS) и 0.28 (ICON), вероятности 1.0 и 0.0
    snaps = [_snapshot(MODELS[0], [5.0], [1.0]), _snapshot(MODELS[1], [0.0], [0.0])]
    day = compute_consensus(snaps, max_days=1)[0]
    expected = 0.30 / (0.30 + 0.28)
    assert abs(day.pop - round(expected, 2)) < 0.02


def test_higher_weight_model_pulls_p50():
    # тяжёлая модель (IFS 0.30) сухо, лёгкая (ARPEGE 0.08) — дождь
    heavy_dry = [_snapshot(MODELS[0], [0.0], [0.0]), _snapshot(MODELS[4], [20.0], [1.0])]
    day = compute_consensus(heavy_dry, max_days=1)[0]
    assert day.p50 < 10.0  # медиана смещена к сухому сценарию
