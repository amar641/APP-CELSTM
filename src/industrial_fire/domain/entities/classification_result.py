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


# Labels that represent routine/expected heat sources rather than a fire needing attention.
_NORMAL_LABELS = frozenset({ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL})


@dataclass(slots=True)
class ClassificationResult:
    id: UUID
    thermal_event_id: UUID
    label: ClassificationLabel
    confidence: float  # 0..1
    reasoning: str
    model_source: ModelSource
    model_version: str
    is_abnormal: bool = True
    # Offline evaluation metrics of `model_version`, denormalized here for
    # dashboard display — None for rule-based results or an untrained checkpoint.
    model_precision: float | None = None
    model_recall: float | None = None
    model_accuracy: float | None = None
    model_f1_macro: float | None = None
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
        model_precision: float | None = None,
        model_recall: float | None = None,
        model_accuracy: float | None = None,
        model_f1_macro: float | None = None,
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
            is_abnormal=label not in _NORMAL_LABELS,
            model_precision=model_precision,
            model_recall=model_recall,
            model_accuracy=model_accuracy,
            model_f1_macro=model_f1_macro,
        )
