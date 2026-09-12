"""API response schemas for classified thermal events — the GIS dashboard's primary data source."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ClassifiedEventResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    frp_mw: float
    confidence: str
    acquired_at: datetime

    nearest_facility: str | None = None
    facility_type: str | None = None
    distance_to_facility_km: float | None = None
    persistence_count: int
    frp_deviation_pct: float | None = None

    classification: str
    classification_confidence: float
    model_source: str
    reasoning: str

    risk_level: str
    risk_score: float
