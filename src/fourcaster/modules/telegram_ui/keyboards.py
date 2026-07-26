"""Inline-клавиатуры (PRD §15.1: кнопки, а не команды)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from fourcaster.modules.locations import CATALOG

FORECAST_CB_PREFIX = "fc:"
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


def start_keyboard() -> InlineKeyboardMarkup:
    """Стартовая клавиатура: кнопка Mini App + локации + легенда."""
    rows = [[InlineKeyboardButton(
        text="🗺️ Открыть приложение", web_app=WebAppInfo(url=MINIAPP_URL))]]
    rows += _location_rows()
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
