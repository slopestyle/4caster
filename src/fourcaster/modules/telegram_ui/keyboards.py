"""Inline-клавиатуры (PRD §15.1: кнопки, а не команды)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from fourcaster.modules.locations import CATALOG

FORECAST_CB_PREFIX = "fc:"
SUB_CB_PREFIX = "sub:"
UNSUB_CB_PREFIX = "unsub:"
HELP_CB = "help"
MINIAPP_URL = "https://4caster-inky.vercel.app/app"


def _location_rows() -> list[list[InlineKeyboardButton]]:
    return [
        [InlineKeyboardButton(text=loc.name, callback_data=f"{FORECAST_CB_PREFIX}{loc.id}")]
        for loc in CATALOG.values()
    ]


def locations_keyboard() -> InlineKeyboardMarkup:
    """Список локаций каталога + кнопка легенды."""
    rows = _location_rows()
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def forecast_keyboard(location_id: str, subscribed: bool) -> InlineKeyboardMarkup:
    """Карточка прогноза: тумблер подписки + другие локации + легенда."""
    if subscribed:
        sub_btn = InlineKeyboardButton(
            text="🔕 Отписаться", callback_data=f"{UNSUB_CB_PREFIX}{location_id}")
    else:
        sub_btn = InlineKeyboardButton(
            text="🔔 Подписаться на изменения", callback_data=f"{SUB_CB_PREFIX}{location_id}")
    rows = [[sub_btn]]
    rows += _location_rows()
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая клавиатура: кнопка Mini App + локации + легенда."""
    rows = [[InlineKeyboardButton(
        text="🗺️ Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL))]]
    rows += _location_rows()
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
