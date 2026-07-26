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
    elevation_m: int
    cluster: str

    @property
    def lat(self) -> float:
        return self.coord.lat

    @property
    def lon(self) -> float:
        return self.coord.lon
