"""Сквозной offline-тест среза на записанных фикстурах Open-Meteo."""

from __future__ import annotations

from pathlib import Path

import pytest

from fourcaster.cli import build_card
from fourcaster.modules.locations import CATALOG, CLUSTERS, published
from fourcaster.shared_kernel.geo import REGION_BBOX

_FIXTURES = sorted(
    p.stem.removeprefix("openmeteo_")
    for p in (Path(__file__).parent / "fixtures").glob("openmeteo_*.json")
)


# Прогон конвейера — только по локациям с записанной фикстурой: тесты offline,
# сеть в них не ходит, а каталог §7.3 гораздо шире набора фикстур.
@pytest.mark.parametrize("location_id", _FIXTURES)
def test_build_card_offline(location_id: str):
    card = build_card(location_id, days=7, offline=True)
    loc = CATALOG[location_id]
    assert loc.name in card
    assert f"{loc.elevation_m} м" in card
    assert "Consensus 5/5 моделей" in card
    # 3 строки шапки + 7 дней присутствуют (по разделителю дат)
    assert card.count(".07") + card.count(".08") >= 7


def test_card_reports_reliability_by_horizon_not_by_single_day():
    """§10.6.3: надёжность даётся на период целиком — сутки / 3 / 7 дней."""
    card = build_card(_FIXTURES[0], days=7, offline=True)
    line = next(ln for ln in card.splitlines() if "Надёжность" in ln)
    assert "на период целиком" in line
    for horizon in ("сутки —", "3 дня —", "7 дней —"):
        assert horizon in line
    assert "на ближайший день" not in card


def test_catalog_is_inside_region_and_has_known_clusters():
    lat_min, lat_max, lon_min, lon_max = REGION_BBOX
    for loc in CATALOG.values():
        assert lat_min <= loc.lat <= lat_max, loc.id
        assert lon_min <= loc.lon <= lon_max, loc.id
        assert loc.cluster in CLUSTERS, loc.id
        assert loc.elevation_m > 0, loc.id


def test_draft_locations_are_hidden_from_users():
    """FR-LOC-5: точки с неуверенной координатой (Conf=L) не публикуются."""
    pub = published()
    assert pub, "публиковать нечего — каталог пуст"
    assert all(not loc.is_draft for loc in pub.values())
    assert all(loc.conf != "L" for loc in pub.values())
    drafts = [loc.id for loc in CATALOG.values() if loc.is_draft]
    assert drafts, "в каталоге §7.3 есть точки с Conf=L — они должны быть черновыми"
    assert not (set(drafts) & set(pub))
