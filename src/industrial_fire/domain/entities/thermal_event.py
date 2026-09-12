"""A single NASA FIRMS thermal detection — the core observation the whole pipeline hangs off."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from industrial_fire.core.types import ThermalSource
from industrial_fire.domain.value_objects.coordinates import Coordinates


@dataclass(slots=True)
class ThermalEvent:
    id: UUID
    location: Coordinates
    brightness_kelvin: float
    frp_mw: float  # Fire Radiative Power, megawatts
    confidence: str
    acquired_at: datetime
    source: ThermalSource
    ingested_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def new(
        cls,
        *,
        location: Coordinates,
        brightness_kelvin: float,
        frp_mw: float,
        confidence: str,
        acquired_at: datetime,
        source: ThermalSource,
    ) -> ThermalEvent:
        return cls(
            id=uuid4(),
            location=location,
            brightness_kelvin=brightness_kelvin,
            frp_mw=frp_mw,
            confidence=confidence,
            acquired_at=acquired_at,
            source=source,
        )

    @property
    def natural_key(self) -> tuple[float, float, datetime, ThermalSource]:
        """Used by ingestion to dedupe/upsert idempotently instead of relying on `id`."""
        return (
            round(self.location.latitude, 5),
            round(self.location.longitude, 5),
            self.acquired_at,
            self.source,
        )
