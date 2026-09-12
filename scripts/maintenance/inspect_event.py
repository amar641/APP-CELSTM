#!/usr/bin/env python
"""
Trace one thermal event through the whole pipeline for manual inspection:
enrichment signals, satellite rounds + embeddings, and the latest
classification/risk — everything GET /events computes, printed instead of
returned as JSON.

    uv run python scripts/maintenance/inspect_event.py <thermal_event_id>
"""

from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.infrastructure.database.repositories.classification_repository import (
    SqlClassificationRepository,
)
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository
from industrial_fire.infrastructure.database.repositories.satellite_image_repository import (
    SqlSatelliteImageRepository,
)
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.repositories.weather_repository import SqlWeatherRepository
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.core.config import get_settings

logger = get_logger(__name__)


async def main(event_id: UUID) -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    async with session_factory() as session:
        thermal_event_repository = SqlThermalEventRepository(session)
        facility_repository = SqlFacilityRepository(session)
        weather_repository = SqlWeatherRepository(session)
        satellite_image_repository = SqlSatelliteImageRepository(session)
        classification_repository = SqlClassificationRepository(session)
        embedding_reader = QdrantEmbeddingRepository(get_qdrant_client(), settings.qdrant_collection)

        event = await thermal_event_repository.get(event_id)
        if event is None:
            print(f"no thermal_event with id {event_id}")
            return

        print(f"=== ThermalEvent {event.id} ===")
        print(f"  location: {event.location.latitude:.5f}, {event.location.longitude:.5f}")
        print(f"  acquired_at: {event.acquired_at}  frp_mw: {event.frp_mw}  source: {event.source.value}")

        enrichment = SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)
        enriched = await enrichment.execute(event)
        print("\n=== Spatial enrichment ===")
        fac = enriched.proximity.facility
        print(f"  nearest facility: {fac.name if fac else None} ({enriched.proximity.distance_km} km)")
        print(f"  persistence_count: {enriched.persistence.matched_event_count}")
        print(f"  frp_deviation_pct: {enriched.persistence.frp_deviation_pct(event.frp_mw)}")

        feature_assembly = AssembleFeaturesUseCase(
            enrichment, weather_repository, satellite_image_repository, embedding_reader
        )
        rounds = await feature_assembly.execute_sequence(event)
        print(f"\n=== Satellite rounds ({len(rounds)}) — this is what CE-LSTM would see ===")
        for i, bundle in enumerate(rounds):
            has_vec = bundle.vision_embedding is not None
            img = bundle.satellite_images[0] if bundle.satellite_images else None
            print(
                f"  round {i}: acquired={img.acquired_at if img else 'n/a'} "
                f"has_embedding={has_vec} structured={bundle.structured_features}"
            )

        classification = await classification_repository.latest_for_event(event.id)
        risk = await classification_repository.latest_risk_for_event(event.id)
        print("\n=== Latest classification ===")
        if classification:
            print(f"  label: {classification.label.value}")
            print(f"  confidence: {classification.confidence:.2f}")
            print(f"  model: {classification.model_source.value} ({classification.model_version})")
            print(f"  reasoning: {classification.reasoning}")
        else:
            print("  none yet — hit GET /api/v1/events to classify it")

        print("\n=== Latest risk ===")
        if risk:
            print(f"  level: {risk.risk_level.value}  score: {risk.risk_score:.2f}")
            print(f"  factors: {risk.contributing_factors}")
        else:
            print("  none yet")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: inspect_event.py <thermal_event_id>")
        raise SystemExit(1)
    ensure_selector_event_loop()
    asyncio.run(main(UUID(sys.argv[1])))
