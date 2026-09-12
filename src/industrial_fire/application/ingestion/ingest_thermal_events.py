"""
Use case: pull NASA FIRMS detections for the AOI and upsert them idempotently.

Depends only on the `ThermalEventProvider` port (implemented by
`infrastructure.firms.client.FirmsClient`) and the `ThermalEventRepository`
domain interface — never on httpx or SQLAlchemy directly. This is what
`scripts/ingest/ingest_firms.py` wires together at runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from industrial_fire.core.exceptions import UseCaseError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.repositories.thermal_event_repository import ThermalEventRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

logger = get_logger(__name__)


class ThermalEventProvider(ABC):
    """Port for any thermal-hotspot data source (FIRMS today; swappable later)."""

    @abstractmethod
    async def fetch_detections(self, bbox: BoundingBox, days_back: int = 0) -> list[ThermalEvent]:
        ...


class IngestThermalEventsUseCase:
    def __init__(self, provider: ThermalEventProvider, repository: ThermalEventRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def execute(self, bbox: BoundingBox, days_back: int = 0) -> list[ThermalEvent]:
        try:
            detections = await self._provider.fetch_detections(bbox, days_back=days_back)
        except Exception as exc:  # noqa: BLE001 - re-raised as a typed use-case error
            raise UseCaseError(f"Failed to fetch thermal detections: {exc}") from exc

        logger.info("fetched %d thermal detections (days_back=%d)", len(detections), days_back)
        return await self._repository.upsert_many(detections)
