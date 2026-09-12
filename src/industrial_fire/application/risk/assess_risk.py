"""
Use case: derive a `RiskAssessment` from a `ClassificationResult`.

Kept separate from classification so risk *policy* (e.g. "any Potential
Industrial Fire near a facility is CRITICAL") can change independently of
which model produced the label — see configs/model.yaml:evaluation.risk_thresholds.
"""

from __future__ import annotations

from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ClassificationLabel, RiskLevel
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.domain.entities.risk_assessment import RiskAssessment
from industrial_fire.domain.repositories.classification_repository import ClassificationRepository

logger = get_logger(__name__)

_LABEL_BASE_SCORE: dict[ClassificationLabel, float] = {
    ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL: 0.1,
    ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE: 0.85,
    ClassificationLabel.WILDFIRE: 0.7,
    ClassificationLabel.UNKNOWN_NEEDS_REVIEW: 0.5,
}


class AssessRiskUseCase:
    def __init__(self, repository: ClassificationRepository) -> None:
        self._repository = repository

    async def execute(self, classification: ClassificationResult) -> RiskAssessment:
        thresholds = get_settings().model_config_yaml.get("evaluation", {}).get(
            "risk_thresholds", {"low": 0.25, "medium": 0.5, "high": 0.75}
        )
        base = _LABEL_BASE_SCORE.get(classification.label, 0.5)
        # Weight by model confidence so an uncertain classification doesn't
        # produce an overconfident risk score.
        score = round(base * classification.confidence + (1 - classification.confidence) * 0.5, 3)

        if score >= thresholds["high"]:
            level = RiskLevel.CRITICAL if score >= 0.9 else RiskLevel.HIGH
        elif score >= thresholds["medium"]:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        factors = [
            f"label={classification.label.value}",
            f"model_confidence={classification.confidence:.2f}",
            f"model_source={classification.model_source.value}",
        ]

        assessment = RiskAssessment.new(
            thermal_event_id=classification.thermal_event_id,
            classification_result_id=classification.id,
            risk_level=level,
            risk_score=score,
            contributing_factors=factors,
        )
        saved = await self._repository.save_risk_assessment(assessment)
        logger.info(
            "assessed risk thermal_event_id=%s level=%s score=%.2f",
            saved.thermal_event_id,
            saved.risk_level.value,
            saved.risk_score,
        )
        return saved
