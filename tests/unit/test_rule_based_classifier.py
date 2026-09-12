from datetime import datetime

import pytest

from industrial_fire.application.classification.rule_based_classifier import RuleBasedClassifier
from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.core.types import ClassificationLabel, FacilityType, ThermalSource
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.services.persistence_service import PersistenceResult
from industrial_fire.domain.services.proximity_service import ProximityResult
from industrial_fire.domain.value_objects.coordinates import Coordinates


def _event(frp_mw: float = 5.0) -> ThermalEvent:
    return ThermalEvent.new(
        location=Coordinates(latitude=22.47, longitude=70.05),
        brightness_kelvin=330.0,
        frp_mw=frp_mw,
        confidence="high",
        acquired_at=datetime(2026, 1, 1, 10, 0),
        source=ThermalSource.VIIRS_SNPP_NRT,
    )


def _facility() -> Facility:
    return Facility.new(
        name="Test Refinery",
        facility_type=FacilityType.REFINERY,
        location=Coordinates(latitude=22.47, longitude=70.05),
    )


@pytest.mark.asyncio
async def test_close_persistent_stable_is_normal_industrial():
    enriched = EnrichedThermalEvent(
        event=_event(frp_mw=10.0),
        proximity=ProximityResult(facility=_facility(), distance_km=1.0),
        persistence=PersistenceResult(matched_event_count=5, average_frp_mw=10.0),
        history_window_days=7,
    )
    result = await RuleBasedClassifier().classify(enriched)
    assert result.label == ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL


@pytest.mark.asyncio
async def test_close_frp_spike_is_potential_industrial_fire():
    enriched = EnrichedThermalEvent(
        event=_event(frp_mw=100.0),
        proximity=ProximityResult(facility=_facility(), distance_km=1.0),
        persistence=PersistenceResult(matched_event_count=5, average_frp_mw=10.0),
        history_window_days=7,
    )
    result = await RuleBasedClassifier().classify(enriched)
    assert result.label == ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE


@pytest.mark.asyncio
async def test_far_low_persistence_is_wildfire():
    enriched = EnrichedThermalEvent(
        event=_event(frp_mw=20.0),
        proximity=ProximityResult(facility=None, distance_km=None),
        persistence=PersistenceResult(matched_event_count=0, average_frp_mw=0.0),
        history_window_days=7,
    )
    result = await RuleBasedClassifier().classify(enriched)
    assert result.label == ClassificationLabel.WILDFIRE


@pytest.mark.asyncio
async def test_far_persistent_is_unknown():
    enriched = EnrichedThermalEvent(
        event=_event(frp_mw=20.0),
        proximity=ProximityResult(facility=None, distance_km=None),
        persistence=PersistenceResult(matched_event_count=5, average_frp_mw=20.0),
        history_window_days=7,
    )
    result = await RuleBasedClassifier().classify(enriched)
    assert result.label == ClassificationLabel.UNKNOWN_NEEDS_REVIEW
