"""Композиционный корень среза (упрощённый аналог main.py, §11.3).

Собирает конвейер §10.1 для одной команды и печатает карточки прогноза
по локациям. По умолчанию — Ачишхо и Аибга.

Запуск:
    python -m fourcaster.cli                 # живой запрос к Open-Meteo
    python -m fourcaster.cli --offline       # из записанной фикстуры
    python -m fourcaster.cli achishkho -d 5
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from fourcaster.modules.consensus.calculator import compute_consensus
from fourcaster.modules.consensus.models import MODELS
from fourcaster.modules.forecasting.normalize import normalize
from fourcaster.modules.ingestion.infrastructure.openmeteo.client import (
    OpenMeteoProvider,
    parse_daily_payload,
)
from fourcaster.modules.locations import get_location
from fourcaster.modules.telegram_ui import render_forecast_card

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
_MODEL_IDS = [m.openmeteo_id for m in MODELS]


def _series_from_fixture(location_id: str):
    payload = json.loads((_FIXTURE_DIR / f"openmeteo_{location_id}.json").read_text("utf-8"))
    return parse_daily_payload(payload, _MODEL_IDS)


def compute_location(location_id: str, *, days: int, offline: bool):
    """Прогон конвейера для локации. Возвращает (location, консенсус, текст, computed_at)."""
    location = get_location(location_id)
    if offline:
        raw_series = _series_from_fixture(location_id)
    else:
        provider = OpenMeteoProvider()
        raw_series = provider.fetch_daily(
            lat=location.lat,
            lon=location.lon,
            elevation_m=location.elevation_m,
            model_ids=_MODEL_IDS,
            forecast_days=days,
        )
    snapshots = [s for s in (normalize(r) for r in raw_series) if s is not None]
    consensus = compute_consensus(snapshots, max_days=days)
    computed_at = datetime.utcnow()
    text = render_forecast_card(
        location, consensus, n_models_total=len(MODELS), computed_at=computed_at
    )
    return location, consensus, text, computed_at


def build_card(location_id: str, *, days: int, offline: bool) -> str:
    return compute_location(location_id, days=days, offline=offline)[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fourcaster", description="4CASTER slice")
    parser.add_argument("locations", nargs="*", default=["achishkho", "aibga"],
                        help="ID локаций (по умолчанию: achishkho aibga)")
    parser.add_argument("-d", "--days", type=int, default=7, help="Горизонт, суток")
    parser.add_argument("--offline", action="store_true",
                        help="Использовать записанную фикстуру вместо сети")
    parser.add_argument("--save", action="store_true",
                        help="Записать карточки в Postgres (read-модель)")
    args = parser.parse_args(argv)

    # Windows-консоль по умолчанию cp1251 и не печатает emoji — принудительно UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    engine = None
    if args.save:
        from fourcaster.platform.db import make_engine
        from fourcaster.platform.read_model import upsert_card
        engine = make_engine()

    for i, loc_id in enumerate(args.locations):
        try:
            location, consensus, card, computed_at = compute_location(
                loc_id, days=args.days, offline=args.offline
            )
        except Exception as exc:  # noqa: BLE001 — CLI-граница
            print(f"[{loc_id}] ошибка: {exc}", file=sys.stderr)
            continue
        if i:
            print("\n" + "─" * 44 + "\n")
        print(card)
        if engine is not None:
            upsert_card(engine, location_id=location.id, computed_at=computed_at,
                        days=consensus, rendered_text=card)
            print(f"→ сохранено в БД: {location.id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
