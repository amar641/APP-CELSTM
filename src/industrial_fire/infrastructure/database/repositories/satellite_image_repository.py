"""Concrete `SatelliteImageRepository` backed by Postgres/PostGIS. Embeddings are NOT handled here — see infrastructure.qdrant."""

from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_XMax, ST_XMin, ST_YMax, ST_YMin
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.domain.entities.satellite_image import SatelliteImage
from industrial_fire.domain.repositories.satellite_image_repository import SatelliteImageRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.models.satellite_image import SatelliteImageModel

_AS_GEOM = lambda col: cast(col, Geometry)  # noqa: E731


def _to_entity(row: SatelliteImageModel, west: float, south: float, east: float, north: float) -> SatelliteImage:
    return SatelliteImage(
        id=row.id,
        thermal_event_id=row.thermal_event_id,
        stac_item_id=row.stac_item_id,
        collection=row.collection,
        footprint=BoundingBox(west=west, south=south, east=east, north=north),
        acquired_at=row.acquired_at,
        cloud_cover_pct=row.cloud_cover_pct,
        local_path=row.local_path,
        structured_features=dict(row.structured_features or {}),
        has_embedding=row.has_embedding,
    )


class SqlSatelliteImageRepository(SatelliteImageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, image: SatelliteImage) -> SatelliteImage:
        footprint_wkt = (
            f"POLYGON(({image.footprint.west} {image.footprint.south},"
            f"{image.footprint.east} {image.footprint.south},"
            f"{image.footprint.east} {image.footprint.north},"
            f"{image.footprint.west} {image.footprint.north},"
            f"{image.footprint.west} {image.footprint.south}))"
        )
        row = {
            "id": image.id,
            "thermal_event_id": image.thermal_event_id,
            "stac_item_id": image.stac_item_id,
            "collection": image.collection,
            "footprint": footprint_wkt,
            "acquired_at": image.acquired_at,
            "cloud_cover_pct": image.cloud_cover_pct,
            "local_path": image.local_path,
            "structured_features": image.structured_features,
            "has_embedding": image.has_embedding,
        }
        stmt = pg_insert(SatelliteImageModel).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "local_path": stmt.excluded.local_path,
                "structured_features": stmt.excluded.structured_features,
                "has_embedding": stmt.excluded.has_embedding,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return image

    async def get(self, image_id: UUID) -> SatelliteImage | None:
        geom = _AS_GEOM(SatelliteImageModel.footprint)
        stmt = select(
            SatelliteImageModel, ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
        ).where(SatelliteImageModel.id == image_id)
        result = await self._session.execute(stmt)
        row = result.first()
        return _to_entity(*row) if row else None

    async def find_for_thermal_event(self, thermal_event_id: UUID) -> list[SatelliteImage]:
        geom = _AS_GEOM(SatelliteImageModel.footprint)
        stmt = select(
            SatelliteImageModel, ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
        ).where(SatelliteImageModel.thermal_event_id == thermal_event_id)
        result = await self._session.execute(stmt)
        return [_to_entity(row, w, s, e, n) for row, w, s, e, n in result.all()]
