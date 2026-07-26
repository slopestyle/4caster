"""Правила значимости изменений (PRD §10.9, упрощённо для MVP).

Значимым считаем изменение на ближнем горизонте (первые дни), если:
- категория HIL сдвинулась на ≥2 уровня, ИЛИ
- вероятность осадков перешла порог 0.5 при ощутимой дельте осадков (≥3 мм).

Сравнение идёт с предыдущим прогоном, поэтому одно и то же изменение
срабатывает один раз (следующий прогон уже сравнивается с новым состоянием) —
это естественный анти-флаппинг для MVP.
"""

from __future__ import annotations

from dataclasses import dataclass

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.hazard.rain import classify_hil

HORIZON_DAYS = 4      # следим за ближними днями
HIL_JUMP = 2          # сдвиг категории
POP_THRESHOLD = 0.5   # порог вероятности
PRECIP_DELTA = 3.0    # мм, минимальная значимая дельта осадков


@dataclass(frozen=True, slots=True)
class Change:
    valid_date: str
    was_hil: int
    now_hil: int
    was_p50: float
    now_p50: float
    was_pop: float
    now_pop: float

    @property
    def worse(self) -> bool:
        return self.now_hil > self.was_hil or self.now_p50 > self.was_p50


def detect_changes(previous: dict, new_days: list[DayConsensus]) -> list[Change]:
    """previous — {valid_date_iso: {p50, pop, hil_level}} из прошлого прогона."""
    if not previous:
        return []  # первый прогон — сравнивать не с чем
    changes: list[Change] = []
    for d in new_days[:HORIZON_DAYS]:
        key = d.day.isoformat()
        prev = previous.get(key)
        if prev is None:
            continue
        now_hil = classify_hil(d.p50).level
        was_hil = int(prev["hil_level"])
        pop_crossed = (prev["pop"] < POP_THRESHOLD) != (d.pop < POP_THRESHOLD)
        big_precip = abs(d.p50 - prev["p50"]) >= PRECIP_DELTA
        if abs(now_hil - was_hil) >= HIL_JUMP or (pop_crossed and big_precip):
            changes.append(Change(
                valid_date=key, was_hil=was_hil, now_hil=now_hil,
                was_p50=round(prev["p50"], 1), now_p50=round(d.p50, 1),
                was_pop=round(prev["pop"], 2), now_pop=round(d.pop, 2),
            ))
    return changes
