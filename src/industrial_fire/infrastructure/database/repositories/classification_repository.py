"""Concrete `ClassificationRepository` backed by Postgres."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.core.types import ClassificationLabel, ModelSource, RiskLevel
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.domain.entities.risk_assessment import RiskAssessment
from industrial_fire.domain.repositories.classification_repository import ClassificationRepository
from industrial_fire.infrastructure.database.models.classification_result import (
    ClassificationResultModel,
    RiskAssessmentModel,
)


def _result_to_entity(row: ClassificationResultModel) -> ClassificationResult:
    return ClassificationResult(
        id=row.id,
        thermal_event_id=row.thermal_event_id,
        label=ClassificationLabel(row.label),
        confidence=row.confidence,
        reasoning=row.reasoning,
        model_source=ModelSource(row.model_source),
        model_version=row.model_version,
        classified_at=row.classified_at,
    )


def _risk_to_entity(row: RiskAssessmentModel) -> RiskAssessment:
    return RiskAssessment(
        id=row.id,
        thermal_event_id=row.thermal_event_id,
        classification_result_id=row.classification_result_id,
        risk_level=RiskLevel(row.risk_level),
        risk_score=row.risk_score,
        contributing_factors=list(row.contributing_factors or []),
        assessed_at=row.assessed_at,
    )


class SqlClassificationRepository(ClassificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_result(self, result: ClassificationResult) -> ClassificationResult:
        row = ClassificationResultModel(
            id=result.id,
            thermal_event_id=result.thermal_event_id,
            label=result.label.value,
            confidence=result.confidence,
            reasoning=result.reasoning,
            model_source=result.model_source.value,
            model_version=result.model_version,
            classified_at=result.classified_at,
        )
        self._session.add(row)
        await self._session.flush()
        return result

    async def save_risk_assessment(self, assessment: RiskAssessment) -> RiskAssessment:
        row = RiskAssessmentModel(
            id=assessment.id,
            thermal_event_id=assessment.thermal_event_id,
            classification_result_id=assessment.classification_result_id,
            risk_level=assessment.risk_level.value,
            risk_score=assessment.risk_score,
            contributing_factors=assessment.contributing_factors,
            assessed_at=assessment.assessed_at,
        )
        self._session.add(row)
        await self._session.flush()
        return assessment

    async def latest_for_event(self, thermal_event_id: UUID) -> ClassificationResult | None:
        stmt = (
            select(ClassificationResultModel)
            .where(ClassificationResultModel.thermal_event_id == thermal_event_id)
            .order_by(ClassificationResultModel.classified_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _result_to_entity(row) if row else None

    async def latest_risk_for_event(self, thermal_event_id: UUID) -> RiskAssessment | None:
        stmt = (
            select(RiskAssessmentModel)
            .where(RiskAssessmentModel.thermal_event_id == thermal_event_id)
            .order_by(RiskAssessmentModel.assessed_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _risk_to_entity(row) if row else None
