"""
The output of classifying a thermal event.

`model_source` and `model_version` give every classification data
provenance — which strategy (rule-based v1 or a specific CELSTM checkpoint)
produced it — so results stay comparable/reproducible as the model evolves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from industrial_fire.core.types import ClassificationLabel, ModelSource


@dataclass(slots=True)
class ClassificationResult:
    id: UUID
    thermal_event_id: UUID
    label: ClassificationLabel
    confidence: float  # 0..1
    reasoning: str
    model_source: ModelSource
    model_version: str
    classified_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def new(
        cls,
        *,
        thermal_event_id: UUID,
        label: ClassificationLabel,
        confidence: float,
        reasoning: str,
        model_source: ModelSource,
        model_version: str,
    ) -> ClassificationResult:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"confidence out of range: {confidence}")
        return cls(
            id=uuid4(),
            thermal_event_id=thermal_event_id,
            label=label,
            confidence=confidence,
            reasoning=reasoning,
            model_source=model_source,
            model_version=model_version,
        )
