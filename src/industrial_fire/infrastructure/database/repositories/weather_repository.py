"""Concrete `WeatherRepository` backed by Postgres/PostGIS."""

from __future__ import annotations

from geoalchemy2.functions import ST_DWithin
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.domain.entities.weather_observation import WeatherObservation
from industrial_fire.domain.repositories.weather_repository import WeatherRepository
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.domain.value_objects.time_range import TimeRange
from industrial_fire.infrastructure.database.models.weather_observation import WeatherObservationModel


def _to_entity(row: WeatherObservationModel, lon: float, lat: float) -> WeatherObservation:
    return WeatherObservation(
        id=row.id,
        location=Coordinates(latitude=lat, longitude=lon),
        observed_at=row.observed_at,
        temperature_c=row.temperature_c,
        wind_speed_ms=row.wind_speed_ms,
        wind_direction_deg=row.wind_direction_deg,
        relative_humidity_pct=row.relative_humidity_pct,
        provider=row.provider,
    )


class SqlWeatherRepository(WeatherRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, observations: list[WeatherObservation]) -> list[WeatherObservation]:
        if not observations:
            return []
        rows = [
            {
                "id": o.id,
                "location": o.location.as_wkt_point(),
                "observed_at": o.observed_at,
                "temperature_c": o.temperature_c,
                "wind_speed_ms": o.wind_speed_ms,
                "wind_direction_deg": o.wind_direction_deg,
                "relative_humidity_pct": o.relative_humidity_pct,
                "provider": o.provider,
            }
            for o in observations
        ]
        await self._session.execute(pg_insert(WeatherObservationModel).values(rows))
        await self._session.flush()
        return observations

    async def find_nearest_in_time(
        self, location: Coordinates, time_range: TimeRange, radius_km: float = 25.0
    ) -> WeatherObservation | None:
        from geoalchemy2 import Geography, Geometry
        from sqlalchemy import cast

        # Cast explicitly to `geography` — otherwise the bound string param
        # arrives typed as varchar and ST_DWithin(geography, varchar, ...)
        # has no matching overload (UndefinedFunction).
        point = cast(f"SRID=4326;{location.as_wkt_point()}", Geography)
        geom = cast(WeatherObservationModel.location, Geometry)
        stmt = (
            select(WeatherObservationModel, func.ST_X(geom), func.ST_Y(geom))
            .where(
                ST_DWithin(WeatherObservationModel.location, point, radius_km * 1000),
                WeatherObservationModel.observed_at >= time_range.start,
                WeatherObservationModel.observed_at <= time_range.end,
            )
            .order_by(func.abs(func.extract("epoch", WeatherObservationModel.observed_at - time_range.end)))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.first()
        return _to_entity(*row) if row else None
