"""Area-of-interest bounding box, shared by FIRMS/OSM/STAC queries."""

from __future__ import annotations

import math
from dataclasses import dataclass

from industrial_fire.domain.value_objects.coordinates import Coordinates

_KM_PER_DEGREE_LATITUDE = 111.32


@dataclass(frozen=True, slots=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        if self.west >= self.east:
            raise ValueError(f"west ({self.west}) must be < east ({self.east})")
        if self.south >= self.north:
            raise ValueError(f"south ({self.south}) must be < north ({self.north})")

    @classmethod
    def from_csv(cls, csv: str) -> BoundingBox:
        """Parse `west,south,east,north` — the FIRMS/AOI_BBOX convention."""
        west, south, east, north = (float(x) for x in csv.split(","))
        return cls(west=west, south=south, east=east, north=north)

    def to_csv(self) -> str:
        return f"{self.west},{self.south},{self.east},{self.north}"

    @classmethod
    def around(cls, center: Coordinates, radius_km: float) -> BoundingBox:
        """
        A square footprint of `radius_km` around a single point — used to
        auto-derive a STAC search area from a thermal event's own
        coordinates instead of requiring a manually supplied bbox per event.
        """
        lat_delta = radius_km / _KM_PER_DEGREE_LATITUDE
        km_per_degree_longitude = _KM_PER_DEGREE_LATITUDE * max(
            math.cos(math.radians(center.latitude)), 0.01
        )
        lon_delta = radius_km / km_per_degree_longitude
        return cls(
            west=center.longitude - lon_delta,
            south=max(center.latitude - lat_delta, -90.0),
            east=center.longitude + lon_delta,
            north=min(center.latitude + lat_delta, 90.0),
        )

    def contains(self, point: Coordinates) -> bool:
        return self.west <= point.longitude <= self.east and self.south <= point.latitude <= self.north
