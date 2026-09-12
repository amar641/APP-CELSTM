"""
Use case: assemble the multimodal `FeatureBundle`(s) that CE-LSTM consumes.

`execute()` builds one bundle from an event's current signals. `execute_sequence()`
builds one bundle per satellite-image round retrieved for the event — see
docs/ml/celstm.md for why rounds map to satellite retrievals. Each bundle combines:
  - structured features from spatial enrichment (proximity, persistence, FRP deviation)
  - weather features
  - that round's satellite structured features (Postgres)
  - that round's satellite embedding (Qdrant, fetched by SatelliteImage.id)

This is the seam between `application` and `ml`: `ml.datasets` consumes
`FeatureBundle` objects, so the ML layer never talks to repositories or
external providers directly — see docs/ml/feature-contract.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import numpy as np

from industrial_fire.application.enrichment.spatial_enrichment import (
    EnrichedThermalEvent,
    SpatialEnrichmentUseCase,
)
from industrial_fire.core.exceptions import FeatureAssemblyError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.satellite_image import SatelliteImage
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.entities.weather_observation import WeatherObservation
from industrial_fire.domain.repositories.satellite_image_repository import SatelliteImageRepository
from industrial_fire.domain.repositories.weather_repository import WeatherRepository
from industrial_fire.domain.value_objects.time_range import TimeRange

logger = get_logger(__name__)


@dataclass(slots=True)
class FeatureBundle:
    """Everything CELSTM needs for one thermal event. See docs/ml/feature-contract.md."""

    thermal_event_id: UUID
    structured_features: dict[str, float] = field(default_factory=dict)
    vision_embedding: np.ndarray | None = None  # shape (vision_embedding_dim,)
    weather: WeatherObservation | None = None
    satellite_images: list[SatelliteImage] = field(default_factory=list)


class AssembleFeaturesUseCase:
    def __init__(
        self,
        enrichment: SpatialEnrichmentUseCase,
        weather_repository: WeatherRepository,
        satellite_image_repository: SatelliteImageRepository,
        embedding_reader: Any,  # infrastructure.qdrant.embedding_repository.EmbeddingRepository
    ) -> None:
        self._enrichment = enrichment
        self._weather_repository = weather_repository
        self._satellite_image_repository = satellite_image_repository
        self._embedding_reader = embedding_reader

    async def execute(self, event: ThermalEvent) -> FeatureBundle:
        try:
            enriched: EnrichedThermalEvent = await self._enrichment.execute(event)
        except Exception as exc:  # noqa: BLE001
            raise FeatureAssemblyError(f"Spatial enrichment failed: {exc}") from exc

        structured = {
            "frp_mw": event.frp_mw,
            "facility_distance_km": enriched.proximity.distance_km or -1.0,
            "persistence_count": float(enriched.persistence.matched_event_count),
            "frp_deviation_pct": enriched.persistence.frp_deviation_pct(event.frp_mw) or 0.0,
        }

        weather = await self._weather_repository.find_nearest_in_time(
            event.location, TimeRange.last_n_days(0, now=event.acquired_at)
        )
        if weather is not None:
            structured.update(
                {
                    "temperature_c": weather.temperature_c or 0.0,
                    "wind_speed_ms": weather.wind_speed_ms or 0.0,
                    "wind_direction_deg": weather.wind_direction_deg or 0.0,
                    "relative_humidity_pct": weather.relative_humidity_pct or 0.0,
                }
            )

        images = await self._satellite_image_repository.find_for_thermal_event(event.id)
        embedding = None
        if images:
            latest = max(images, key=lambda im: im.acquired_at)
            if latest.has_embedding:
                embedding = await self._embedding_reader.get(vector_id=latest.id)

        return FeatureBundle(
            thermal_event_id=event.id,
            structured_features=structured,
            vision_embedding=embedding,
            weather=weather,
            satellite_images=images,
        )

    async def execute_sequence(self, event: ThermalEvent) -> list[FeatureBundle]:
        """
        One `FeatureBundle` per satellite image retrieved for this event,
        oldest-acquired first — these are the CE-LSTM's temporal "rounds"
        (see docs/ml/celstm.md). Event-level signals (FRP/proximity/
        persistence/weather) are shared across rounds; only the vision
        embedding and that image's own structured features vary per round.
        If no imagery has been retrieved yet, returns a single round built
        from event-level signals alone (no vision source available).
        """
        try:
            enriched: EnrichedThermalEvent = await self._enrichment.execute(event)
        except Exception as exc:  # noqa: BLE001
            raise FeatureAssemblyError(f"Spatial enrichment failed: {exc}") from exc

        structured = {
            "frp_mw": event.frp_mw,
            "facility_distance_km": enriched.proximity.distance_km or -1.0,
            "persistence_count": float(enriched.persistence.matched_event_count),
            "frp_deviation_pct": enriched.persistence.frp_deviation_pct(event.frp_mw) or 0.0,
        }

        weather = await self._weather_repository.find_nearest_in_time(
            event.location, TimeRange.last_n_days(0, now=event.acquired_at)
        )
        if weather is not None:
            structured.update(
                {
                    "temperature_c": weather.temperature_c or 0.0,
                    "wind_speed_ms": weather.wind_speed_ms or 0.0,
                    "wind_direction_deg": weather.wind_direction_deg or 0.0,
                    "relative_humidity_pct": weather.relative_humidity_pct or 0.0,
                }
            )

        images = sorted(
            await self._satellite_image_repository.find_for_thermal_event(event.id),
            key=lambda im: im.acquired_at,
        )
        if not images:
            return [
                FeatureBundle(
                    thermal_event_id=event.id, structured_features=dict(structured), weather=weather
                )
            ]

        bundles: list[FeatureBundle] = []
        for image in images:
            round_structured = {**structured, **{f"vision_{k}": v for k, v in image.structured_features.items()}}
            embedding = None
            if image.has_embedding:
                embedding = await self._embedding_reader.get(vector_id=image.id)
            bundles.append(
                FeatureBundle(
                    thermal_event_id=event.id,
                    structured_features=round_structured,
                    vision_embedding=embedding,
                    weather=weather,
                    satellite_images=[image],
                )
            )
        return bundles
