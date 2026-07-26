"""Бизнес-логика ответов бота, независимая от транспорта (тестируется без Telegram).

Читает готовые карточки из read-модели (FR-TG-7). Здесь нет доменных
вычислений — только выбор текста и клавиатуры (MB-5).
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.engine import Engine

from fourcaster.modules.locations import CATALOG, get_location
from fourcaster.modules.telegram_ui.keyboards import (
    forecast_keyboard,
    locations_keyboard,
    start_keyboard,
)
from fourcaster.platform.read_model import (
    get_card,
    list_subscriptions,
    subscribe,
    unsubscribe,
)


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
    return BotReply(text, start_keyboard())


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


def forecast_reply(
    engine: Engine, location_id: str | None, chat_id: int | None = None
) -> BotReply:
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
    subscribed = bool(chat_id) and location.id in list_subscriptions(engine, chat_id)
    return BotReply(card, forecast_keyboard(location.id, subscribed))


def set_subscription_reply(
    engine: Engine, chat_id: int, location_id: str, *, on: bool
) -> BotReply:
    try:
        location = get_location(location_id)
    except KeyError:
        return BotReply("Такой локации нет.", locations_keyboard())
    if on:
        subscribe(engine, chat_id, location_id)
    else:
        unsubscribe(engine, chat_id, location_id)
    # перерисуем карточку с обновлённым тумблером
    return forecast_reply(engine, location_id, chat_id)


def my_reply(engine: Engine, chat_id: int) -> BotReply:
    ids = list_subscriptions(engine, chat_id)
    if not ids:
        return BotReply(
            "У вас пока нет подписок. Откройте прогноз по локации и нажмите "
            "«🔔 Подписаться на изменения».",
            locations_keyboard(),
        )
    names = "\n".join(
        f"• {CATALOG[i].name}" for i in ids if i in CATALOG
    )
    return BotReply(f"🔔 <b>Ваши подписки:</b>\n{names}", locations_keyboard())
