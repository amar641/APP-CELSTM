"""Concrete `ThermalEventRepository` backed by Postgres/PostGIS via SQLAlchemy + GeoAlchemy2."""

from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geography, Geometry
from geoalchemy2.functions import ST_DWithin, ST_MakeEnvelope, ST_X, ST_Y
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.core.types import ThermalSource
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.repositories.thermal_event_repository import ThermalEventRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.domain.value_objects.time_range import TimeRange
from industrial_fire.infrastructure.database.models.thermal_event import ThermalEventModel

_AS_GEOM = lambda col: cast(col, Geometry)  # noqa: E731 - geography -> geometry for ST_X/ST_Y


def _to_entity(row: ThermalEventModel, lon: float, lat: float) -> ThermalEvent:
    return ThermalEvent(
        id=row.id,
        location=Coordinates(latitude=lat, longitude=lon),
        brightness_kelvin=row.brightness_kelvin,
        frp_mw=row.frp_mw,
        confidence=row.confidence,
        acquired_at=row.acquired_at,
        source=ThermalSource(row.source),
        ingested_at=row.ingested_at,
    )


class SqlThermalEventRepository(ThermalEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, event: ThermalEvent) -> ThermalEvent:
        return (await self.upsert_many([event]))[0]

    async def upsert_many(self, events: list[ThermalEvent]) -> list[ThermalEvent]:
        if not events:
            return []
        rows = [
            {
                "id": e.id,
                "location": e.location.as_wkt_point(),
                "brightness_kelvin": e.brightness_kelvin,
                "frp_mw": e.frp_mw,
                "confidence": e.confidence,
                "acquired_at": e.acquired_at,
                "source": e.source.value,
                "ingested_at": e.ingested_at,
            }
            for e in events
        ]
        stmt = pg_insert(ThermalEventModel).values(rows)
        # DO UPDATE (a no-op touch of ingested_at), not DO NOTHING: with DO
        # NOTHING, a row that already exists (re-ingesting a day already
        # pulled) keeps its ORIGINAL id in the table, but this method would
        # still return the freshly-generated, never-persisted id from the
        # input `events` — every downstream write (classification_results,
        # satellite_images, ...) then references an id that isn't actually
        # in `thermal_events`, and fails its foreign key constraint.
        # RETURNING gives back the id that's really stored, in insert order,
        # so callers always get a persisted, referenceable id.
        stmt = stmt.on_conflict_do_update(
            index_elements=["acquired_at", "source", "location"],
            set_={"ingested_at": stmt.excluded.ingested_at},
        ).returning(ThermalEventModel.id)
        result = await self._session.execute(stmt)
        persisted_ids = [row[0] for row in result.all()]
        await self._session.flush()
        return [
            ThermalEvent(
                id=persisted_id,
                location=e.location,
                brightness_kelvin=e.brightness_kelvin,
                frp_mw=e.frp_mw,
                confidence=e.confidence,
                acquired_at=e.acquired_at,
                source=e.source,
                ingested_at=e.ingested_at,
            )
            for persisted_id, e in zip(persisted_ids, events)
        ]

    async def get(self, event_id: UUID) -> ThermalEvent | None:
        stmt = select(
            ThermalEventModel, ST_X(_AS_GEOM(ThermalEventModel.location)), ST_Y(_AS_GEOM(ThermalEventModel.location))
        ).where(ThermalEventModel.id == event_id)
        result = await self._session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        model, lon, lat = row
        return _to_entity(model, lon, lat)

    async def find_in_bbox(self, bbox: BoundingBox, time_range: TimeRange) -> list[ThermalEvent]:
        envelope = ST_MakeEnvelope(bbox.west, bbox.south, bbox.east, bbox.north, 4326)
        stmt = select(
            ThermalEventModel, ST_X(_AS_GEOM(ThermalEventModel.location)), ST_Y(_AS_GEOM(ThermalEventModel.location))
        ).where(
            _AS_GEOM(ThermalEventModel.location).op("&&")(envelope),
            ThermalEventModel.acquired_at >= time_range.start,
            ThermalEventModel.acquired_at <= time_range.end,
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row, lon, lat) for row, lon, lat in result.all()]

    async def find_near(
        self, location: Coordinates, radius_km: float, time_range: TimeRange
    ) -> list[ThermalEvent]:
        # Cast explicitly to `geography` — otherwise the bound string param
        # arrives typed as varchar and ST_DWithin(geography, varchar, ...)
        # has no matching overload (UndefinedFunction).
        point = cast(f"SRID=4326;{location.as_wkt_point()}", Geography)
        stmt = select(
            ThermalEventModel, ST_X(_AS_GEOM(ThermalEventModel.location)), ST_Y(_AS_GEOM(ThermalEventModel.location))
        ).where(
            ST_DWithin(ThermalEventModel.location, point, radius_km * 1000),
            ThermalEventModel.acquired_at >= time_range.start,
            ThermalEventModel.acquired_at <= time_range.end,
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row, lon, lat) for row, lon, lat in result.all()]
