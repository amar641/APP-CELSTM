"""Immutable geographic point + distance math shared by every layer that needs it."""

from __future__ import annotations

import math
from dataclasses import dataclass

_EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True, slots=True)
class Coordinates:
    """WGS84 latitude/longitude, degrees."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(f"longitude out of range: {self.longitude}")

    def distance_km(self, other: Coordinates) -> float:
        """Great-circle (haversine) distance in kilometers."""
        p1, p2 = math.radians(self.latitude), math.radians(other.latitude)
        dp = math.radians(other.latitude - self.latitude)
        dl = math.radians(other.longitude - self.longitude)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))

    def as_wkt_point(self) -> str:
        """WKT `POINT(lon lat)` — PostGIS convention is (x=lon, y=lat)."""
        return f"POINT({self.longitude} {self.latitude})"
