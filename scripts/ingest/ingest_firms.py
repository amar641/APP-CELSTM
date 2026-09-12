#!/usr/bin/env python
"""
Composition-root script: pull today's FIRMS detections for the configured
AOI and upsert them into Postgres.

    uv run python scripts/ingest/ingest_firms.py [--days-back N]

Run on a schedule (cron, GitHub Actions, Airflow, ...) per
`configs/app.yaml:ingestion.firms.poll_interval_minutes`.
"""

from __future__ import annotations

import argparse
import asyncio

from industrial_fire.application.ingestion.ingest_thermal_events import IngestThermalEventsUseCase
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.firms.client import FirmsClient

logger = get_logger(__name__)


async def main(days_back: int) -> None:
    settings = get_settings()
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    data_cfg = settings.data_config.get("firms", {})

    client = FirmsClient(
        map_key=settings.firms_map_key or "",
        base_url=data_cfg.get("base_url", "https://firms.modaps.eosdis.nasa.gov/api/area/csv"),
        source=settings.firms_source,
    )

    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlThermalEventRepository(session)
        use_case = IngestThermalEventsUseCase(client, repository)
        events = await use_case.execute(bbox, days_back=days_back)
        await session.commit()

    logger.info("ingested %d thermal events (days_back=%d)", len(events), days_back)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days-back", type=int, default=0, help="0 = today")
    args = parser.parse_args()
    ensure_selector_event_loop()
    asyncio.run(main(args.days_back))
