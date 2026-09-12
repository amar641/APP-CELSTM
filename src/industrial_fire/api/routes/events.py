"""
Classified thermal events — the primary feed for the GIS dashboard.

Mirrors the original MVP's `/events` endpoint, but each step (ingest,
enrich, classify, assess risk) now runs through its own use case instead
of one monolithic function.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from industrial_fire.api.dependencies import (
    SettingsDep,
    get_assess_risk_use_case,
    get_classify_use_case,
    get_ingest_thermal_events_use_case,
    get_spatial_enrichment_use_case,
)
from industrial_fire.api.schemas.events import ClassifiedEventResponse
from industrial_fire.application.classification.classify_event import ClassifyEventUseCase
from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.application.ingestion.ingest_thermal_events import IngestThermalEventsUseCase
from industrial_fire.application.risk.assess_risk import AssessRiskUseCase
from industrial_fire.core.exceptions import ExternalServiceError, UseCaseError
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

router = APIRouter(prefix="/events", tags=["events"])

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@router.get("", response_model=list[ClassifiedEventResponse])
async def list_events(
    settings: SettingsDep,
    ingest: Annotated[IngestThermalEventsUseCase, Depends(get_ingest_thermal_events_use_case)],
    enrich: Annotated[SpatialEnrichmentUseCase, Depends(get_spatial_enrichment_use_case)],
    classify: Annotated[ClassifyEventUseCase, Depends(get_classify_use_case)],
    assess_risk: Annotated[AssessRiskUseCase, Depends(get_assess_risk_use_case)],
    days_back: Annotated[
        int, Query(ge=0, le=10, description="0 = today (default); FIRMS free tier max lookback is 10 days")
    ] = 0,
) -> list[ClassifiedEventResponse]:
    """Pulls FIRMS detections for the configured AOI on the given day (`days_back` days before today), enriches, classifies, and scores risk for each."""
    bbox = BoundingBox.from_csv(settings.aoi_bbox)

    try:
        events = await ingest.execute(bbox, days_back=days_back)
    except (ExternalServiceError, UseCaseError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    responses: list[ClassifiedEventResponse] = []
    for event in events:
        enriched = await enrich.execute(event)
        classification = await classify.execute(enriched)
        risk = await assess_risk.execute(classification)

        responses.append(
            ClassifiedEventResponse(
                id=str(event.id),
                latitude=event.location.latitude,
                longitude=event.location.longitude,
                frp_mw=event.frp_mw,
                confidence=event.confidence,
                acquired_at=event.acquired_at,
                nearest_facility=enriched.proximity.facility.name if enriched.proximity.facility else None,
                facility_type=(
                    enriched.proximity.facility.facility_type.value if enriched.proximity.facility else None
                ),
                distance_to_facility_km=enriched.proximity.distance_km,
                persistence_count=enriched.persistence.matched_event_count,
                frp_deviation_pct=enriched.persistence.frp_deviation_pct(event.frp_mw),
                classification=classification.label.value,
                classification_confidence=classification.confidence,
                model_source=classification.model_source.value,
                reasoning=classification.reasoning,
                risk_level=risk.risk_level.value,
                risk_score=risk.risk_score,
            )
        )

    responses.sort(key=lambda r: _RISK_ORDER.get(r.risk_level, 4))
    return responses
