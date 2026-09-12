"""Use case: pull industrial facilities (OSM/Overpass today) and upsert them."""

from __future__ import annotations

from abc import ABC, abstractmethod

from industrial_fire.core.exceptions import UseCaseError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.repositories.facility_repository import FacilityRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

logger = get_logger(__name__)


class FacilityProvider(ABC):
    """Port for any industrial-facility data source (OSM/Overpass today)."""

    @abstractmethod
    async def fetch_facilities(self, bbox: BoundingBox) -> list[Facility]:
        ...


class IngestFacilitiesUseCase:
    def __init__(self, provider: FacilityProvider, repository: FacilityRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def execute(self, bbox: BoundingBox) -> list[Facility]:
        try:
            facilities = await self._provider.fetch_facilities(bbox)
        except Exception as exc:  # noqa: BLE001
            raise UseCaseError(f"Failed to fetch facilities: {exc}") from exc

        logger.info("fetched %d facilities", len(facilities))
        return await self._repository.upsert_many(facilities)
