from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.domain.entities.risk_assessment import RiskAssessment


class ClassificationRepository(ABC):
    @abstractmethod
    async def save_result(self, result: ClassificationResult) -> ClassificationResult:
        ...

    @abstractmethod
    async def save_risk_assessment(self, assessment: RiskAssessment) -> RiskAssessment:
        ...

    @abstractmethod
    async def latest_for_event(self, thermal_event_id: UUID) -> ClassificationResult | None:
        ...

    @abstractmethod
    async def latest_risk_for_event(self, thermal_event_id: UUID) -> RiskAssessment | None:
        ...

    @abstractmethod
    async def exists_for_event(self, thermal_event_id: UUID) -> bool:
        """True once at least one classifier has produced a result for this event — the pipeline's "already processed" gate."""

    @abstractmethod
    async def list_for_event(self, thermal_event_id: UUID) -> list[ClassificationResult]:
        """Every classification result for this event (one per model_source that has run) — most recent first."""

    @abstractmethod
    async def list_risk_for_event(self, thermal_event_id: UUID) -> list[RiskAssessment]:
        """Every risk assessment for this event, one per classification result."""
