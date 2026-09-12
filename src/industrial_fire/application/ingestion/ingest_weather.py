"""Use case: pull weather observations for the AOI and upsert them for later joining onto thermal events."""

from __future__ import annotations

from abc import ABC, abstractmethod

from industrial_fire.core.exceptions import UseCaseError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.weather_observation import WeatherObservation
from industrial_fire.domain.repositories.weather_repository import WeatherRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

logger = get_logger(__name__)


class WeatherProvider(ABC):
    """Port for any weather data source (Open-Meteo today; swappable via WEATHER_PROVIDER)."""

    @abstractmethod
    async def fetch_observations(self, bbox: BoundingBox) -> list[WeatherObservation]:
        ...


class IngestWeatherUseCase:
    def __init__(self, provider: WeatherProvider, repository: WeatherRepository) -> None:
        self._provider = provider
        self._repository = repository

    async def execute(self, bbox: BoundingBox) -> list[WeatherObservation]:
        try:
            observations = await self._provider.fetch_observations(bbox)
        except Exception as exc:  # noqa: BLE001
            raise UseCaseError(f"Failed to fetch weather observations: {exc}") from exc

        logger.info("fetched %d weather observations", len(observations))
        return await self._repository.upsert_many(observations)
