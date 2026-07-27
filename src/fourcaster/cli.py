"""Композиционный корень среза (упрощённый аналог main.py, §11.3).

Собирает конвейер §10.1 для одной команды и печатает карточки прогноза
по локациям. По умолчанию — все опубликованные точки каталога §7.3
(черновые с Conf=L пропускаем, FR-LOC-5).

Запуск:
    python -m fourcaster.cli                 # живой запрос к Open-Meteo
    python -m fourcaster.cli --offline       # из записанной фикстуры
    python -m fourcaster.cli achishkho -d 5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fourcaster.modules.consensus.calculator import build_pools, consensus_from_pool
from fourcaster.modules.consensus.models import ENSEMBLES, MODELS
from fourcaster.modules.downscaling import build_profile
from fourcaster.modules.forecasting.normalize import normalize, normalize_ensemble
from fourcaster.modules.reliability import compute_reliability, sigma_clim
from fourcaster.modules.ingestion.infrastructure.openmeteo.client import (
    OpenMeteoProvider,
    parse_daily_payload,
    parse_ensemble_payload,
)
from fourcaster.modules.locations import get_location, published
from fourcaster.modules.telegram_ui import render_forecast_card
from fourcaster.shared_kernel.geo import Location

_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
_MODEL_IDS = [m.openmeteo_id for m in MODELS]
_ENSEMBLE_IDS = [e.openmeteo_id for e in ENSEMBLES]
_ENSEMBLE_KEYS = [e.response_key for e in ENSEMBLES]

# Горизонт ансамблей — 10 суток (горизонт GEFS по §8.2 E2). Дальше в пуле
# остаются только детерминированные модели, и это видно в `n_members` дня.
ENSEMBLE_DAYS = 10


# Провайдер один на прогон: в нём живут пауза между запросами и предохранитель
# (задача 1.2). Создавать его на каждую локацию — значит обнулять их 22 раза и
# лишить конвейер защиты ровно тогда, когда она нужна.
_PROVIDER: OpenMeteoProvider | None = None


def provider() -> OpenMeteoProvider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = OpenMeteoProvider()
    return _PROVIDER


def _series_from_fixture(location_id: str):
    payload = json.loads((_FIXTURE_DIR / f"openmeteo_{location_id}.json").read_text("utf-8"))
    return parse_daily_payload(payload, _MODEL_IDS)


def _fixture_locations() -> list[str]:
    """Локации, для которых есть записанная фикстура (для `--offline`)."""
    return sorted(
        p.stem.removeprefix("openmeteo_") for p in _FIXTURE_DIR.glob("openmeteo_*.json")
    )


def _ensembles_from_fixture(location_id: str):
    path = _FIXTURE_DIR / f"ensemble_{location_id}.json"
    if not path.exists():
        return []
    return parse_ensemble_payload(json.loads(path.read_text("utf-8")), _ENSEMBLE_KEYS)


@dataclass(frozen=True, slots=True)
class LocationRun:
    """Результат одного прогона конвейера по локации."""

    location: Location
    consensus: list
    reliability: list
    profiles: list          # DayProfile: изотерма и фаза осадков (§10.3)
    card: str
    computed_at: datetime


def compute_location(
    location_id: str,
    *,
    days: int,
    offline: bool,
    history: dict | None = None,
    with_ensembles: bool = True,
) -> LocationRun:
    """Прогон конвейера для локации: сбор → пул членов → консенсус → надёжность.

    `history` — последние прогоны по датам из read-модели ({date_iso: {p50, hil}}).
    Без неё компонента S (устойчивость во времени) не считается: сравнивать
    не с чем. Так и происходит при `--offline` и в боте.
    """
    location = get_location(location_id)
    if offline:
        raw_series = _series_from_fixture(location_id)
        raw_ensembles = _ensembles_from_fixture(location_id)
    else:
        source = provider()
        raw_series = source.fetch_daily(
            lat=location.lat,
            lon=location.lon,
            elevation_m=location.elevation_m,
            model_ids=_MODEL_IDS,
            forecast_days=days,
        )
        raw_ensembles = []
        if with_ensembles:
            try:
                raw_ensembles = source.fetch_ensembles(
                    lat=location.lat,
                    lon=location.lon,
                    elevation_m=location.elevation_m,
                    ensemble_ids=_ENSEMBLE_IDS,
                    response_keys=_ENSEMBLE_KEYS,
                    forecast_days=min(days, ENSEMBLE_DAYS),
                )
            except Exception as exc:  # noqa: BLE001 — ансамбли не ответили
                # Деградированный режим: прогноз считается по детерминированному
                # ядру, надёжность теряет компоненту E и говорит об этом честно.
                print(f"[{location_id}] ансамбли недоступны: {exc}", file=sys.stderr)
    snapshots = [s for s in (normalize(r) for r in raw_series) if s is not None]
    ensembles = [e for e in (normalize_ensemble(r) for r in raw_ensembles) if e is not None]

    pools = build_pools(snapshots, ensembles, max_days=days)
    consensus = [consensus_from_pool(p) for p in pools]

    # Орографическая коррекция §10.3: температура, нулевая изотерма и фаза
    # осадков в точке. Поправка остаточная — провайдер уже сгладил температуру
    # к переданной высоте, и повторная коррекция удвоила бы её.
    profiles = [
        build_profile(
            temp_max_c=day.temp_max_c,
            temp_min_c=day.temp_min_c,
            provider_elevation_m=pool.provider_elevation_m,
            true_elevation_m=location.elevation_m,
        )
        for pool, day in zip(pools, consensus)
    ]

    history = history or {}
    today = pools[0].day if pools else None
    reliability = []
    for pool in pools:
        past = history.get(pool.day.isoformat(), {})
        reliability.append(compute_reliability(
            pool,
            sigma_clim_mm=sigma_clim(location.cluster, pool.day.month),
            lead_days=(pool.day - today).days if today else 0,
            p50_history=past.get("p50"),
            hil_history=past.get("hil"),
        ))

    computed_at = datetime.utcnow()
    text = render_forecast_card(
        location, consensus, reliability=reliability, profiles=profiles,
        n_models_total=len(MODELS), computed_at=computed_at,
    )
    return LocationRun(location, consensus, reliability, profiles, text, computed_at)


def build_card(location_id: str, *, days: int, offline: bool) -> str:
    return compute_location(location_id, days=days, offline=offline).card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fourcaster", description="4CASTER slice")
    parser.add_argument("locations", nargs="*",
                        help="ID локаций (по умолчанию — весь опубликованный каталог)")
    parser.add_argument("-d", "--days", type=int, default=14, help="Горизонт, суток")
    parser.add_argument("--offline", action="store_true",
                        help="Использовать записанную фикстуру вместо сети")
    parser.add_argument("--save", action="store_true",
                        help="Записать карточки в Postgres (read-модель)")
    parser.add_argument("--no-ensembles", action="store_true",
                        help="Считать только по детерминированным моделям "
                             "(вдвое меньше обращений к провайдеру)")
    args = parser.parse_args(argv)
    # Offline-прогон ограничен точками с записанной фикстурой: каталог §7.3
    # много шире, и без этого команда выдала бы стену «файл не найден».
    location_ids = args.locations or (
        _fixture_locations() if args.offline else list(published())
    )

    # Windows-консоль по умолчанию cp1251 и не печатает emoji — принудительно UTF-8.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    engine = None
    token = None
    if args.save:
        from fourcaster.platform.db import make_engine
        engine = make_engine()
        try:
            from fourcaster.platform.config import telegram_token
            token = telegram_token()
        except Exception:  # noqa: BLE001 — без токена просто не рассылаем
            token = None

    for i, loc_id in enumerate(location_ids):
        history = {}
        if engine is not None:
            from fourcaster.platform.read_model import get_recent_series
            # История нужна ДО записи нового прогона: компонента S сравнивает
            # свежую оценку с тем, что система говорила на этот день раньше.
            history = get_recent_series(engine, loc_id)
        try:
            run = compute_location(
                loc_id, days=args.days, offline=args.offline, history=history,
                with_ensembles=not args.no_ensembles,
            )
        except Exception as exc:  # noqa: BLE001 — CLI-граница
            print(f"[{loc_id}] ошибка: {exc}", file=sys.stderr)
            continue
        location, consensus, card, computed_at = (
            run.location, run.consensus, run.card, run.computed_at
        )
        if i:
            print("\n" + "─" * 44 + "\n")
        print(card)
        if engine is not None:
            from fourcaster.modules.changedetection import detect_changes
            from fourcaster.modules.notification import send_alerts
            from fourcaster.platform.read_model import (
                get_previous_snapshot, insert_history, subscribers_for, upsert_card,
            )
            previous = get_previous_snapshot(engine, location.id)
            upsert_card(engine, location_id=location.id, computed_at=computed_at,
                        days=consensus, rendered_text=card,
                        reliability=run.reliability, profiles=run.profiles)
            insert_history(engine, location_id=location.id, issued_at=computed_at,
                           days=consensus)
            print(f"→ сохранено в БД: {location.id}", file=sys.stderr)

            changes = detect_changes(previous, consensus)
            if changes and token:
                chat_ids = subscribers_for(engine, location.id)
                n = send_alerts(token=token, chat_ids=chat_ids,
                                location_name=location.name, changes=changes)
                print(f"→ алертов отправлено ({location.id}): {n} "
                      f"по {len(changes)} изменениям", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
