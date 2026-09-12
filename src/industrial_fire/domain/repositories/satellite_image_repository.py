from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from industrial_fire.domain.entities.satellite_image import SatelliteImage


class SatelliteImageRepository(ABC):
    """Persists structured satellite-image metadata/features in Postgres.

    Embedding vectors are NOT handled here — see
    `infrastructure.qdrant.embedding_repository.EmbeddingRepository`.
    """

    @abstractmethod
    async def upsert(self, image: SatelliteImage) -> SatelliteImage:
        ...

    @abstractmethod
    async def get(self, image_id: UUID) -> SatelliteImage | None:
        ...

    @abstractmethod
    async def find_for_thermal_event(self, thermal_event_id: UUID) -> list[SatelliteImage]:
        ...
