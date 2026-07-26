"""Inline-клавиатуры (PRD §15.1: кнопки, а не команды)."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from fourcaster.modules.locations import CATALOG

FORECAST_CB_PREFIX = "fc:"


def locations_keyboard() -> InlineKeyboardMarkup:
    """Список локаций каталога как кнопки прогноза."""
    rows = [
        [InlineKeyboardButton(text=loc.name, callback_data=f"{FORECAST_CB_PREFIX}{loc.id}")]
        for loc in CATALOG.values()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
