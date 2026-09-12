"""Risk scoring derived from a `ClassificationResult` — separate entity so risk policy can evolve independently of the classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from industrial_fire.core.types import RiskLevel


@dataclass(slots=True)
class RiskAssessment:
    id: UUID
    thermal_event_id: UUID
    classification_result_id: UUID
    risk_level: RiskLevel
    risk_score: float  # 0..1, continuous score behind the discrete level
    contributing_factors: list[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def new(
        cls,
        *,
        thermal_event_id: UUID,
        classification_result_id: UUID,
        risk_level: RiskLevel,
        risk_score: float,
        contributing_factors: list[str] | None = None,
    ) -> RiskAssessment:
        if not 0.0 <= risk_score <= 1.0:
            raise ValueError(f"risk_score out of range: {risk_score}")
        return cls(
            id=uuid4(),
            thermal_event_id=thermal_event_id,
            classification_result_id=classification_result_id,
            risk_level=risk_level,
            risk_score=risk_score,
            contributing_factors=contributing_factors or [],
        )
