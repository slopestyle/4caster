"""Офлайн-тесты слоя бота (без БД и без Telegram)."""

from __future__ import annotations

from fourcaster.modules.locations import CATALOG
from fourcaster.modules.telegram_ui import service
from fourcaster.modules.telegram_ui.keyboards import (
    FORECAST_CB_PREFIX,
    locations_keyboard,
)


def test_keyboard_has_button_per_location():
    kb = locations_keyboard()
    buttons = [b for row in kb.inline_keyboard for b in row]
    assert len(buttons) == len(CATALOG)
    for b in buttons:
        assert b.callback_data.startswith(FORECAST_CB_PREFIX)
        loc_id = b.callback_data[len(FORECAST_CB_PREFIX):]
        assert loc_id in CATALOG


def test_start_reply_mentions_locations_and_has_keyboard():
    r = service.start_reply()
    assert "4CASTER" in r.text
    assert r.keyboard is not None
    for loc in CATALOG.values():
        assert loc.name in r.text


def test_locations_reply_has_keyboard():
    r = service.locations_reply()
    assert r.keyboard is not None
