"""Бизнес-логика ответов бота, независимая от транспорта (тестируется без Telegram).

Читает готовые карточки из read-модели (FR-TG-7). Здесь нет доменных
вычислений — только выбор текста и клавиатуры (MB-5).
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.engine import Engine

from fourcaster.modules.locations import CATALOG, get_location
from fourcaster.modules.telegram_ui.keyboards import locations_keyboard
from fourcaster.platform.read_model import get_card


@dataclass(frozen=True, slots=True)
class BotReply:
    text: str
    keyboard: InlineKeyboardMarkup | None = None


def start_reply() -> BotReply:
    names = " · ".join(loc.name for loc in CATALOG.values())
    text = (
        "🏔 <b>4CASTER</b> — не прогноз погоды, а помощь в решении: идти в горы или нет.\n\n"
        "Показываю консенсус нескольких метеомоделей и честно — насколько ему можно верить.\n\n"
        f"Доступные точки: {names}\n\n"
        "Выберите локацию или отправьте /forecast."
    )
    return BotReply(text, locations_keyboard())


def locations_reply() -> BotReply:
    return BotReply("Выберите локацию:", locations_keyboard())


HELP_TEXT = (
    "📖 <b>Как читать карточку</b>\n\n"
    "<code>🏔 Ачишхо · 2391 м · Consensus 5/5 моделей</code>\n"
    "Высота точки и сколько независимых метеомоделей сошлось "
    "(IFS, ICON, GFS, GEM, ARPEGE). Меньше моделей → ниже надёжность.\n\n"
    "<code>Сб 26.07  ⛈ Ливень  12 (4–31) мм  ▓▓▓▓░  88%</code>\n"
    "• <b>Иконка + слово</b> — влияние осадков на поход (HIL): Сухо → Ливень.\n"
    "• <b>12 (4–31) мм</b> — осадки за сутки: <b>12</b> основной сценарий, "
    "в скобках разброс моделей от «оптимистично» (4) до «пессимистично» (31). "
    "Шире разброс — выше неопределённость.\n"
    "• <b>▓▓▓▓░ 88%</b> — вероятность осадков.\n\n"
    "<b>📊 Надёжность 1д/3д/7д/14д</b> — насколько можно верить прогнозу на разном "
    "горизонте: 🟢 надёжно · 🟡 ориентировочно · 🟠 низкая · 🔴 не опираться. "
    "Чем дальше день — тем ниже.\n\n"
    "<i>Главное правило продукта: честность о неопределённости. Мы показываем не "
    "«красивую иконку», а насколько ей можно верить.</i>"
)


def help_reply() -> BotReply:
    return BotReply(HELP_TEXT, locations_keyboard())


def forecast_reply(engine: Engine, location_id: str | None) -> BotReply:
    if not location_id:
        return locations_reply()
    try:
        location = get_location(location_id)
    except KeyError:
        return BotReply("Такой локации нет. Выберите из списка:", locations_keyboard())

    card = get_card(engine, location.id)
    if card is None:
        return BotReply(
            f"По «{location.name}» пока нет рассчитанного прогноза — "
            f"конвейер ещё не отработал. Попробуйте позже.",
            locations_keyboard(),
        )
    return BotReply(card, locations_keyboard())
