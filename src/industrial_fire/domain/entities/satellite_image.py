"""
A satellite image retrieved for a thermal event's surroundings.

Structured, queryable outputs of feature extraction (band statistics, burn
indices, etc.) live on this entity and are persisted in Postgres. The raw
embedding vector is NOT stored here — it goes to Qdrant, keyed by
`SatelliteImage.id`, so Qdrant never becomes the system of record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from industrial_fire.domain.value_objects.bounding_box import BoundingBox


@dataclass(slots=True)
class SatelliteImage:
    id: UUID
    thermal_event_id: UUID
    stac_item_id: str
    collection: str
    footprint: BoundingBox
    acquired_at: datetime
    cloud_cover_pct: float | None
    local_path: str | None = None  # where preprocessed image is cached, if downloaded
    structured_features: dict[str, float] = field(default_factory=dict)
    has_embedding: bool = False  # True once a vector has been written to Qdrant

    @classmethod
    def new(
        cls,
        *,
        thermal_event_id: UUID,
        stac_item_id: str,
        collection: str,
        footprint: BoundingBox,
        acquired_at: datetime,
        cloud_cover_pct: float | None,
    ) -> SatelliteImage:
        return cls(
            id=uuid4(),
            thermal_event_id=thermal_event_id,
            stac_item_id=stac_item_id,
            collection=collection,
            footprint=footprint,
            acquired_at=acquired_at,
            cloud_cover_pct=cloud_cover_pct,
        )
