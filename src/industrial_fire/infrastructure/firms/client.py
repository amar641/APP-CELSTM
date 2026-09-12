"""
NASA FIRMS adapter — implements the `ThermalEventProvider` port.

Ported from the original MVP's `app/firms_client.py`, with retry/backoff
and mapping into domain entities instead of ad hoc Pydantic models.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from industrial_fire.application.ingestion.ingest_thermal_events import ThermalEventProvider
from industrial_fire.core.exceptions import ExternalServiceError
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ThermalSource
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates

logger = get_logger(__name__)


class FirmsClient(ThermalEventProvider):
    def __init__(self, map_key: str, base_url: str, source: str) -> None:
        if not map_key:
            raise ExternalServiceError(
                "FIRMS",
                "FIRMS_MAP_KEY not set. Get a free key at "
                "https://firms.modaps.eosdis.nasa.gov/api/map_key/ and put it in .env",
            )
        self._map_key = map_key
        self._base_url = base_url
        self._source = source

    async def fetch_detections(self, bbox: BoundingBox, days_back: int = 0) -> list[ThermalEvent]:
        target_date = date.today() - timedelta(days=days_back)
        url = f"{self._base_url}/{self._map_key}/{self._source}/{bbox.to_csv()}/1/{target_date.isoformat()}"

        try:
            text = await self._get(url)
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("FIRMS", "did not respond within 30 seconds") from exc
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(
                "FIRMS",
                f"HTTP {exc.response.status_code} — check FIRMS_MAP_KEY, FIRMS_SOURCE, AOI_BBOX",
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError("FIRMS", "could not connect — check network connection") from exc

        return self._parse_csv(text)

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _get(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    def _parse_csv(self, text: str) -> list[ThermalEvent]:
        events: list[ThermalEvent] = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                acquired_at = datetime.strptime(
                    f"{row['acq_date']} {row.get('acq_time', '0000').zfill(4)}", "%Y-%m-%d %H%M"
                )
                events.append(
                    ThermalEvent.new(
                        location=Coordinates(
                            latitude=float(row["latitude"]), longitude=float(row["longitude"])
                        ),
                        brightness_kelvin=float(row.get("bright_ti4") or row.get("brightness") or 0),
                        frp_mw=float(row.get("frp") or 0),
                        confidence=str(row.get("confidence", "")),
                        acquired_at=acquired_at,
                        source=ThermalSource(self._source),
                    )
                )
            except (ValueError, KeyError):
                logger.debug("skipping malformed FIRMS row: %r", row)
                continue
        return events
