from __future__ import annotations

from pydantic import BaseModel


class AoiResponse(BaseModel):
    """The configured area of interest as a GeoJSON Polygon feature, for the dashboard's boundary overlay."""

    type: str = "Feature"
    geometry: dict
    properties: dict = {}
