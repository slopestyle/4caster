"""Расчёт консенсуса: единый взвешенный пул членов (PRD §10.5).

Для каждого валидного дня строится пул членов §10.5.1: детерминированная
модель даёт один член с весом `w_i`, ансамбль из N членов — N членов с весом
`w_j / N` каждый. Из пула берутся перцентили p10/p25/p50/p75/p90 и POP.
Сумма нормированных весов = 1.0 (INV-3); каждая модель учтена один раз (INV-4).

Среднее по осадкам не считается и не публикуется: распределение сильно
скошено, и одна «мокрая» модель уводит среднее туда, где не находится ни один
из сценариев (§10.5.1).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from fourcaster.modules.forecasting.normalize import EnsembleSnapshot, ModelSnapshot

# Порог «был дождь» для POP по §10.5.1.
POP_THRESHOLD_MM = 0.2
# Ниже этого размера пула вероятность по долям веса слишком грубая (пять
# детерминированных моделей дают шаг ~0.2), и честнее взять вероятность,
# посчитанную самим провайдером.
POOLED_POP_MIN_MEMBERS = 10


@dataclass(frozen=True, slots=True)
class DayPool:
    """Пул членов на одни сутки (§10.5.1).

    Детерминированная и ансамблевая части хранятся раздельно: консенсус
    считается по объединению, а надёжность — по частям (компонента A смотрит
    только на согласие независимых моделей, E — только на разброс членов).
    """

    day: date
    det_values: tuple[float, ...] = ()
    det_weights: tuple[float, ...] = ()
    det_probabilities: tuple[float, ...] = ()
    det_prob_weights: tuple[float, ...] = ()
    ens_values: tuple[float, ...] = ()
    ens_weights: tuple[float, ...] = ()
    det_temp_max: tuple[float, ...] = ()
    det_temp_min: tuple[float, ...] = ()
    provider_elevation_m: float | None = None    # FR-DS-2

    @property
    def values(self) -> np.ndarray:
        return np.asarray(self.det_values + self.ens_values, dtype=float)

    @property
    def weights(self) -> np.ndarray:
        """Веса всего пула, нормированные к единице (INV-3)."""
        w = np.asarray(self.det_weights + self.ens_weights, dtype=float)
        return w / w.sum()

    @property
    def n_models(self) -> int:
        return len(self.det_values)

    @property
    def n_members(self) -> int:
        return len(self.det_values) + len(self.ens_values)


@dataclass(frozen=True, slots=True)
class DayConsensus:
    day: date
    p10: float
    p50: float
    p90: float
    pop: float           # вероятность осадков > 0.2 мм, 0..1
    n_models: int        # сколько детерминированных моделей участвовало в дне
    p25: float = 0.0
    p75: float = 0.0
    n_members: int = 0   # размер пула вместе с членами ансамблей
    temp_max_c: float | None = None   # медиана по моделям, до коррекции §10.3
    temp_min_c: float | None = None


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


def build_pools(
    snapshots: list[ModelSnapshot],
    ensembles: list[EnsembleSnapshot] | None = None,
    *,
    max_days: int,
) -> list[DayPool]:
    """Сборка пула членов по суткам (§10.5.1).

    Дни собираются по календарной дате, а не по позиции в ряду: детерминированные
    и ансамблевые ряды приходят из разных эндпоинтов и могут начинаться с разных
    суток, а сдвиг на день здесь означал бы прогноз не на тот день.
    """
    det_v: dict[date, list[float]] = defaultdict(list)
    det_w: dict[date, list[float]] = defaultdict(list)
    det_p: dict[date, list[float]] = defaultdict(list)
    det_pw: dict[date, list[float]] = defaultdict(list)
    ens_v: dict[date, list[float]] = defaultdict(list)
    ens_w: dict[date, list[float]] = defaultdict(list)
    t_max: dict[date, list[float]] = defaultdict(list)
    t_min: dict[date, list[float]] = defaultdict(list)
    provider_elevation: float | None = None

    for snapshot in snapshots:
        provider_elevation = snapshot.provider_elevation_m or provider_elevation
        n = len(snapshot.dates)
        temps_max = snapshot.temp_max_c or (None,) * n
        temps_min = snapshot.temp_min_c or (None,) * n
        for day, value, prob, hi, lo in zip(
            snapshot.dates, snapshot.precip_total_mm, snapshot.precip_probability,
            temps_max, temps_min,
        ):
            if value is None:
                continue  # модель не покрывает этот день — вне пула
            det_v[day].append(value)
            det_w[day].append(snapshot.model.weight)
            if prob is not None:
                det_p[day].append(prob)
                det_pw[day].append(snapshot.model.weight)
            if hi is not None:
                t_max[day].append(hi)
            if lo is not None:
                t_min[day].append(lo)

    for ens in ensembles or ():
        # Вес ансамбля делится между членами, реально покрывшими день: если на
        # дальнем дне ответила половина членов, ансамбль не должен из-за этого
        # потерять половину своего веса в пуле.
        covered: dict[date, list[float]] = defaultdict(list)
        for member in ens.members:
            for day, value in zip(ens.dates, member):
                if value is not None:
                    covered[day].append(value)
        for day, values in covered.items():
            ens_v[day].extend(values)
            ens_w[day].extend([ens.ensemble.weight / len(values)] * len(values))

    days = sorted(set(det_v) | set(ens_v))[:max_days]
    return [
        DayPool(
            day=day,
            det_values=tuple(det_v[day]),
            det_weights=tuple(det_w[day]),
            det_probabilities=tuple(det_p[day]),
            det_prob_weights=tuple(det_pw[day]),
            ens_values=tuple(ens_v[day]),
            ens_weights=tuple(ens_w[day]),
            det_temp_max=tuple(t_max[day]),
            det_temp_min=tuple(t_min[day]),
            provider_elevation_m=provider_elevation,
        )
        for day in days
    ]


def compute_consensus(
    snapshots: list[ModelSnapshot],
    *,
    max_days: int,
    ensembles: list[EnsembleSnapshot] | None = None,
) -> list[DayConsensus]:
    return [consensus_from_pool(p) for p in build_pools(snapshots, ensembles, max_days=max_days)]


def consensus_from_pool(pool: DayPool) -> DayConsensus:
    values, weights = pool.values, pool.weights
    return DayConsensus(
        day=pool.day,
        p10=round(weighted_percentile(values, weights, 0.10), 1),
        p25=round(weighted_percentile(values, weights, 0.25), 1),
        p50=round(weighted_percentile(values, weights, 0.50), 1),
        p75=round(weighted_percentile(values, weights, 0.75), 1),
        p90=round(weighted_percentile(values, weights, 0.90), 1),
        pop=round(_pop(pool, values, weights), 2),
        n_models=pool.n_models,
        n_members=pool.n_members,
        temp_max_c=_median(pool.det_temp_max),
        temp_min_c=_median(pool.det_temp_min),
    )


def _median(values: tuple[float, ...]) -> float | None:
    """Медиана по моделям — устойчива к одной выпавшей из строя модели."""
    return round(float(np.median(values)), 1) if values else None


def _pop(pool: DayPool, values: np.ndarray, weights: np.ndarray) -> float:
    """Вероятность осадков.

    При достаточно большом пуле — прямо по нему (§10.5.1): доля веса членов,
    давших больше порога. Это то же самое, что вероятность по эмпирической CDF,
    и с 82 членами ансамблей она хорошо разрешена. Если ансамблей на этот день
    нет, пул вырождается в пять детерминированных значений: доля веса дала бы
    вероятность с шагом ~0.2, поэтому берём вероятность от провайдера.
    """
    if pool.n_members >= POOLED_POP_MIN_MEMBERS:
        return float(weights[values > POP_THRESHOLD_MM].sum())
    if pool.det_probabilities:
        return float(np.average(
            pool.det_probabilities, weights=np.asarray(pool.det_prob_weights)
        ))
    return float(weights[values > POP_THRESHOLD_MM].sum())
