"""API response schemas for classified thermal events — the GIS dashboard's primary data source."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ClassificationSummary(BaseModel):
    """One classifier's opinion on an event — the dashboard shows one of these per model (CELSTM, XGBoost, or the rule-based fallback)."""

    model_source: str
    model_version: str
    label: str
    confidence: float
    is_abnormal: bool
    reasoning: str
    model_precision: float | None = None
    model_recall: float | None = None
    model_accuracy: float | None = None
    model_f1_macro: float | None = None
    risk_level: str | None = None
    risk_score: float | None = None
    contributing_factors: list[str] = []


class ClassifiedEventResponse(BaseModel):
    id: str
    latitude: float
    longitude: float
    brightness_kelvin: float
    frp_mw: float
    confidence: str
    acquired_at: datetime

    nearest_facility: str | None = None
    facility_type: str | None = None
    distance_to_facility_km: float | None = None
    persistence_count: int
    frp_deviation_pct: float | None = None

    classifications: list[ClassificationSummary]

    # Derived across `classifications` (max risk_score) — for map color/sort,
    # not a separate model output.
    risk_level: str
    risk_score: float


class SatelliteImageSummary(BaseModel):
    id: str
    stac_item_id: str
    collection: str
    acquired_at: datetime
    cloud_cover_pct: float | None = None
    has_embedding: bool


class EventDetailResponse(ClassifiedEventResponse):
    persistence_window_days: int
    satellite_images: list[SatelliteImageSummary]
