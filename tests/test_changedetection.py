"""Тесты правил значимости изменений (офлайн)."""

from __future__ import annotations

from datetime import date

from fourcaster.modules.changedetection import detect_changes
from fourcaster.modules.consensus.calculator import DayConsensus


def _day(p50, pop):
    return DayConsensus(day=date(2026, 7, 26), p10=0.0, p50=p50, p90=p50 + 2,
                        pop=pop, n_models=5)


def test_no_previous_no_changes():
    assert detect_changes({}, [_day(20.0, 0.9)]) == []


def test_hil_jump_triggers():
    prev = {"2026-07-26": {"p50": 0.2, "pop": 0.1, "hil_level": 0}}  # сухо
    changes = detect_changes(prev, [_day(20.0, 0.95)])  # сильный дождь
    assert len(changes) == 1
    assert changes[0].worse is True


def test_stable_forecast_no_change():
    prev = {"2026-07-26": {"p50": 0.4, "pop": 0.2, "hil_level": 0}}
    assert detect_changes(prev, [_day(0.5, 0.25)]) == []


def test_pop_crossing_with_precip_delta_triggers():
    prev = {"2026-07-26": {"p50": 1.0, "pop": 0.3, "hil_level": 1}}
    changes = detect_changes(prev, [_day(6.0, 0.7)])  # POP пересёк 0.5, +5 мм
    assert len(changes) == 1
