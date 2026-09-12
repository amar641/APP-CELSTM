from __future__ import annotations

from pydantic import BaseModel


class FacilityResponse(BaseModel):
    id: str
    name: str
    facility_type: str
    latitude: float
    longitude: float
