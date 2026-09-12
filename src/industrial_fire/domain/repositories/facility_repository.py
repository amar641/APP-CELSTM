from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates


class FacilityRepository(ABC):
    @abstractmethod
    async def upsert(self, facility: Facility) -> Facility:
        ...

    @abstractmethod
    async def upsert_many(self, facilities: list[Facility]) -> list[Facility]:
        ...

    @abstractmethod
    async def get(self, facility_id: UUID) -> Facility | None:
        ...

    @abstractmethod
    async def find_in_bbox(self, bbox: BoundingBox) -> list[Facility]:
        ...

    @abstractmethod
    async def find_nearest(self, location: Coordinates, limit: int = 1) -> list[Facility]:
        """Ordered nearest-first. Used for the facility-proximity signal."""
