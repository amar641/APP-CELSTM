"""
OpenStreetMap/Overpass adapter — implements the `FacilityProvider` port.

Replaces the MVP's hardcoded `app/facilities.py` list with a real query
against tags configured in `configs/data.yaml:osm.facility_tags`. See
docs/data/osm.md for the query design and tag-to-FacilityType mapping.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from industrial_fire.application.ingestion.ingest_facilities import FacilityProvider
from industrial_fire.core.exceptions import ExternalServiceError
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import FacilityType
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.coordinates import Coordinates

logger = get_logger(__name__)

_TAG_TO_FACILITY_TYPE: dict[str, FacilityType] = {
    "man_made=works": FacilityType.OTHER,
    "industrial=refinery": FacilityType.REFINERY,
    "power=plant": FacilityType.POWER_PLANT,
    "landuse=industrial": FacilityType.OTHER,
    "man_made=petroleum_well": FacilityType.LNG,
}


class OverpassFacilityProvider(FacilityProvider):
    def __init__(self, api_url: str, timeout_seconds: int, facility_tags: list[str]) -> None:
        self._api_url = api_url
        self._timeout_seconds = timeout_seconds
        self._facility_tags = facility_tags

    async def fetch_facilities(self, bbox: BoundingBox) -> list[Facility]:
        query = self._build_query(bbox)
        try:
            data = await self._post(query)
        except httpx.TimeoutException as exc:
            raise ExternalServiceError("Overpass", "request timed out") from exc
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Overpass", f"request failed: {exc}") from exc

        return self._parse_elements(data.get("elements", []))

    def _build_query(self, bbox: BoundingBox) -> str:
        bbox_clause = f"{bbox.south},{bbox.west},{bbox.north},{bbox.east}"
        clauses = "\n".join(f"  node[{tag}]({bbox_clause});" for tag in self._facility_tags)
        return f"[out:json][timeout:{self._timeout_seconds}];\n(\n{clauses}\n);\nout center;"

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def _post(self, query: str) -> dict:
        # Overpass rejects requests without an identifying User-Agent (returns 406).
        # See https://wiki.openstreetmap.org/wiki/Overpass_API#Introduction
        headers = {
            "User-Agent": "industrial-fire-ai/0.1 (https://github.com/industrial-fire-ai)",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds, headers=headers) as client:
            resp = await client.post(self._api_url, data={"data": query})
            resp.raise_for_status()
            return resp.json()

    def _parse_elements(self, elements: list[dict]) -> list[Facility]:
        facilities: list[Facility] = []
        for el in elements:
            try:
                tags = el.get("tags", {})
                facility_type = self._infer_type(tags)
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                if lat is None or lon is None:
                    continue
                facilities.append(
                    Facility.new(
                        name=tags.get("name", f"Unnamed {facility_type.value}"),
                        facility_type=facility_type,
                        location=Coordinates(latitude=float(lat), longitude=float(lon)),
                        osm_id=str(el.get("id")),
                    )
                )
            except (ValueError, KeyError):
                logger.debug("skipping malformed Overpass element: %r", el)
                continue
        return facilities

    @staticmethod
    def _infer_type(tags: dict) -> FacilityType:
        for key, value in tags.items():
            candidate = f"{key}={value}"
            if candidate in _TAG_TO_FACILITY_TYPE:
                return _TAG_TO_FACILITY_TYPE[candidate]
        return FacilityType.OTHER
