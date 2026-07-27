"""Inline-клавиатуры (PRD §15.1: кнопки, а не команды)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from fourcaster.modules.locations import published

LIST_CB = "locs"
FORECAST_CB_PREFIX = "fc:"
SUB_CB_PREFIX = "sub:"
UNSUB_CB_PREFIX = "unsub:"
HELP_CB = "help"
MINIAPP_URL = "https://4caster-inky.vercel.app/app"


def _location_rows(cols: int = 2) -> list[list[InlineKeyboardButton]]:
    """Кнопки локаций в несколько колонок: точек в каталоге больше двух десятков."""
    btns = [
        InlineKeyboardButton(text=loc.name, callback_data=f"{FORECAST_CB_PREFIX}{loc.id}")
        for loc in published().values()
    ]
    return [btns[i:i + cols] for i in range(0, len(btns), cols)]


def locations_keyboard() -> InlineKeyboardMarkup:
    """Список локаций каталога (без черновых, FR-LOC-5) + легенда и приложение."""
    rows = _location_rows()
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    rows.append([InlineKeyboardButton(
        text="🗺️ Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def forecast_keyboard(location_id: str, subscribed: bool) -> InlineKeyboardMarkup:
    """Карточка прогноза: тумблер подписки, возврат к списку, приложение, легенда.

    Полный список локаций под каждой карточкой больше не разворачиваем — с
    двумя десятками точек это простыня; переход к списку одной кнопкой.
    """
    if subscribed:
        sub_btn = InlineKeyboardButton(
            text="🔕 Отписаться", callback_data=f"{UNSUB_CB_PREFIX}{location_id}")
    else:
        sub_btn = InlineKeyboardButton(
            text="🔔 Подписаться на изменения", callback_data=f"{SUB_CB_PREFIX}{location_id}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [sub_btn],
        [InlineKeyboardButton(text="📍 Все точки", callback_data=LIST_CB),
         InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)],
        [InlineKeyboardButton(
            text="🗺️ Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL))],
    ])


def start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая клавиатура: только кнопка приложения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗺️ Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL))],
    ])
