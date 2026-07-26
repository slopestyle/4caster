"""Seed-каталог локаций для среза (подмножество PRD §7.3).

Кластер CL-ALP-W — «Высокогорье Западного Кавказа (Аибга–Псеашхо)».
Ачишхо взят из seed-набора §7.3. Аибга отдельной строкой в §7.3
отсутствует; заведена как точка того же кластера (ориентир — гребень
Аибга / Роза Пик). Координаты [ASSUMPTION] — требуют верификации
по DEM/топокарте (Задача 0.3 плана §19.2) до эксплуатации.
"""

from __future__ import annotations

from fourcaster.shared_kernel.geo import Coordinate, Location

CATALOG: dict[str, Location] = {
    "achishkho": Location(
        id="achishkho",
        name="Ачишхо",
        coord=Coordinate(43.725, 40.180),
        elevation_m=2391,
        cluster="CL-ALP-W",
    ),
    "aibga": Location(
        id="aibga",
        name="Аибга",
        coord=Coordinate(43.626, 40.315),
        elevation_m=2509,
        cluster="CL-ALP-W",
    ),
}


def get_location(location_id: str) -> Location:
    try:
        return CATALOG[location_id]
    except KeyError:
        raise KeyError(
            f"Локация '{location_id}' не найдена. Доступны: {', '.join(CATALOG)}"
        ) from None
