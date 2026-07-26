"""Сквозной offline-тест среза на записанных фикстурах Open-Meteo."""

from __future__ import annotations

import pytest

from fourcaster.cli import build_card
from fourcaster.modules.locations import CATALOG


@pytest.mark.parametrize("location_id", list(CATALOG))
def test_build_card_offline(location_id: str):
    card = build_card(location_id, days=7, offline=True)
    loc = CATALOG[location_id]
    assert loc.name in card
    assert f"{loc.elevation_m} м" in card
    assert "Consensus 5/5 моделей" in card
    # 3 строки шапки + 7 дней присутствуют (по разделителю дат)
    assert card.count(".07") + card.count(".08") >= 7
