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
