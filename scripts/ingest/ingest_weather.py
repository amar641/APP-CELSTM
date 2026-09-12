#!/usr/bin/env python
"""
Composition-root script: pull current weather for the configured AOI's
centroid and upsert it into Postgres.

    uv run python scripts/ingest/ingest_weather.py

Run per `configs/app.yaml:ingestion.weather.refresh_interval_minutes`.
"""

from __future__ import annotations

import asyncio

from industrial_fire.application.ingestion.ingest_weather import IngestWeatherUseCase
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.repositories.weather_repository import SqlWeatherRepository
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.weather.client import OpenMeteoWeatherProvider

logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    bbox = BoundingBox.from_csv(settings.aoi_bbox)

    provider = OpenMeteoWeatherProvider(
        base_url=settings.weather_api_base_url, api_key=settings.weather_api_key
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlWeatherRepository(session)
        use_case = IngestWeatherUseCase(provider, repository)
        observations = await use_case.execute(bbox)
        await session.commit()

    logger.info("ingested %d weather observations", len(observations))


if __name__ == "__main__":
    ensure_selector_event_loop()
    asyncio.run(main())
