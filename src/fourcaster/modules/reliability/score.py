"""Компоненты Reliability Score A, E, S и их свёртка (PRD §10.6).

Что здесь есть:

- **A — Inter-Model Agreement.** Насколько независимые модели говорят одно и
  то же: непрерывная часть по межквартильному размаху и категориальная — по
  доле веса, согласной с операционной категорией HIL.
- **E — Ensemble Spread.** Разброс членов ансамблей относительно
  климатического. Если ансамблей на этот день нет, §10.6 предписывает заменять
  E на A с коэффициентом 0.8 — и говорить об этом вслух.
- **S — Temporal Stability.** Flip-Flop Index по последним прогонам на ту же
  дату: прогноз может показывать отличное согласие моделей прямо сейчас и при
  этом скакать от рана к рану.

Чего здесь нет: компоненты H (историческая оправдываемость), G (предсказуемость
режима) и D (полнота данных) требуют Accuracy Engine — Фаза 3, §10.8. Веса α
недостающих компонент перераспределяются между имеющимися.

**Число наружу не отдаётся.** Пока нет калибровки (§10.6.4), скор — эвристика;
INV-6 требует помечать его `is_calibrated = false` и показывать качественной
шкалой. Отсюда `Reliability.level` и `Reliability.label` — их и печатает UI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from fourcaster.modules.consensus.calculator import DayPool, weighted_percentile
from fourcaster.modules.hazard.rain import classify_hil

# Веса компонент §10.6.2 (стартовые). Сумма по имеющимся нормируется.
ALPHA = {"agreement": 0.28, "ensemble": 0.22, "stability": 0.20}

# Нижняя отсечка компонент §10.6.2: одна плохая компонента не должна обнулять
# итог, иначе скор перестаёт различать «плохо» и «очень плохо».
FLOOR = 0.05

K_A = 1.2          # масштаб непрерывной части согласия (§10.6.2, компонента A)
P0_MM = 1.0        # регуляризатор: не даёт метрике взорваться на малых осадках
LAMBDA_E = 1.0     # масштаб компоненты E

# k_S(lead) = K_S0 + K_S1 · lead: на десятый день колебания прогноза нормальны,
# на завтра — тревожный признак. Значения провизорные: §10.6 требует
# калибровать их по истории, а история копится только с апреля 2026.
K_S0, K_S1 = 2.0, 0.8
FFI_MIN_POINTS = 3          # FFI определён с трёх точек (в знаменателе n−2)

# Качественная шкала §10.6.4. Пороги подобраны так, чтобы совпадать со
# словами, которые Mini App уже говорит пользователю.
LEVELS = ("надёжно", "осторожно", "низкая", "не опираться")
LEVEL_EDGES = (0.70, 0.50, 0.30)


@dataclass(frozen=True, slots=True)
class ReliabilityComponents:
    agreement: float                  # A ∈ [0.05, 1]
    ensemble: float                   # E ∈ [0.05, 1]
    stability: float | None           # S, None — истории не хватает
    ensemble_is_proxy: bool           # E получена из A (ансамблей не было)
    n_models: int
    n_members: int
    n_history_runs: int


@dataclass(frozen=True, slots=True)
class Reliability:
    """Итог по одним суткам. `score` — сырой, наружу идёт `level`/`label`."""

    day: date
    score: int                        # R_raw, 0..100
    level: int                        # 0 «надёжно» … 3 «не опираться»
    components: ReliabilityComponents
    is_calibrated: bool = False       # INV-6: калибровки пока нет (§10.6.4)

    @property
    def label(self) -> str:
        return LEVELS[self.level]


def _clamp(value: float) -> float:
    return min(1.0, max(FLOOR, value))


def agreement(pool: DayPool) -> float:
    """Компонента A = √(A_cont · A_cat) по детерминированным моделям."""
    if not pool.det_values:
        return FLOOR
    values = np.asarray(pool.det_values, dtype=float)
    weights = np.asarray(pool.det_weights, dtype=float)
    weights = weights / weights.sum()

    iqr = (weighted_percentile(values, weights, 0.75)
           - weighted_percentile(values, weights, 0.25))
    median = weighted_percentile(values, weights, 0.50)
    a_cont = math.exp(-iqr / (K_A * (median + P0_MM)))

    # A_cat: максимальная доля веса, согласная по категории HIL. Модели могут
    # разойтись в миллиметрах (12 против 18), оставаясь в одной операционной
    # категории, — для похода это согласие; и наоборот, 0.1 против 2.5 мм —
    # мелочь в миллиметрах, но переход через «сухо/мокро».
    by_category: dict[int, float] = {}
    for value, weight in zip(values, weights):
        level = classify_hil(float(value)).level
        by_category[level] = by_category.get(level, 0.0) + float(weight)
    a_cat = max(by_category.values())

    return _clamp(math.sqrt(a_cont * a_cat))


def ensemble_spread(pool: DayPool, sigma_clim_mm: float) -> float | None:
    """Компонента E = exp(−λ · σ_ens / σ_clim). None, если ансамблей нет.

    Смысл: если разброс членов сопоставим с климатическим, прогноз не несёт
    информации сверх «обычной погоды для этого места и месяца» (E ≈ 0.37).
    """
    if not pool.ens_values or sigma_clim_mm <= 0:
        return None
    values = np.asarray(pool.ens_values, dtype=float)
    weights = np.asarray(pool.ens_weights, dtype=float)
    weights = weights / weights.sum()
    mean = float(np.sum(weights * values))
    sigma = math.sqrt(float(np.sum(weights * (values - mean) ** 2)))
    return _clamp(math.exp(-LAMBDA_E * sigma / sigma_clim_mm))


def flip_flop_index(series: list[float]) -> float:
    """FFI (Ruth et al.) по последовательности прогнозов на одну и ту же дату.

    Монотонный тренд (прогноз последовательно мокреет) даёт FFI = 0 — и это
    правильно: направленное изменение информативно, шумом его считать нельзя.
    Колебания вверх-вниз дают большой FFI.
    """
    n = len(series)
    if n < FFI_MIN_POINTS:
        return 0.0
    path = sum(abs(series[i] - series[i - 1]) for i in range(1, n))
    return max(0.0, (path - (max(series) - min(series))) / (n - 2))


def stability(
    p50_series: list[float], hil_series: list[int], *, lead_days: int
) -> float | None:
    """Компонента S = √(S_cont · (1 − доля смен категории)). None без истории."""
    if len(p50_series) < FFI_MIN_POINTS:
        return None
    k_s = K_S0 + K_S1 * max(0, lead_days)
    s_cont = math.exp(-flip_flop_index(p50_series) / k_s)
    flips = sum(1 for a, b in zip(hil_series, hil_series[1:]) if a != b)
    flip_rate = flips / max(1, len(hil_series) - 1) if len(hil_series) > 1 else 0.0
    return _clamp(math.sqrt(s_cont * (1.0 - flip_rate)))


def _level(score01: float) -> int:
    for i, edge in enumerate(LEVEL_EDGES):
        if score01 >= edge:
            return i
    return len(LEVEL_EDGES)


def compute_reliability(
    pool: DayPool,
    *,
    sigma_clim_mm: float,
    lead_days: int,
    p50_history: list[float] | None = None,
    hil_history: list[int] | None = None,
) -> Reliability:
    """Свёртка §10.6.2: R = 100 · Π Cᵢ^αᵢ по имеющимся компонентам.

    Геометрическая свёртка означает, что провал любой компоненты обрушивает
    итог: прогноз, где модели согласны, но скачут от рана к рану, надёжным не
    считается.
    """
    a = agreement(pool)
    e = ensemble_spread(pool, sigma_clim_mm)
    ensemble_is_proxy = e is None
    if e is None:
        e = _clamp(0.8 * a)     # §10.6: замена E на A с понижением
    s = stability(p50_history or [], hil_history or [], lead_days=lead_days)

    parts = {"agreement": a, "ensemble": e}
    if s is not None:
        parts["stability"] = s
    total_alpha = sum(ALPHA[name] for name in parts)
    score01 = math.prod(value ** (ALPHA[name] / total_alpha)
                        for name, value in parts.items())

    return Reliability(
        day=pool.day,
        score=round(score01 * 100),
        level=_level(score01),
        components=ReliabilityComponents(
            agreement=round(a, 3),
            ensemble=round(e, 3),
            stability=round(s, 3) if s is not None else None,
            ensemble_is_proxy=ensemble_is_proxy,
            n_models=pool.n_models,
            n_members=pool.n_members,
            n_history_runs=len(p50_history or []),
        ),
    )
