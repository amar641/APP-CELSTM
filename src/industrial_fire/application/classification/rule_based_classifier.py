"""
v1 classification strategy — transparent, threshold-based, ported from the
original MVP's `app/scoring.py`. Every number driving a decision is a real
computed signal (facility distance, persistence count, FRP deviation); no
black-box scoring.

This is a `ClassificationStrategy` implementation so it can run side-by-side
with, and eventually be replaced by, `ml.inference.predict.CELSTMClassifier`
without any change to `ClassifyEventUseCase` or the API layer.
"""

from __future__ import annotations

from industrial_fire.application.classification.classify_event import ClassificationStrategy
from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.core.types import ClassificationLabel, ModelSource
from industrial_fire.domain.entities.classification_result import ClassificationResult

FACILITY_CLOSE_KM = 5.0
PERSISTENCE_HIGH = 4  # detections in window => "persistent" source
FRP_SPIKE_PCT = 60.0  # % above historical avg FRP => "spike"

MODEL_VERSION = "rule-based-v1.0"


class RuleBasedClassifier(ClassificationStrategy):
    async def classify(self, enriched: EnrichedThermalEvent) -> ClassificationResult:
        event = enriched.event
        proximity = enriched.proximity
        persistence = enriched.persistence

        near_facility = proximity.is_within(FACILITY_CLOSE_KM)
        is_persistent = persistence.matched_event_count >= PERSISTENCE_HIGH
        frp_deviation_pct = persistence.frp_deviation_pct(event.frp_mw)
        is_spike = frp_deviation_pct is not None and frp_deviation_pct >= FRP_SPIKE_PCT

        label, confidence, reasoning = self._decide(
            near_facility, is_persistent, is_spike, proximity, persistence, frp_deviation_pct,
            enriched.history_window_days,
        )

        return ClassificationResult.new(
            thermal_event_id=event.id,
            label=label,
            confidence=confidence,
            reasoning=reasoning,
            model_source=ModelSource.RULE_BASED_V1,
            model_version=MODEL_VERSION,
        )

    @staticmethod
    def _decide(
        near_facility: bool,
        is_persistent: bool,
        is_spike: bool,
        proximity,
        persistence,
        frp_deviation_pct: float | None,
        window_days: int,
    ) -> tuple[ClassificationLabel, float, str]:
        fac_name = proximity.facility.name if proximity.facility else "no known facility"
        fac_type = proximity.facility.facility_type.value if proximity.facility else "n/a"
        fac_dist = proximity.distance_km
        count = persistence.matched_event_count

        if near_facility and is_persistent and not is_spike:
            return (
                ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL,
                0.85,
                f"Within {fac_dist}km of {fac_name} ({fac_type}), detected {count}/{window_days} "
                f"recent days with stable FRP — consistent with routine industrial heat.",
            )
        if near_facility and (is_spike or not is_persistent):
            return (
                ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE,
                0.9 if is_spike else 0.7,
                f"Within {fac_dist}km of {fac_name} ({fac_type}) but "
                + (f"FRP is {frp_deviation_pct}% above local historical average — " if is_spike else "")
                + f"low persistence ({count}/{window_days} days) — deviates from expected pattern.",
            )
        if not near_facility and not is_persistent:
            return (
                ClassificationLabel.WILDFIRE,
                0.75,
                f"No known facility within {FACILITY_CLOSE_KM}km, low persistence "
                f"({count}/{window_days} days) — consistent with an active spreading fire.",
            )
        return (
            ClassificationLabel.UNKNOWN_NEEDS_REVIEW,
            0.4,
            "Signals do not clearly match a known pattern — flagged for analyst review.",
        )
