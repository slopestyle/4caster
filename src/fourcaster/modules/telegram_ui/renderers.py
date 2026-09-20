"""Рендер карточки прогноза (PRD §15.3).

Формат `p50 (p10–p90)` показывает основной сценарий и разброс одной
строкой — компактно и честно (принцип: числа сопровождаются словами).
В пользовательских текстах эти величины называем только словами: «скорее
всего столько» и «от минимума до максимума по моделям». Перцентилей и
слова «медиана» в интерфейсе быть не должно.

Reliability Score НЕ показывается числом: калибровки пока нет, а INV-6
запрещает выдавать некалиброванный скор как число. Показывается качественная
шкала (§10.6.4) — слово и из чего оно сложилось.

Надёжность даётся **на горизонт, а не на отдельные сутки** (§10.6.3): вопрос
пользователя — «на сколько дней вперёд этому прогнозу можно верить», и ответ
на него один на весь период, а не свой у каждого четверга.
"""

from __future__ import annotations

from datetime import date, datetime

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.downscaling import DayProfile
from fourcaster.modules.hazard.rain import classify_hil
from fourcaster.modules.reliability import HorizonReliability
from fourcaster.shared_kernel.geo import Location
from fourcaster.shared_kernel.variables import PrecipPhase

_WEEKDAYS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
# Фазу показываем, только когда она не «дождь»: подпись «дождём» у строки про
# дождь — шум, а вот мокрый снег на 2800 м в июле меняет решение.
_PHASE_RU = {PrecipPhase.SNOW: "❄ снег", PrecipPhase.SLEET: "🌨 мокрый снег"}


def _fmt_day(d: date) -> str:
    return f"{_WEEKDAYS_RU[d.weekday()]} {d.day:02d}.{d.month:02d}"


def _prob_bar(pop: float, cells: int = 5) -> str:
    filled = round(pop * cells)
    return "▓" * filled + "░" * (cells - filled)


def _fmt_amount(day: DayConsensus) -> str:
    return f"{day.p50:g} ({day.p10:g}–{day.p90:g}) мм"


def render_forecast_card(
    location: Location,
    days: list[DayConsensus],
    *,
    horizons: list[HorizonReliability] | None = None,
    profiles: list[DayProfile] | None = None,
    n_models_total: int = 5,
    computed_at: datetime | None = None,
) -> str:
    computed_at = computed_at or datetime.utcnow()
    n_ok = days[0].n_models if days else 0
    n_members = days[0].n_members if days else 0

    members_note = (
        f" + {n_members - n_ok} членов ансамблей" if n_members > n_ok else ""
    )
    lines = [
        f"🏔 {location.name} · {location.elevation_m} м · "
        f"Consensus {n_ok}/{n_models_total} моделей{members_note}",
        f"🕐 обновлено {computed_at:%H:%M} UTC",
        "",
    ]
    by_index = list(profiles or ())
    for i, day in enumerate(days):
        hil = classify_hil(day.p50)
        label = f"{hil.icon} {hil.label}".ljust(18)
        amount = _fmt_amount(day).rjust(16)
        bar = _prob_bar(day.pop)
        pct = f"{round(day.pop * 100):>3d}%"
        profile = by_index[i] if i < len(by_index) else None
        phase = _PHASE_RU.get(profile.phase) if profile else None
        tail = f"  {phase}" if phase and day.p50 > 0 else ""
        lines.append(f"{_fmt_day(day.day)}  {label}{amount}  {bar}  {pct}{tail}")

    lines.append("")
    lines.extend(_reliability_lines(horizons, days, n_ok, n_models_total))
    # Что именно упрощено, стоит называть точно: температура и фаза осадков уже
    # корректируются (§10.3), а вот усиление осадков рельефом обучается по факту
    # в Фазе 3, и HIL пока эвристика по суточной сумме.
    lines.append("ℹ️ Срез конвейера: HIL — упрощённый, усиление осадков рельефом ещё не учтено.")
    return "\n".join(lines)


def _days_word(n: int) -> str:
    """«1 сутки» звучит канцелярски, поэтому однодневный горизонт — «сутки»."""
    if n == 1:
        return "сутки"
    a, b = n % 10, n % 100
    if 2 <= a <= 4 and not (10 <= b < 20):
        return f"{n} дня"
    return f"{n} дней"


def _reliability_lines(
    horizons: list[HorizonReliability] | None,
    days: list[DayConsensus],
    n_ok: int,
    n_models_total: int,
) -> list[str]:
    """Надёжность по горизонтам — словом, а не числом (INV-6, §10.6.3).

    Оценка даётся на период целиком: «на ближайшие сутки — надёжно, на неделю —
    низкая». Отдельные сутки внутри периода своей надёжности наружу не имеют:
    прогноз на четверг из прогона, где вся неделя шатается, надёжным не бывает.
    """
    if not horizons:
        return [f"📊 Надёжность: не рассчитана — "
                f"согласие {n_ok}/{n_models_total} моделей."]

    words = " · ".join(f"{_days_word(h.days)} — {h.label}" for h in horizons)
    lines = [f"📊 Надёжность прогноза на период целиком: {words}."]

    # Подробности — по горизонту в 3 суток (типичный выход с ночёвкой); если
    # прогноз короче, берём самый длинный из имеющихся.
    detail = next((h for h in horizons if h.days >= 3), horizons[-1])
    parts = [f"согласие моделей {round(detail.components.agreement * 100)}%"]
    if detail.components.ensemble_is_proxy:
        parts.append("ансамбли не на все дни")
    else:
        parts.append(f"разброс ансамблей {round(detail.components.ensemble * 100)}%")
    if detail.components.stability is not None:
        parts.append(f"устойчивость {round(detail.components.stability * 100)}%")
    else:
        parts.append("истории для устойчивости пока мало")
    # H — насколько вообще оправдываются прогнозы на таком сроке: согласие
    # моделей на дальних днях само по себе ещё не означает попадание в факт.
    parts.append(f"оправдываемость срока {round(detail.components.history * 100)}%")

    total = sum(d.p50 for d in days[:detail.days])
    lines.append(f"   за {_days_word(detail.days)} суммарно ≈{total:g} мм · "
                 + ", ".join(parts) + ".")
    return lines
