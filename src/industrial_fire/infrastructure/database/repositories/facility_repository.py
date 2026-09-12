"""Concrete `FacilityRepository` backed by Postgres/PostGIS."""

from __future__ import annotations

from uuid import UUID

from geoalchemy2 import Geography, Geometry
from geoalchemy2.functions import ST_Distance, ST_MakeEnvelope, ST_X, ST_Y
from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.core.types import FacilityType
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.repositories.facility_repository import FacilityRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.infrastructure.database.models.facility import FacilityModel

_AS_GEOM = lambda col: cast(col, Geometry)  # noqa: E731


def _to_entity(row: FacilityModel, lon: float, lat: float) -> Facility:
    return Facility(
        id=row.id,
        name=row.name,
        facility_type=FacilityType(row.facility_type),
        location=Coordinates(latitude=lat, longitude=lon),
        osm_id=row.osm_id,
    )


class SqlFacilityRepository(FacilityRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, facility: Facility) -> Facility:
        return (await self.upsert_many([facility]))[0]

    async def upsert_many(self, facilities: list[Facility]) -> list[Facility]:
        if not facilities:
            return []
        rows = [
            {
                "id": f.id,
                "name": f.name,
                "facility_type": f.facility_type.value,
                "location": f.location.as_wkt_point(),
                "osm_id": f.osm_id,
            }
            for f in facilities
        ]
        stmt = pg_insert(FacilityModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["osm_id"],
            set_={"name": stmt.excluded.name, "location": stmt.excluded.location},
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return facilities

    async def get(self, facility_id: UUID) -> Facility | None:
        stmt = select(FacilityModel, ST_X(_AS_GEOM(FacilityModel.location)), ST_Y(_AS_GEOM(FacilityModel.location))).where(
            FacilityModel.id == facility_id
        )
        result = await self._session.execute(stmt)
        row = result.first()
        return _to_entity(*row) if row else None

    async def find_in_bbox(self, bbox: BoundingBox) -> list[Facility]:
        envelope = ST_MakeEnvelope(bbox.west, bbox.south, bbox.east, bbox.north, 4326)
        stmt = select(FacilityModel, ST_X(_AS_GEOM(FacilityModel.location)), ST_Y(_AS_GEOM(FacilityModel.location))).where(
            _AS_GEOM(FacilityModel.location).op("&&")(envelope)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row, lon, lat) for row, lon, lat in result.all()]

    async def find_nearest(self, location: Coordinates, limit: int = 1) -> list[Facility]:
        # Cast explicitly to `geography` — without it, the bound string param
        # arrives at Postgres typed as varchar, and ST_Distance(geography,
        # varchar) has no matching overload (UndefinedFunction).
        point = cast(f"SRID=4326;{location.as_wkt_point()}", Geography)
        stmt = (
            select(FacilityModel, ST_X(_AS_GEOM(FacilityModel.location)), ST_Y(_AS_GEOM(FacilityModel.location)))
            .order_by(ST_Distance(FacilityModel.location, point))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [_to_entity(row, lon, lat) for row, lon, lat in result.all()]
