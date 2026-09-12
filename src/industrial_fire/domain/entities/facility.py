"""An industrial facility sourced from OpenStreetMap (or a seed list before OSM ingestion is wired up)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from industrial_fire.core.types import FacilityType
from industrial_fire.domain.value_objects.coordinates import Coordinates


@dataclass(slots=True)
class Facility:
    id: UUID
    name: str
    facility_type: FacilityType
    location: Coordinates
    osm_id: str | None = None  # None for manually seeded facilities

    @classmethod
    def new(
        cls,
        *,
        name: str,
        facility_type: FacilityType,
        location: Coordinates,
        osm_id: str | None = None,
    ) -> Facility:
        return cls(id=uuid4(), name=name, facility_type=facility_type, location=location, osm_id=osm_id)
