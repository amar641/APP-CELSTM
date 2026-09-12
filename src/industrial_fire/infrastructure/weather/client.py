"""
Open-Meteo adapter — implements the `WeatherProvider` port.

`WEATHER_PROVIDER` in `.env` documents the intent to swap providers; doing
so means adding a new class here that implements the same port, with no
change to `application.ingestion.ingest_weather`.
"""

from __future__ import annotations

from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from industrial_fire.application.ingestion.ingest_weather import WeatherProvider
from industrial_fire.core.exceptions import ExternalServiceError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.weather_observation import WeatherObservation
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates

logger = get_logger(__name__)


class OpenMeteoWeatherProvider(WeatherProvider):
    """
    Open-Meteo only supports point queries, not bbox — so this samples the
    AOI's centroid. Good enough for a regional weather signal; swap for a
    gridded provider if per-facility weather is needed later.
    """

    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._base_url = base_url
        self._api_key = api_key

    async def fetch_observations(self, bbox: BoundingBox) -> list[WeatherObservation]:
        centroid = Coordinates(
            latitude=(bbox.south + bbox.north) / 2, longitude=(bbox.west + bbox.east) / 2
        )
        params = {
            "latitude": centroid.latitude,
            "longitude": centroid.longitude,
            "current": "temperature_2m,wind_speed_10m,wind_direction_10m,relative_humidity_2m",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await self._get(client, params)
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Open-Meteo", f"request failed: {exc}") from exc

        current = resp.get("current", {})
        if not current:
            return []

        observation = WeatherObservation.new(
            location=centroid,
            observed_at=datetime.fromisoformat(current["time"]),
            temperature_c=current.get("temperature_2m"),
            wind_speed_ms=current.get("wind_speed_10m"),
            wind_direction_deg=current.get("wind_direction_10m"),
            relative_humidity_pct=current.get("relative_humidity_2m"),
            provider="open-meteo",
        )
        return [observation]

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _get(self, client: httpx.AsyncClient, params: dict) -> dict:
        resp = await client.get(f"{self._base_url}/forecast", params=params)
        resp.raise_for_status()
        return resp.json()
