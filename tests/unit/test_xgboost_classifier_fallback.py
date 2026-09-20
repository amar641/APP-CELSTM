"""
When no XGBoost checkpoint exists yet (fresh install, before
scripts/training/train_xgboost.py has run), XGBoostClassifier must fall
back to the rule-based classifier rather than error — mirrors the same
contract `ml.inference.predict.CELSTMClassifier` implements.
"""

from datetime import datetime

import pytest

from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.core.types import ClassificationLabel, ModelSource, ThermalSource
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.services.persistence_service import PersistenceResult
from industrial_fire.domain.services.proximity_service import ProximityResult
from industrial_fire.domain.value_objects.coordinates import Coordinates
from industrial_fire.ml.inference.predict_xgboost import XGBoostClassifier
from industrial_fire.ml.models.xgboost_classifier import XGBoostConfig


def _enriched() -> EnrichedThermalEvent:
    event = ThermalEvent.new(
        location=Coordinates(latitude=22.47, longitude=70.05),
        brightness_kelvin=330.0,
        frp_mw=100.0,
        confidence="high",
        acquired_at=datetime(2026, 1, 1, 10, 0),
        source=ThermalSource.VIIRS_SNPP_NRT,
    )
    return EnrichedThermalEvent(
        event=event,
        proximity=ProximityResult(facility=None, distance_km=None),
        persistence=PersistenceResult(matched_event_count=0, average_frp_mw=0.0),
        history_window_days=7,
    )


@pytest.mark.asyncio
async def test_falls_back_to_rule_based_when_no_checkpoint(tmp_path):
    classifier = XGBoostClassifier(
        model_config=XGBoostConfig(),
        registry_dir=str(tmp_path / "does-not-exist"),
        feature_assembly=None,  # unused — classify() short-circuits to fallback when model is None
    )
    result = await classifier.classify(_enriched())

    assert result.model_source == ModelSource.RULE_BASED_V1
    assert result.label == ClassificationLabel.WILDFIRE
