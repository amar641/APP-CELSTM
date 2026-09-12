"""
Repository interface for `ThermalEvent` persistence.

The application layer depends only on this abstract interface (dependency
inversion) — the concrete SQLAlchemy/PostGIS implementation lives in
`infrastructure.database.repositories.thermal_event_repository` and is
injected via `api/dependencies.py` or a script's composition root.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.domain.value_objects.time_range import TimeRange


class ThermalEventRepository(ABC):
    @abstractmethod
    async def upsert(self, event: ThermalEvent) -> ThermalEvent:
        """Idempotent insert keyed on `ThermalEvent.natural_key` — safe to call repeatedly."""

    @abstractmethod
    async def upsert_many(self, events: list[ThermalEvent]) -> list[ThermalEvent]:
        ...

    @abstractmethod
    async def get(self, event_id: UUID) -> ThermalEvent | None:
        ...

    @abstractmethod
    async def find_in_bbox(
        self, bbox: BoundingBox, time_range: TimeRange
    ) -> list[ThermalEvent]:
        ...

    @abstractmethod
    async def find_near(
        self, location: Coordinates, radius_km: float, time_range: TimeRange
    ) -> list[ThermalEvent]:
        """Used for the persistence signal — detections near a point over a history window."""
