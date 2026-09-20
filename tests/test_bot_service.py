"""Офлайн-тесты слоя бота (без БД и без Telegram)."""

from __future__ import annotations

from fourcaster.modules.locations import CATALOG, published
from fourcaster.modules.telegram_ui import service
from fourcaster.modules.telegram_ui.keyboards import (
    FORECAST_CB_PREFIX,
    HELP_CB,
    locations_keyboard,
)


def test_keyboard_has_button_per_published_location_and_help():
    kb = locations_keyboard()
    buttons = [b for row in kb.inline_keyboard for b in row]
    fc_buttons = [b for b in buttons if (b.callback_data or "").startswith(FORECAST_CB_PREFIX)]
    ids = {b.callback_data[len(FORECAST_CB_PREFIX):] for b in fc_buttons}
    # кнопки ровно по опубликованным точкам: черновые (Conf=L) наружу не выходят
    assert ids == set(published())
    assert all(not CATALOG[i].is_draft for i in ids)
    # кнопка легенды присутствует
    assert any(b.callback_data == HELP_CB for b in buttons)


def test_help_reply_explains_parameters():
    r = service.help_reply()
    assert r.keyboard is not None
    for token in ("Consensus", "HIL", "мм", "Надёжность"):
        assert token in r.text


def test_start_reply_counts_published_locations_and_has_keyboard():
    # перечислять два десятка названий в приветствии бессмысленно — там счётчик
    r = service.start_reply()
    assert "4CASTER" in r.text
    assert r.keyboard is not None
    assert str(len(published())) in r.text


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


# ── горизонты надёжности в проекции карточки (§10.6.3) ─────────────────────

def _day_json(iso: str, score: int) -> dict:
    return {
        "day": iso, "p50": 1.0, "n_models": 5,
        "reliability": {"score": score, "level": 1, "agreement": 0.7,
                        "ensemble": 0.6, "stability": None, "history": 0.8,
                        "ensemble_is_proxy": False, "n_members": 60,
                        "n_history_runs": 0},
    }


def test_stored_horizons_are_served_as_is_for_a_fresh_card():
    from fourcaster.platform.read_model import horizons_for

    days = [_day_json("2026-07-26", 70), _day_json("2026-07-27", 60)]
    stored = [{"days": 2, "start": "2026-07-26", "end": "2026-07-27", "level": 1}]
    assert horizons_for(stored, days) is stored


def test_horizons_are_rebuilt_when_the_card_lost_its_first_day():
    """Горизонт считается от первых суток карточки: после отсечения вчерашнего
    дня «ближайшие 3 дня» из записи означали бы вчера-сегодня-завтра."""
    from fourcaster.platform.read_model import horizons_for

    days = [_day_json("2026-07-27", 60), _day_json("2026-07-28", 50)]
    stored = [{"days": 3, "start": "2026-07-26", "end": "2026-07-28", "level": 1}]
    rebuilt = horizons_for(stored, days)
    assert [h["days"] for h in rebuilt] == [1, 2]
    assert all(h["start"] == "2026-07-27" for h in rebuilt)


def test_horizons_are_built_for_cards_written_before_the_column_existed():
    from fourcaster.platform.read_model import horizons_for

    days = [_day_json("2026-07-27", 60), _day_json("2026-07-28", 50)]
    assert [h["days"] for h in horizons_for(None, days)] == [1, 2]
