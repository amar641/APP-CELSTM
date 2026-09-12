"""Pure domain logic for the facility-proximity signal. No I/O — callers supply candidates already loaded from a repository."""

from __future__ import annotations

from dataclasses import dataclass

from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.value_objects.coordinates import Coordinates


@dataclass(frozen=True, slots=True)
class ProximityResult:
    facility: Facility | None
    distance_km: float | None

    def is_within(self, radius_km: float) -> bool:
        return self.distance_km is not None and self.distance_km <= radius_km


class ProximityService:
    @staticmethod
    def nearest_facility(location: Coordinates, facilities: list[Facility]) -> ProximityResult:
        if not facilities:
            return ProximityResult(facility=None, distance_km=None)
        best = min(facilities, key=lambda f: location.distance_km(f.location))
        return ProximityResult(facility=best, distance_km=round(location.distance_km(best.location), 2))
