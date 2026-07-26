"""Юнит-тесты ядра консенсуса (INV-3, INV-4) и взвешенных перцентилей."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import numpy as np

from fourcaster.modules.consensus.calculator import (
    compute_consensus,
    compute_hourly,
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


# ── часовой консенсус: окно «48 ч от текущего часа» ──────────────────────────

def _hourly_series(start: datetime, hours: int) -> list[dict]:
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return [
        {
            "model_openmeteo_id": m.openmeteo_id,
            "times": times,
            "precip": [float(i % 3) for i in range(hours)],
            "pop": [0.5] * hours,
        }
        for m in MODELS[:3]
    ]


def test_hourly_window_starts_at_current_hour_not_midnight():
    # ряд провайдера начинается в 00:00 UTC текущих суток (72 ч = 3 суток)
    series = _hourly_series(datetime(2026, 7, 26, 0, 0), 72)
    now = datetime(2026, 7, 26, 14, 37, tzinfo=UTC)
    out = compute_hourly(series, now=now)
    assert out["times"][0] == "2026-07-26T14:00"     # текущий час, а не полночь
    assert len(out["times"]) == 48                   # ровно 48 ч вперёд
    assert out["times"][-1] == "2026-07-28T13:00"


def test_hourly_window_is_capped_by_available_hours():
    # двух суток от полуночи не хватает на 48 ч вперёд — отдаём что есть
    series = _hourly_series(datetime(2026, 7, 26, 0, 0), 48)
    out = compute_hourly(series, now=datetime(2026, 7, 26, 10, 0, tzinfo=UTC))
    assert out["times"][0] == "2026-07-26T10:00"
    assert len(out["times"]) == 38
    assert len(out["p50"]) == len(out["pop"]) == 38
