"""Офлайн-тесты слоя бота (без БД и без Telegram)."""

from __future__ import annotations

from fourcaster.modules.locations import CATALOG
from fourcaster.modules.telegram_ui import service
from fourcaster.modules.telegram_ui.keyboards import (
    FORECAST_CB_PREFIX,
    HELP_CB,
    locations_keyboard,
)


def test_keyboard_has_button_per_location_and_help():
    kb = locations_keyboard()
    buttons = [b for row in kb.inline_keyboard for b in row]
    fc_buttons = [b for b in buttons if b.callback_data.startswith(FORECAST_CB_PREFIX)]
    assert len(fc_buttons) == len(CATALOG)
    for b in fc_buttons:
        loc_id = b.callback_data[len(FORECAST_CB_PREFIX):]
        assert loc_id in CATALOG
    # кнопка легенды присутствует
    assert any(b.callback_data == HELP_CB for b in buttons)


def test_help_reply_explains_parameters():
    r = service.help_reply()
    assert r.keyboard is not None
    for token in ("Consensus", "HIL", "мм", "Надёжность"):
        assert token in r.text


def test_start_reply_mentions_locations_and_has_keyboard():
    r = service.start_reply()
    assert "4CASTER" in r.text
    assert r.keyboard is not None
    for loc in CATALOG.values():
        assert loc.name in r.text


def test_locations_reply_has_keyboard():
    r = service.locations_reply()
    assert r.keyboard is not None


# ── read-модель: прошедшие дни не показываем ────────────────────────────────

def test_upcoming_drops_past_days():
    from datetime import date

    from fourcaster.platform.read_model import upcoming

    days = [{"day": "2026-07-25", "p50": 1.0}, {"day": "2026-07-26", "p50": 2.0},
            {"day": "2026-07-27", "p50": 3.0}]
    left = upcoming(days, today=date(2026, 7, 26))
    assert [d["day"] for d in left] == ["2026-07-26", "2026-07-27"]


def test_upcoming_keeps_everything_when_card_is_fresh():
    from datetime import date

    from fourcaster.platform.read_model import upcoming

    days = [{"day": "2026-07-26"}, {"day": "2026-07-27"}]
    assert upcoming(days, today=date(2026, 7, 26)) == days


def test_upcoming_on_fully_stale_card_is_empty():
    from datetime import date

    from fourcaster.platform.read_model import upcoming

    assert upcoming([{"day": "2026-07-01"}], today=date(2026, 7, 26)) == []
