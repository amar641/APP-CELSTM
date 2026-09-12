"""A weather observation joined to a thermal event's location/time for feature assembly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from industrial_fire.domain.value_objects.coordinates import Coordinates


@dataclass(slots=True)
class WeatherObservation:
    id: UUID
    location: Coordinates
    observed_at: datetime
    temperature_c: float | None
    wind_speed_ms: float | None
    wind_direction_deg: float | None
    relative_humidity_pct: float | None
    provider: str

    @classmethod
    def new(
        cls,
        *,
        location: Coordinates,
        observed_at: datetime,
        temperature_c: float | None,
        wind_speed_ms: float | None,
        wind_direction_deg: float | None,
        relative_humidity_pct: float | None,
        provider: str,
    ) -> WeatherObservation:
        return cls(
            id=uuid4(),
            location=location,
            observed_at=observed_at,
            temperature_c=temperature_c,
            wind_speed_ms=wind_speed_ms,
            wind_direction_deg=wind_direction_deg,
            relative_humidity_pct=relative_humidity_pct,
            provider=provider,
        )
