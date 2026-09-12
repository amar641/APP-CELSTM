#!/usr/bin/env python
"""
Composition-root script: pull industrial facilities from OSM/Overpass for
the configured AOI and upsert them into Postgres.

    uv run python scripts/ingest/ingest_osm.py

Run per `configs/app.yaml:ingestion.osm.refresh_interval_hours` — OSM data
changes far less often than thermal detections.
"""

from __future__ import annotations

import asyncio

from industrial_fire.application.ingestion.ingest_facilities import IngestFacilitiesUseCase
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.osm.overpass_client import OverpassFacilityProvider

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    osm_cfg = settings.data_config.get("osm", {})

    provider = OverpassFacilityProvider(
        api_url=settings.overpass_api_url,
        timeout_seconds=settings.overpass_timeout_seconds,
        facility_tags=osm_cfg.get("facility_tags", ["landuse=industrial"]),
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlFacilityRepository(session)
        use_case = IngestFacilitiesUseCase(provider, repository)
        facilities = await use_case.execute(bbox)
        await session.commit()

    logger.info("ingested %d facilities", len(facilities))


if __name__ == "__main__":
    ensure_selector_event_loop()
    asyncio.run(main())
