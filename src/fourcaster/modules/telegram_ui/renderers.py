"""Рендер карточки прогноза (PRD §15.3).

Формат `p50 (p10–p90)` показывает основной сценарий и разброс одной
строкой — компактно и честно (принцип: числа сопровождаются словами).
В пользовательских текстах эти величины называем только словами: «скорее
всего столько» и «от минимума до максимума по моделям». Перцентилей и
слова «медиана» в интерфейсе быть не должно.

Reliability Score НЕ показывается числом: в срезе калибровки нет, а INV-6
запрещает выдавать некалиброванный скор как число. Вместо него — строка
согласия моделей и явная пометка, что надёжность появится в Фазе 2.
"""

from __future__ import annotations

from datetime import date, datetime

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.hazard.rain import classify_hil
from fourcaster.shared_kernel.geo import Location

_WEEKDAYS_RU = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")


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
    n_models_total: int = 5,
    computed_at: datetime | None = None,
) -> str:
    computed_at = computed_at or datetime.utcnow()
    n_ok = days[0].n_models if days else 0

    lines = [
        f"🏔 {location.name} · {location.elevation_m} м · "
        f"Consensus {n_ok}/{n_models_total} моделей",
        f"🕐 обновлено {computed_at:%H:%M} UTC",
        "",
    ]
    for day in days:
        hil = classify_hil(day.p50)
        label = f"{hil.icon} {hil.label}".ljust(18)
        amount = _fmt_amount(day).rjust(16)
        bar = _prob_bar(day.pop)
        pct = f"{round(day.pop * 100):>3d}%"
        lines.append(f"{_fmt_day(day.day)}  {label}{amount}  {bar}  {pct}")

    lines.append("")
    lines.append(
        f"📊 Надёжность: расчёт в Фазе 2 (калибровка, §10.6). "
        f"Сейчас — согласие {n_ok}/{n_models_total} моделей."
    )
    lines.append("ℹ️ Срез конвейера: downscaling и HIL — упрощённые.")
    return "\n".join(lines)
