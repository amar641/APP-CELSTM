#!/usr/bin/env python
"""
Seed a small hand-picked facility list, ported from the original MVP's
`app/facilities.py`. Useful for testing the proximity signal end-to-end
before OSM ingestion (`scripts/ingest/ingest_osm.py`) is run for real.

    uv run python scripts/seed/seed_facilities.py
"""

from __future__ import annotations

import asyncio

from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.core.types import FacilityType
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository
from industrial_fire.infrastructure.database.session import get_session_factory

logger = get_logger(__name__)

SAMPLE_FACILITIES = [
    Facility.new(
        name="Mathura refinery",
        facility_type=FacilityType.REFINERY,
        location=Coordinates(latitude=22.470, longitude=70.050),
    ),
    Facility.new(
        name="Surat power plant",
        facility_type=FacilityType.POWER_PLANT,
        location=Coordinates(latitude=23.020, longitude=72.580),
    ),
    Facility.new(
        name="Tata steel",
        facility_type=FacilityType.STEEL,
        location=Coordinates(latitude=21.170, longitude=72.830),
    ),
]


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlFacilityRepository(session)
        saved = await repository.upsert_many(SAMPLE_FACILITIES)
        await session.commit()

    logger.info("seeded %d sample facilities", len(saved))


if __name__ == "__main__":
    ensure_selector_event_loop()
    asyncio.run(main())
