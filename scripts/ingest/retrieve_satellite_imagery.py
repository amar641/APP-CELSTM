#!/usr/bin/env python
"""
Composition-root script: for thermal hotspots already ingested from FIRMS
(`scripts/ingest/ingest_firms.py`) that don't have satellite imagery yet,
auto-derive a small search footprint from each hotspot's own coordinates
(`BoundingBox.around`), fetch+preprocess+embed imagery, and persist
structured features (Postgres) + embedding (Qdrant).

    uv run python scripts/ingest/retrieve_satellite_imagery.py [--days-back N]

Idempotent by design: a hotspot that already has at least one
`satellite_images` row is skipped, so re-running this (e.g. on the same
schedule as `ingest_firms.py`) only fetches imagery for genuinely new
detections — including repeat detections at a location already covered,
which is what lets persistence/history checks reuse what's already stored
instead of re-fetching from FIRMS/STAC every time.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from industrial_fire.application.satellite.retrieve_satellite_imagery import (
    RetrieveSatelliteImageryUseCase,
)
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.time_range import TimeRange
from industrial_fire.infrastructure.database.models.satellite_image import SatelliteImageModel
from industrial_fire.infrastructure.database.repositories.satellite_image_repository import (
    SqlSatelliteImageRepository,
)
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.infrastructure.satellite.preprocessor import RasterioImagePreprocessor
from industrial_fire.infrastructure.satellite.stac_client import StacSatelliteImageProvider
from industrial_fire.ml.encoders.vision_encoder import ResNetVisionEncoder

logger = get_logger(__name__)


async def main(days_back: int) -> None:
    settings = get_settings()
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    time_range = TimeRange.last_n_days(days_back or settings.history_days)
    sat_cfg = settings.data_config.get("satellite", {})

    session_factory = get_session_factory()
    async with session_factory() as session:
        thermal_event_repository = SqlThermalEventRepository(session)
        satellite_image_repository = SqlSatelliteImageRepository(session)

        candidates = await thermal_event_repository.find_in_bbox(bbox, time_range)
        already_covered = set(
            (await session.execute(select(SatelliteImageModel.thermal_event_id))).scalars().all()
        )
        pending = [e for e in candidates if e.id not in already_covered]
        logger.info(
            "%d hotspots in AOI/window, %d already have imagery, %d pending",
            len(candidates), len(already_covered), len(pending),
        )
        if not pending:
            return

        provider = StacSatelliteImageProvider(
            api_url=settings.stac_api_url,
            collection=settings.stac_collection,
            cache_dir=settings.satellite_image_cache_dir,
            bands=sat_cfg.get("bands", ["B04", "B03", "B02", "B08"]),
        )
        preprocessor = RasterioImagePreprocessor(bands=sat_cfg.get("bands", ["B04", "B03", "B02", "B08"]))
        extractor = ResNetVisionEncoder(device=settings.model_device)

        qdrant_client = get_qdrant_client()
        embedding_writer = QdrantEmbeddingRepository(qdrant_client, settings.qdrant_collection)
        await embedding_writer.ensure_collection()

        use_case = RetrieveSatelliteImageryUseCase(
            provider=provider,
            preprocessor=preprocessor,
            extractor=extractor,
            repository=satellite_image_repository,
            embedding_writer=embedding_writer,
            max_cloud_cover_pct=sat_cfg.get("max_cloud_cover_pct", 20.0),
        )

        radius_km = sat_cfg.get("footprint_radius_km", 2.0)
        total_images = 0
        for event in pending:
            footprint = BoundingBox.around(event.location, radius_km)
            try:
                images = await use_case.execute(event, footprint)
                total_images += len(images)
            except Exception:  # noqa: BLE001 - one bad hotspot shouldn't stop the batch
                logger.exception("satellite retrieval failed for thermal_event_id=%s", event.id)

        await session.commit()

    logger.info("retrieved %d satellite images across %d hotspots", total_images, len(pending))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days-back", type=int, default=0, help="lookback window; 0 = use HISTORY_DAYS from config"
    )
    args = parser.parse_args()
    ensure_selector_event_loop()
    asyncio.run(main(args.days_back))
