"""Inline-клавиатуры (PRD §15.1: кнопки, а не команды)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from fourcaster.modules.locations import CATALOG

FORECAST_CB_PREFIX = "fc:"
HELP_CB = "help"


def locations_keyboard() -> InlineKeyboardMarkup:
    """Список локаций каталога + кнопка легенды."""
    rows = [
        [InlineKeyboardButton(text=loc.name, callback_data=f"{FORECAST_CB_PREFIX}{loc.id}")]
        for loc in CATALOG.values()
    ]
    rows.append([InlineKeyboardButton(text="❓ Что значат числа?", callback_data=HELP_CB)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
