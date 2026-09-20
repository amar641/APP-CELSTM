"""
Classified thermal events — the primary feed for the GIS dashboard.

Pure DB reads: the continuous background pipeline (`application.pipeline.
continuous_pipeline.ContinuousPipeline`, started from `api/main.py`'s
lifespan) is what ingests/enriches/classifies/scores risk now — these
routes just read what it has already written to Postgres, so they stay
fast enough for the dashboard to poll.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from industrial_fire.api.dependencies import (
    SettingsDep,
    get_classification_repository,
    get_facility_repository,
    get_satellite_image_repository,
    get_thermal_event_repository,
)
from industrial_fire.api.schemas.events import (
    ClassificationSummary,
    ClassifiedEventResponse,
    EventDetailResponse,
    SatelliteImageSummary,
)
from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.core.exceptions import EntityNotFoundError
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.domain.entities.risk_assessment import RiskAssessment
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.repositories.classification_repository import ClassificationRepository
from industrial_fire.domain.repositories.facility_repository import FacilityRepository
from industrial_fire.domain.repositories.satellite_image_repository import SatelliteImageRepository
from industrial_fire.domain.repositories.thermal_event_repository import ThermalEventRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.domain.value_objects.time_range import TimeRange

router = APIRouter(prefix="/events", tags=["events"])

_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _classification_summaries(
    results: list[ClassificationResult], risks: list[RiskAssessment]
) -> list[ClassificationSummary]:
    risk_by_result_id = {r.classification_result_id: r for r in risks}
    summaries = []
    for result in results:
        risk = risk_by_result_id.get(result.id)
        summaries.append(
            ClassificationSummary(
                model_source=result.model_source.value,
                model_version=result.model_version,
                label=result.label.value,
                confidence=result.confidence,
                is_abnormal=result.is_abnormal,
                reasoning=result.reasoning,
                model_precision=result.model_precision,
                model_recall=result.model_recall,
                model_accuracy=result.model_accuracy,
                model_f1_macro=result.model_f1_macro,
                risk_level=risk.risk_level.value if risk else None,
                risk_score=risk.risk_score if risk else None,
                contributing_factors=risk.contributing_factors if risk else [],
            )
        )
    return summaries


def _overall_risk(classifications: list[ClassificationSummary]) -> tuple[str, float]:
    scored = [c for c in classifications if c.risk_score is not None]
    if not scored:
        return "LOW", 0.0
    best = max(scored, key=lambda c: c.risk_score)
    return best.risk_level or "LOW", best.risk_score or 0.0


async def _build_event_response(
    event: ThermalEvent,
    enrichment: SpatialEnrichmentUseCase,
    classification_repository: ClassificationRepository,
) -> ClassifiedEventResponse:
    enriched = await enrichment.execute(event)
    results = await classification_repository.list_for_event(event.id)
    risks = await classification_repository.list_risk_for_event(event.id)
    classifications = _classification_summaries(results, risks)
    risk_level, risk_score = _overall_risk(classifications)

    return ClassifiedEventResponse(
        id=str(event.id),
        latitude=event.location.latitude,
        longitude=event.location.longitude,
        brightness_kelvin=event.brightness_kelvin,
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
        classifications=classifications,
        risk_level=risk_level,
        risk_score=risk_score,
    )


@router.get("", response_model=list[ClassifiedEventResponse])
async def list_events(
    settings: SettingsDep,
    thermal_event_repository: Annotated[
        ThermalEventRepository, Depends(get_thermal_event_repository)
    ],
    facility_repository: Annotated[FacilityRepository, Depends(get_facility_repository)],
    classification_repository: Annotated[
        ClassificationRepository, Depends(get_classification_repository)
    ],
    days_back: Annotated[
        int, Query(ge=0, le=30, description="How many days of already-ingested history to include")
    ] = 1,
) -> list[ClassifiedEventResponse]:
    """Events already ingested/classified by the continuous pipeline, sorted highest-risk first."""
    bbox = BoundingBox.from_csv(settings.aoi_bbox)
    time_range = TimeRange.last_n_days(days_back)
    events = await thermal_event_repository.find_in_bbox(bbox, time_range)

    enrichment = SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)
    responses = [
        await _build_event_response(event, enrichment, classification_repository)
        for event in events
    ]
    responses.sort(key=lambda r: _RISK_ORDER.get(r.risk_level, 4))
    return responses


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event(
    event_id: UUID,
    thermal_event_repository: Annotated[
        ThermalEventRepository, Depends(get_thermal_event_repository)
    ],
    facility_repository: Annotated[FacilityRepository, Depends(get_facility_repository)],
    classification_repository: Annotated[
        ClassificationRepository, Depends(get_classification_repository)
    ],
    satellite_image_repository: Annotated[
        SatelliteImageRepository, Depends(get_satellite_image_repository)
    ],
) -> EventDetailResponse:
    """Detail for the click panel — fire, satellite evidence, history, both classifiers' output."""
    event = await thermal_event_repository.get(event_id)
    if event is None:
        raise EntityNotFoundError(f"thermal event {event_id} not found")

    enrichment = SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)
    base = await _build_event_response(event, enrichment, classification_repository)
    enriched = await enrichment.execute(event)
    images = await satellite_image_repository.find_for_thermal_event(event_id)

    return EventDetailResponse(
        **base.model_dump(),
        persistence_window_days=enriched.history_window_days,
        satellite_images=[
            SatelliteImageSummary(
                id=str(img.id),
                stac_item_id=img.stac_item_id,
                collection=img.collection,
                acquired_at=img.acquired_at,
                cloud_cover_pct=img.cloud_cover_pct,
                has_embedding=img.has_embedding,
            )
            for img in images
        ],
    )
