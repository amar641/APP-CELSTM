from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from industrial_fire.api.dependencies import (
    SettingsDep,
    get_facility_repository,
    get_ingest_facilities_use_case,
)
from industrial_fire.api.schemas.facilities import FacilityResponse
from industrial_fire.application.ingestion.ingest_facilities import IngestFacilitiesUseCase
from industrial_fire.core.exceptions import ExternalServiceError, UseCaseError
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository

router = APIRouter(prefix="/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityResponse])
async def list_facilities(
    settings: SettingsDep,
    repository: Annotated[SqlFacilityRepository, Depends(get_facility_repository)],
) -> list[FacilityResponse]:
    """Reads facilities already ingested into Postgres — see POST /facilities/refresh to (re)fetch from OSM."""
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    facilities = await repository.find_in_bbox(bbox)
    return [
        FacilityResponse(
            id=str(f.id),
            name=f.name,
            facility_type=f.facility_type.value,
            latitude=f.location.latitude,
            longitude=f.location.longitude,
        )
        for f in facilities
    ]


@router.post("/refresh", response_model=list[FacilityResponse])
async def refresh_facilities(
    settings: SettingsDep,
    use_case: Annotated[IngestFacilitiesUseCase, Depends(get_ingest_facilities_use_case)],
) -> list[FacilityResponse]:
    """Re-fetches facilities from OpenStreetMap/Overpass for the configured AOI and upserts them."""
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    try:
        facilities = await use_case.execute(bbox)
    except (ExternalServiceError, UseCaseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        FacilityResponse(
            id=str(f.id),
            name=f.name,
            facility_type=f.facility_type.value,
            latitude=f.location.latitude,
            longitude=f.location.longitude,
        )
        for f in facilities
    ]
