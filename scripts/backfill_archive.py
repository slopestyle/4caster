"""Backfill архива осадков и климатология σ_clim (PRD, задача 1.7).

Зачем это нужно раньше всего остального в Фазе 3: без «что было на самом деле»
нельзя ни обучить веса моделей (3.4), ни откалибровать надёжность (3.5), ни
посчитать порог значимости `NoiseFloor` (4.2). Задача 1.7 — прямая зависимость
всех трёх, поэтому она и стоит в критическом пути §19.3.

Источник — реанализ ERA5 через архивный API Open-Meteo, §8.4. Это не измерения
станции: для суточных сумм осадков в горах реанализ занижает пики конвекции, но
это единственный источник со сплошным покрытием по всем точкам каталога.
Дополнение станциями и IMERG — задача 3.1.

Берём `era5_seamless` (ERA5-Land 9 км там, где он есть, с добором из ERA5),
а не чистый `era5_land`: последний на диапазонах длиннее нескольких суток
отдаёт `null` на весь период — молча, со статусом 200. Именно поэтому первая
выгрузка записала ноль строк, и именно поэтому ниже стоит проверка на пустой
ответ: тихий `null` от источника не должен выглядеть как «данных нет».

Что делает скрипт:

    python scripts/backfill_archive.py                # выгрузить в БД
    python scripts/backfill_archive.py --report       # только отчёт о полноте
    python scripts/backfill_archive.py --climatology  # пересобрать σ_clim из БД

Выгрузка идемпотентна (ON CONFLICT DO NOTHING по `(локация, дата)`), так что
повторный запуск дозаливает пропуски и ничего не портит.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from fourcaster.modules.locations import CATALOG
from fourcaster.platform.db import make_engine
from fourcaster.platform.models import ArchiveDaily

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "4CASTER/0.0.1 (contact@example.org)"
SOURCE = "era5_seamless"

# Реанализ публикуется с задержкой — просить свежее бессмысленно.
ARCHIVE_LAG_DAYS = 7
DEFAULT_START = date(2024, 1, 1)

_SIGMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "fourcaster" / "modules" / "reliability" / "data" / "sigma_clim.json"
)
# Меньше этого числа суточных значений в ячейке «кластер × месяц» разброс
# считать нечестно — оценка σ по десятку точек сама себе шум.
MIN_SAMPLE = 60


def fetch_archive(lat: float, lon: float, start: date, end: date) -> list[tuple[date, float]]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "models": SOURCE,
        "timezone": "UTC",
    }
    for attempt in range(6):
        try:
            with httpx.Client(timeout=120.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(ARCHIVE_URL, params=params)
        except httpx.TransportError:
            time.sleep(10 * (attempt + 1))
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(60 * (attempt + 1))
            continue
        resp.raise_for_status()
        daily = resp.json().get("daily", {})
        days, values = daily.get("time", []), daily.get("precipitation_sum", [])
        rows = [
            (date.fromisoformat(d), float(v))
            for d, v in zip(days, values)
            if v is not None
        ]
        if days and not rows:
            # Источник ответил 200 и молча отдал null на весь период — это не
            # «данных нет», а неподходящий запрос; глотать такое нельзя.
            raise RuntimeError(
                f"источник вернул {len(days)} суток и ни одного значения "
                f"({start} … {end}) — проверьте модель и диапазон"
            )
        return rows
    raise RuntimeError("архивный API Open-Meteo не отвечает или держит лимит")


def store(engine, location_id: str, rows: list[tuple[date, float]]) -> int:
    if not rows:
        return 0
    payload = [
        {"location_id": location_id, "valid_date": d, "precip_mm": v, "source": SOURCE}
        for d, v in rows
    ]
    stmt = insert(ArchiveDaily).values(payload).on_conflict_do_nothing(
        index_elements=[ArchiveDaily.location_id, ArchiveDaily.valid_date]
    )
    with engine.begin() as conn:
        return conn.execute(stmt).rowcount or 0


def report(engine, start: date, end: date) -> None:
    """Отчёт о полноте — часть DoD задачи 1.7."""
    expected = (end - start).days + 1
    stmt = (
        select(
            ArchiveDaily.location_id,
            func.count(ArchiveDaily.valid_date),
            func.min(ArchiveDaily.valid_date),
            func.max(ArchiveDaily.valid_date),
        )
        .group_by(ArchiveDaily.location_id)
        .order_by(ArchiveDaily.location_id)
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    print(f"\nПолнота архива (ожидается {expected} сут. на точку):")
    print(f"{'локация':<22}{'суток':>7}{'полнота':>9}  период")
    print("─" * 66)
    for location_id, count, first, last in rows:
        print(f"{location_id:<22}{count:>7}{count / expected:>8.0%}  {first} … {last}")
    print("─" * 66)
    print(f"точек в архиве: {len(rows)} из {len(CATALOG)}")


def build_climatology(engine) -> dict[str, float]:
    """σ_clim по «кластер × месяц» — нормировка компоненты E надёжности (§10.6).

    Берётся стандартное отклонение суточных сумм: именно с ним сравнивается
    разброс ансамбля, чтобы отличить «модели разошлись» от «здесь в это время
    года всегда так».
    """
    stmt = select(ArchiveDaily.location_id, ArchiveDaily.valid_date, ArchiveDaily.precip_mm)
    with engine.connect() as conn:
        rows = conn.execute(stmt).all()

    buckets: dict[str, list[float]] = defaultdict(list)
    for location_id, valid_date, precip in rows:
        location = CATALOG.get(location_id)
        if location is None:
            continue        # точка исчезла из каталога — в климатологию не берём
        buckets[f"{location.cluster}:{valid_date.month}"].append(float(precip))

    table = {
        key: round(statistics.pstdev(values), 2)
        for key, values in buckets.items()
        if len(values) >= MIN_SAMPLE and statistics.pstdev(values) > 0
    }
    _SIGMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SIGMA_PATH.write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True), "utf-8")
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill архива (задача 1.7)")
    parser.add_argument("locations", nargs="*", help="ID локаций (по умолчанию — весь каталог)")
    parser.add_argument("--start", type=date.fromisoformat, default=DEFAULT_START)
    parser.add_argument("--end", type=date.fromisoformat,
                        default=date.today() - timedelta(days=ARCHIVE_LAG_DAYS))
    parser.add_argument("--report", action="store_true", help="только отчёт о полноте")
    parser.add_argument("--climatology", action="store_true",
                        help="пересобрать σ_clim из того, что уже в БД")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    engine = make_engine()

    if not args.report and not args.climatology:
        # Черновые точки выгружаем тоже: климатология считается по кластеру, и
        # лишние точки внутри кластера её только уточняют.
        ids = args.locations or list(CATALOG)
        print(f"Выгрузка ERA5-Land: {len(ids)} точек, {args.start} … {args.end}")
        for i, location_id in enumerate(ids, 1):
            location = CATALOG[location_id]
            try:
                rows = fetch_archive(location.lat, location.lon, args.start, args.end)
            except Exception as exc:  # noqa: BLE001 — граница скрипта
                print(f"[{location_id}] ошибка: {exc}", file=sys.stderr)
                continue
            written = store(engine, location_id, rows)
            print(f"[{i}/{len(ids)}] {location_id:<22} получено {len(rows):>5}, "
                  f"записано {written:>5}")

    if not args.climatology:
        report(engine, args.start, args.end)

    if args.climatology or not args.report:
        table = build_climatology(engine)
        print(f"\nσ_clim: ячеек «кластер × месяц» {len(table)} → {_SIGMA_PATH.name}")
        for key in sorted(table)[:8]:
            print(f"  {key:<16}{table[key]:>7} мм")
        if len(table) > 8:
            print(f"  … ещё {len(table) - 8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
