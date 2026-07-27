"""Сверка каталога локаций с DEM (PRD, задача 0.3; FR-LOC-1, FR-LOC-2).

Высоты и координаты в §7.3 помечены `[ASSUMPTION]` — взяты из описаний, а не
измерены. Скрипт спрашивает у Open-Meteo Elevation API высоту рельефа в точке
(Copernicus DEM GLO-90 — тот же рельеф, по которому провайдер выбирает ячейку)
и сравнивает с каталогом. По FR-LOC-1 расхождение > 150 м требует разбора.

Как читать расхождение:

- **DEM ниже каталога** — для вершины норма: ячейка 90 м срезает пик. Проверено
  на эталонах: Монблан −16 м, Казбек −142 м, Эльбрус −217 м. Значит для вершин
  честный допуск ~250 м, а разница в 500–1200 м — это уже промах координаты.
- **DEM выше каталога** — координата ушла на склон выше точки; для дна ущелья
  или базы курорта это прямой признак промаха.

Режим `--snap` предлагает исправленную координату: сканирует DEM вокруг
исходной точки и выбирает ту, что соответствует **типу ориентира** (`KIND`):
вершина — локальный максимум рельефа, всё остальное — ячейка с высотой,
ближайшей к каталожной. Тип — единственное, что здесь задано вручную: DEM
знает высоту, но не знает, что именно мы хотели этой точкой назвать.

Скрипт ничего не меняет сам: `catalog.py` правит человек, сверяясь с выводом.

Лимиты Open-Meteo считаются по точкам, а не по запросам (81 точка = 81 вызов
при лимите 600/мин), поэтому сетка мелкая, а запросы разнесены во времени.

Запуск:
    python scripts/verify_locations.py            # сверка всех точек
    python scripts/verify_locations.py --drafts   # только черновые (Conf=L)
    python scripts/verify_locations.py --snap     # + поиск исправленных координат
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import httpx

from fourcaster.modules.locations import CATALOG

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
USER_AGENT = "4CASTER/0.0.1 (contact@example.org)"

# Допуск сходимости: FR-LOC-1 требует разбора при расхождении > 150 м.
# Для вершин допуск шире — 90-метровая ячейка систематически срезает пик.
TOL = 150
TOL_PEAK = 250
CALLS_PER_MIN = 500          # свой потолок ниже документированных 600/мин

# Тип ориентира — что искать в рельефе вокруг точки:
#   peak — вершина или гребень: локальный максимум DEM;
#   at   — точка на известной высоте: перевал, плато, лагерь, озеро, ущелье,
#          посёлок, база. Ищем ячейку с высотой, ближайшей к каталожной, —
#          «самое дно в радиусе» уводило бы посёлок в чужое русло.
# `peak` — только именованные вершины с опубликованной высотой: там совпадение
# локального максимума с высотой из каталога — сильное подтверждение. «Роза Пик»
# и «Альпика-Сервис (верх)» — верхние станции подъёмников, а не вершины: поиск
# максимума уводил их на гребень Аибги, на 130–190 м выше станции.
KIND: dict[str, str] = {
    "achishkho": "peak", "aibga": "peak", "dzitaku": "peak",
    "tsakhvoa": "peak", "fisht": "peak", "oshten": "peak",
    "psheha-su": "peak", "arabika-massif": "peak", "mamdzyshkha": "peak",
}

_spent: list[float] = []     # отметки времени израсходованных вызовов

# Рельеф не меняется, а квота Open-Meteo считается по точкам и заканчивается
# быстро (часовой лимит выбирается одним полным прогоном --snap). Поэтому все
# ответы кладём на диск: повторный прогон не стоит ни одного вызова.
_CACHE_PATH = Path(__file__).with_name(".dem_cache.json")
_cache: dict[str, float] = (
    json.loads(_CACHE_PATH.read_text("utf-8")) if _CACHE_PATH.exists() else {}
)


def _cache_key(lat: float, lon: float) -> str:
    return f"{lat:.5f},{lon:.5f}"


def _throttle(n_points: int) -> None:
    """Простой скользящий лимитер: не больше CALLS_PER_MIN точек в минуту."""
    now = time.monotonic()
    _spent[:] = [t for t in _spent if now - t < 60.0]
    if len(_spent) + n_points > CALLS_PER_MIN and _spent:
        time.sleep(max(0.0, 60.0 - (now - _spent[0])) + 0.5)
        _throttle(n_points)
        return
    _spent.extend([now] * n_points)


def fetch_dem(coords: list[tuple[float, float]]) -> list[float]:
    """Высоты рельефа по списку координат (до 100 точек за запрос), с кэшем."""
    missing = [c for c in coords if _cache_key(*c) not in _cache]
    for i in range(0, len(missing), 100):        # API принимает до 100 точек
        chunk = missing[i:i + 100]
        _cache.update(zip((_cache_key(*c) for c in chunk), _fetch_dem_live(chunk)))
        _CACHE_PATH.write_text(json.dumps(_cache), "utf-8")
    return [_cache[_cache_key(*c)] for c in coords]


def _fetch_dem_live(coords: list[tuple[float, float]]) -> list[float]:
    params = {
        "latitude": ",".join(str(lat) for lat, _ in coords),
        "longitude": ",".join(str(lon) for _, lon in coords),
    }
    for attempt in range(8):
        _throttle(len(coords))
        try:
            with httpx.Client(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(ELEVATION_URL, params=params)
        except httpx.TransportError:     # обрыв/таймаут — ретрай с бэкоффом
            time.sleep(10 * (attempt + 1))
            continue
        if resp.status_code == 429:
            # Лимит бывает и часовым (5000 вызовов) — ждём соответственно долго:
            # прогон всё равно один раз в жизни точки, спешить некуда.
            time.sleep(90 * (attempt + 1))
            continue
        if resp.status_code >= 500:      # временная ошибка сервиса
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        return [float(v) for v in resp.json()["elevation"]]
    raise RuntimeError("Open-Meteo Elevation API: не отвечает или держит лимит")


def tolerance(location_id: str) -> int:
    return TOL_PEAK if KIND.get(location_id) == "peak" else TOL


def verdict(location_id: str, diff: int) -> str:
    """diff = DEM − каталог, метры."""
    tol = tolerance(location_id)
    if abs(diff) <= tol:
        return "сходится"
    if abs(diff) <= tol * 2:
        return "расхождение"
    return "КООРДИНАТА ПОД ВОПРОСОМ"


def _grid(lat: float, lon: float, radius_m: float, n: int) -> list[tuple[float, float]]:
    """Квадратная сетка n×n точек вокруг (lat, lon) с полушириной radius_m."""
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    step = 2.0 / (n - 1)
    return [
        (round(lat - dlat + dlat * step * i, 5), round(lon - dlon + dlon * step * j, 5))
        for i in range(n)
        for j in range(n)
    ]


def _dist_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Расстояние между точками, метры (равнопромежуточное приближение — на
    масштабе километров ошибка ничтожна)."""
    dlat = (a[0] - b[0]) * 111_320.0
    dlon = (a[1] - b[1]) * 111_320.0 * math.cos(math.radians(a[0]))
    return math.hypot(dlat, dlon)


def _pick(
    kind: str,
    target_m: int,
    origin: tuple[float, float],
    points: list[tuple[float, float]],
    dem: list[float],
) -> tuple[float, float, float]:
    """Выбор ячейки сетки.

    Вершина — просто локальный максимум. Для остальных типов нужную высоту в
    радиусе трёх километров даёт множество ячеек (горизонталь проходит через
    полсклона), поэтому берём **ближайшую к исходной координате** из попавших в
    допуск: иначе база курорта «сходится» за три километра от себя. Если в
    допуск не попал никто — ближайшую по высоте, чтобы показать, насколько
    промах велик.
    """
    pairs = list(zip(points, dem))
    if kind == "peak":
        (lat, lon), elev = max(pairs, key=lambda pd: pd[1])
        return lat, lon, elev
    within = [pd for pd in pairs if abs(pd[1] - target_m) <= TOL]
    if within:
        (lat, lon), elev = min(within, key=lambda pd: _dist_m(origin, pd[0]))
    else:
        (lat, lon), elev = min(pairs, key=lambda pd: abs(pd[1] - target_m))
    return lat, lon, elev


def snap(lat: float, lon: float, target_m: int, kind: str) -> tuple[float, float, float]:
    """Двухступенчатый поиск по DEM: грубо ±3 км (шаг 1 км), затем ±500 м (шаг 250 м).

    Радиус выбран по масштабу расхождений в §7.3: промахи там — сотни метров и
    первые километры, а не десятки.
    """
    origin = (lat, lon)
    for radius, n in ((3000.0, 7), (500.0, 5)):
        points = _grid(lat, lon, radius, n)
        lat, lon, elev = _pick(kind, target_m, origin, points, fetch_dem(points))
    return lat, lon, elev


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сверка каталога с DEM (задача 0.3)")
    parser.add_argument("--drafts", action="store_true",
                        help="только черновые точки (Conf=L)")
    parser.add_argument("--snap", action="store_true",
                        help="искать исправленную координату для несошедшихся точек")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    items = [loc for loc in CATALOG.values() if not args.drafts or loc.is_draft]
    dem = fetch_dem([(loc.lat, loc.lon) for loc in items])

    print(f"{'id':<22}{'conf':<6}{'каталог':>9}{'DEM':>8}{'Δ':>8}  вердикт")
    print("─" * 78)
    off: list[tuple] = []
    for loc, dem_m in zip(items, dem):
        diff = round(dem_m) - loc.elevation_m
        v = verdict(loc.id, diff)
        if v != "сходится":
            off.append((loc, diff))
        print(f"{loc.id:<22}{loc.conf:<6}{loc.elevation_m:>9}{round(dem_m):>8}"
              f"{diff:>+8}  {v}")
    print("─" * 78)
    print(f"точек: {len(items)}, требуют разбора (FR-LOC-1): {len(off)}")
    print("Источник DEM: Copernicus GLO-90 через Open-Meteo Elevation API.")

    if args.snap and off:
        print(f"\nПоиск координат для {len(off)} точек "
              f"(peak — максимум рельефа, at — высота из каталога).\n")
        print(f"{'id':<22}{'тип':<6}{'lat':>9}{'lon':>9}{'DEM':>7}"
              f"{'было':>7}{'стало':>7}{'сдвиг':>8}  итог")
        print("─" * 86)
        for loc, was in off:
            kind = KIND.get(loc.id, "at")
            lat, lon, elev = snap(loc.lat, loc.lon, loc.elevation_m, kind)
            now = round(elev) - loc.elevation_m
            moved = _dist_m((loc.lat, loc.lon), (lat, lon)) / 1000.0
            ok = "сошлась" if abs(now) <= tolerance(loc.id) else "остаётся черновиком"
            print(f"{loc.id:<22}{kind:<6}{lat:>9}{lon:>9}{round(elev):>7}"
                  f"{was:>+7}{now:>+7}{moved:>7.1f}к  {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
