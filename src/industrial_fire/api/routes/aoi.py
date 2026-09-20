from __future__ import annotations

from fastapi import APIRouter

from industrial_fire.api.dependencies import SettingsDep
from industrial_fire.api.schemas.aoi import AoiResponse

router = APIRouter(prefix="/aoi", tags=["aoi"])


@router.get("", response_model=AoiResponse)
async def get_aoi(settings: SettingsDep) -> AoiResponse:
    """The configured AOI as GeoJSON for the boundary overlay. No DB — derived from AOI_BBOX."""
    west, south, east, north = settings.aoi_bbox_tuple
    return AoiResponse(
        geometry={
            "type": "Polygon",
            "coordinates": [
                [[west, south], [east, south], [east, north], [west, north], [west, south]]
            ],
        },
        properties={"bbox": [west, south, east, north]},
    )
