"""Расчёт консенсуса: взвешенные перцентили + POP (PRD §10.5).

Для каждого валидного дня строится взвешенный пул членов (по одному
члену на модель в срезе) и считаются перцентили p10/p50/p90 и
вероятность осадков POP. Сумма нормированных весов = 1.0 (INV-3);
каждая модель учтена один раз (INV-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np

from fourcaster.modules.forecasting.normalize import ModelSnapshot


@dataclass(frozen=True, slots=True)
class DayConsensus:
    day: date
    p10: float
    p50: float
    p90: float
    pop: float           # вероятность осадков > 0.1 мм, 0..1
    n_models: int        # сколько моделей участвовало в дне


def weighted_percentile(
    values: np.ndarray, weights: np.ndarray, q: float
) -> float:
    """Взвешенный перцентиль q∈[0,1] методом линейной интерполяции по
    накопленному нормированному весу."""

    order = np.argsort(values)
    v = values[order]
    w = weights[order]
    cum = np.cumsum(w) - 0.5 * w
    cum /= w.sum()
    return float(np.interp(q, cum, v))


def _first_future_hour(times: list[str], now: datetime) -> int:
    """Индекс первого часа ряда, который ещё не прошёл (текущий час включительно).

    Метки времени Open-Meteo — наивный ISO в UTC (`timezone=UTC`), напр.
    `2026-07-26T14:00`. Если ряд целиком в прошлом — возвращаем его длину
    (окно окажется пустым, UI покажет «нет данных»), если целиком в будущем — 0.
    """
    cur = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0, tzinfo=None)
    for i, t in enumerate(times):
        try:
            ts = datetime.fromisoformat(t)
        except ValueError:      # неожиданный формат — не режем ряд
            return 0
        if ts.tzinfo is not None:
            ts = ts.astimezone(UTC).replace(tzinfo=None)
        if ts >= cur:
            return i
    return len(times)


def compute_hourly(
    series: list[dict], *, max_hours: int = 48, now: datetime | None = None
) -> dict:
    """Часовой консенсус осадков по моделям для метеограммы (US-FC-2).

    series — сырые часовые ряды из Open-Meteo: [{model_openmeteo_id, times,
    precip, pop}]. Возвращает выровненные массивы p10/p50/p90 и POP по часам.

    Окно — ровно `max_hours` часов **от текущего часа UTC**, а не от начала
    суток: провайдер отдаёт ряд с 00:00 UTC, и без обрезки «48 часов» молча
    превращались бы в «до конца завтрашнего дня». Прошедшие часы отбрасываются.
    """
    from fourcaster.modules.consensus.models import BY_OPENMETEO_ID

    known = [s for s in series if s["model_openmeteo_id"] in BY_OPENMETEO_ID]
    if not known:
        return {"times": [], "p10": [], "p50": [], "p90": [], "pop": []}

    ref = known[0]["times"]
    start = _first_future_hour(ref, now or datetime.now(UTC))
    total = min(len(s["times"]) for s in known)
    n = min(max_hours, max(0, total - start))
    times = ref[start:start + n]
    weights_all = np.asarray(
        [BY_OPENMETEO_ID[s["model_openmeteo_id"]].weight for s in known], dtype=float
    )

    p10, p50, p90, pop = [], [], [], []
    for k in range(n):
        i = start + k
        vals = np.asarray([s["precip"][i] for s in known], dtype=float)
        w = weights_all / weights_all.sum()
        p10.append(round(weighted_percentile(vals, w, 0.10), 2))
        p50.append(round(weighted_percentile(vals, w, 0.50), 2))
        p90.append(round(weighted_percentile(vals, w, 0.90), 2))
        probs, pw = [], []
        for s, wi in zip(known, weights_all):
            v = s["pop"][i]
            if v is not None:
                probs.append(v)
                pw.append(wi)
        if probs:
            pop.append(round(float(np.average(probs, weights=np.asarray(pw))), 2))
        else:
            pop.append(round(float(w[vals > 0.1].sum()), 2))

    return {"times": times, "p10": p10, "p50": p50, "p90": p90, "pop": pop}


def compute_consensus(
    snapshots: list[ModelSnapshot], *, max_days: int
) -> list[DayConsensus]:
    if not snapshots:
        return []

    # общий календарь дней (пересечение по позиции — ряды выровнены по UTC)
    n_days = min(max_days, min(len(s.dates) for s in snapshots))
    ref_dates = snapshots[0].dates

    result: list[DayConsensus] = []
    for i in range(n_days):
        vals: list[float] = []
        wts: list[float] = []
        probs: list[float] = []
        prob_wts: list[float] = []
        for s in snapshots:
            v = s.precip_total_mm[i]
            if v is None:
                continue  # модель не покрывает этот день — вне пула
            vals.append(v)
            wts.append(s.model.weight)
            p = s.precip_probability[i]
            if p is not None:
                probs.append(p)
                prob_wts.append(s.model.weight)

        if not vals:
            continue  # день не покрыт ни одной моделью — горизонт закончился

        values = np.asarray(vals, dtype=float)
        weights = np.asarray(wts, dtype=float)
        weights = weights / weights.sum()  # нормировка (INV-3)

        if probs:
            pw = np.asarray(prob_wts, dtype=float)
            pop = float(np.average(probs, weights=pw))
        else:
            # запасной POP: доля веса моделей, давших > 0.1 мм
            pop = float(weights[values > 0.1].sum())

        result.append(
            DayConsensus(
                day=ref_dates[i],
                p10=round(weighted_percentile(values, weights, 0.10), 1),
                p50=round(weighted_percentile(values, weights, 0.50), 1),
                p90=round(weighted_percentile(values, weights, 0.90), 1),
                pop=round(pop, 2),
                n_models=len(vals),
            )
        )
    return result
