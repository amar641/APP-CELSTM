"""
Use case: classify an enriched thermal event.

`ClassificationStrategy` is the swap point between the v1 rule-based
classifier (`rule_based_classifier.RuleBasedClassifier`) and the future
CELSTM model (`ml.inference.predict.CELSTMClassifier`) — the use case,
API routes, and persistence layer never change when the strategy does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.domain.repositories.classification_repository import ClassificationRepository

logger = get_logger(__name__)


class ClassificationStrategy(ABC):
    @abstractmethod
    async def classify(self, enriched: EnrichedThermalEvent) -> ClassificationResult:
        ...


class ClassifyEventUseCase:
    def __init__(self, strategy: ClassificationStrategy, repository: ClassificationRepository) -> None:
        self._strategy = strategy
        self._repository = repository

    async def execute(self, enriched: EnrichedThermalEvent) -> ClassificationResult:
        result = await self._strategy.classify(enriched)
        saved = await self._repository.save_result(result)
        logger.info(
            "classified thermal_event_id=%s as %s (confidence=%.2f, model=%s)",
            saved.thermal_event_id,
            saved.label.value,
            saved.confidence,
            saved.model_source.value,
        )
        return saved
