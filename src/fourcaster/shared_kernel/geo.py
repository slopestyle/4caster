"""Геопримитивы канонического ядра (PRD §7.1, §9.1).

Локация — это точка (lat, lon, elevation_m) + метаданные. Никаких
административных сущностей (принцип P6). Высота обязательна — она
передаётся провайдеру явно, иначе температура в горах уходит на 8–10 °C.
"""

from __future__ import annotations

from dataclasses import dataclass

# Bounding box региона (FR-LOC-4): 42.7–44.3 N, 39.5–42.2 E.
REGION_BBOX = (42.7, 44.3, 39.5, 42.2)  # lat_min, lat_max, lon_min, lon_max


@dataclass(frozen=True, slots=True)
class Coordinate:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        lat_min, lat_max, lon_min, lon_max = REGION_BBOX
        if not (lat_min <= self.lat <= lat_max and lon_min <= self.lon <= lon_max):
            raise ValueError(
                f"Координата ({self.lat}, {self.lon}) вне региона {REGION_BBOX}"
            )


@dataclass(frozen=True, slots=True)
class Location:
    id: str
    name: str
    coord: Coordinate
    elevation_m: int         # истинная высота точки — её передаём провайдеру
    cluster: str
    # FR-LOC-2: высота той же точки по DEM провайдера хранится отдельно.
    # Разница `elevation_m − dem_elevation_m` — это то, насколько сетка модели
    # «не видит» рельеф, и именно она нужна орографической коррекции (§10.3).
    dem_elevation_m: int = 0
    conf: str = "M"          # уверенность в координате: H / M / L (§7.3)
    is_draft: bool = False   # FR-LOC-5: черновая точка, пользователям не видна

    @property
    def dem_offset_m(self) -> int:
        """На сколько метров точка выше своей ячейки DEM (§10.3)."""
        return self.elevation_m - self.dem_elevation_m

    @property
    def lat(self) -> float:
        return self.coord.lat

    @property
    def lon(self) -> float:
        return self.coord.lon
