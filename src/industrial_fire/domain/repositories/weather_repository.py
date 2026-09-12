from __future__ import annotations

from abc import ABC, abstractmethod

from industrial_fire.domain.entities.weather_observation import WeatherObservation
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.domain.value_objects.time_range import TimeRange


class WeatherRepository(ABC):
    @abstractmethod
    async def upsert_many(self, observations: list[WeatherObservation]) -> list[WeatherObservation]:
        ...

    @abstractmethod
    async def find_nearest_in_time(
        self, location: Coordinates, time_range: TimeRange, radius_km: float = 25.0
    ) -> WeatherObservation | None:
        """Closest observation in space+time — used to join weather onto a thermal event."""
