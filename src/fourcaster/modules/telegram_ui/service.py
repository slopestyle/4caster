"""Бизнес-логика ответов бота, независимая от транспорта (тестируется без Telegram).

Читает готовые карточки из read-модели (FR-TG-7). Здесь нет доменных
вычислений — только выбор текста и клавиатуры (MB-5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.engine import Engine

from fourcaster.modules.consensus.calculator import DayConsensus
from fourcaster.modules.locations import CATALOG, get_location, published
from fourcaster.modules.telegram_ui.renderers import render_forecast_card
from fourcaster.modules.telegram_ui.keyboards import (
    forecast_keyboard,
    locations_keyboard,
    start_keyboard,
)
from fourcaster.platform.read_model import (
    get_card_full,
    list_subscriptions,
    subscribe,
    unsubscribe,
)


def render_cached_card(engine: Engine, location) -> str | None:
    """Текст карточки из read-модели, но без прошедших дней.

    В кэше лежит `rendered_text` того прогона, который отработал последним;
    если конвейер опоздал с ночным циклом, там всё ещё вчерашний день. Поэтому
    берём структурированную карточку (она уже отфильтрована `upcoming`) и
    форматируем заново — доменных вычислений здесь по-прежнему нет (MB-5).
    """
    data = get_card_full(engine, location.id)
    if data is None:
        return None
    days = [
        DayConsensus(
            day=date.fromisoformat(d["day"]),
            p10=d["p10"], p50=d["p50"], p90=d["p90"],
            pop=d["pop"], n_models=d["n_models"],
        )
        for d in data["days"]
    ]
    return render_forecast_card(
        location, days, computed_at=datetime.fromisoformat(data["computed_at"])
    )


@dataclass(frozen=True, slots=True)
class BotReply:
    text: str
    keyboard: InlineKeyboardMarkup | None = None


def _plural(n: int, one: str, few: str, many: str) -> str:
    a, b = n % 10, n % 100
    if a == 1 and b != 11:
        return one
    if 2 <= a <= 4 and not (10 <= b < 20):
        return few
    return many


def start_reply() -> BotReply:
    pub = published()
    n_clusters = len({loc.cluster for loc in pub.values()})
    text = (
        "🏔 <b>4CASTER</b> — не прогноз погоды, а помощь в решении: идти в горы или нет.\n\n"
        "Показываю консенсус нескольких метеомоделей и честно — насколько ему можно верить.\n\n"
        f"Сейчас в каталоге <b>{len(pub)} {_plural(len(pub), 'точка', 'точки', 'точек')}</b> "
        f"в {n_clusters} горных {_plural(n_clusters, 'районе', 'районах', 'районах')} — "
        "от Красной Поляны до Кодорского ущелья.\n\n"
        "Откройте приложение — все точки, поиск, прогнозы и надёжность внутри."
    )
    return BotReply(text, start_keyboard())


def locations_reply() -> BotReply:
    pub = published()
    text = (
        f"Выберите точку — их {len(pub)}. "
        "В приложении есть поиск и группировка по районам."
    )
    return BotReply(text, locations_keyboard())


HELP_TEXT = (
    "📖 <b>Как читать карточку</b>\n\n"
    "<code>🏔 Ачишхо · 2391 м · Consensus 5/5 моделей</code>\n"
    "Высота точки и сколько независимых метеомоделей сошлось "
    "(IFS, ICON, GFS, GEM, ARPEGE). Меньше моделей → ниже надёжность.\n\n"
    "<code>Сб 26.07  ⛈ Ливень  12 (4–31) мм  ▓▓▓▓░  88%</code>\n"
    "• <b>Иконка + слово</b> — влияние осадков на поход (HIL): Сухо → Ливень.\n"
    "• <b>12 (4–31) мм</b> — дождь за сутки: скорее всего <b>12 мм</b>, "
    "а в скобках — от минимума (4) до максимума (31) по моделям. "
    "Шире скобки — меньше определённости.\n"
    "• <b>▓▓▓▓░ 88%</b> — вероятность осадков.\n\n"
    "<b>📊 Надёжность 1д/3д/7д/14д</b> — насколько можно верить прогнозу на разном "
    "горизонте: 🟢 надёжно · 🟡 ориентировочно · 🟠 низкая · 🔴 не опираться. "
    "Чем дальше день — тем ниже.\n\n"
    "<i>Главное правило продукта: честность о неопределённости. Мы показываем не "
    "«красивую иконку», а насколько ей можно верить.</i>"
)


def help_reply() -> BotReply:
    return BotReply(HELP_TEXT, start_keyboard())


def forecast_reply(
    engine: Engine, location_id: str | None, chat_id: int | None = None
) -> BotReply:
    if not location_id:
        return locations_reply()
    try:
        location = get_location(location_id)
    except KeyError:
        return BotReply("Такой локации нет. Выберите из списка:", locations_keyboard())

    card = render_cached_card(engine, location)
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
