"""
XGBoost inference — implements `ClassificationStrategy`, the same seam
`RuleBasedClassifier` and `CELSTMClassifier` implement (see
application.classification.classify_event.ClassificationStrategy). Runs
side-by-side with CELSTMClassifier in the continuous pipeline — both
produce independent `ClassificationResult` rows for the same event.

Falls back to the rule-based classifier when no trained checkpoint exists
yet, mirroring `ml.inference.predict.CELSTMClassifier`.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np

from industrial_fire.application.classification.classify_event import ClassificationStrategy
from industrial_fire.application.classification.rule_based_classifier import RuleBasedClassifier
from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ClassificationLabel, ModelSource
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.ml.models.xgboost_classifier import XGBoostConfig, build_feature_vector

logger = get_logger(__name__)

_INDEX_TO_LABEL: dict[int, ClassificationLabel] = {
    0: ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL,
    1: ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE,
    2: ClassificationLabel.WILDFIRE,
    3: ClassificationLabel.UNKNOWN_NEEDS_REVIEW,
}


def _latest_checkpoint(registry_dir: str) -> Path | None:
    root = Path(registry_dir)
    if not root.exists():
        return None
    candidates = sorted((p for p in root.iterdir() if (p / "model.joblib").exists()), reverse=True)
    return candidates[0] if candidates else None


def _load_metrics(checkpoint_dir: Path) -> dict:
    metrics_path = checkpoint_dir / "metrics.json"
    if not metrics_path.exists():
        return {}
    return json.loads(metrics_path.read_text())


class XGBoostClassifier(ClassificationStrategy):
    def __init__(
        self,
        model_config: XGBoostConfig,
        registry_dir: str,
        feature_assembly: AssembleFeaturesUseCase,
        fallback: RuleBasedClassifier | None = None,
    ) -> None:
        self._model_config = model_config
        self._feature_assembly = feature_assembly
        self._fallback = fallback or RuleBasedClassifier()

        checkpoint_dir = _latest_checkpoint(registry_dir)
        self._model = None
        self._model_version = "none"
        self._metrics: dict = {}
        if checkpoint_dir is not None:
            self._model = joblib.load(checkpoint_dir / "model.joblib")
            self._model_version = checkpoint_dir.name
            self._metrics = _load_metrics(checkpoint_dir)
        else:
            logger.warning(
                "no XGBoost checkpoint found in %s — falling back to rule-based classifier",
                registry_dir,
            )

    async def classify(self, enriched: EnrichedThermalEvent) -> ClassificationResult:
        if self._model is None:
            return await self._fallback.classify(enriched)

        try:
            bundle = await self._feature_assembly.execute(enriched.event)
        except Exception as exc:  # noqa: BLE001
            logger.error("feature assembly failed, falling back to rule-based: %s", exc)
            return await self._fallback.classify(enriched)

        vector = build_feature_vector(
            bundle.structured_features, bundle.vision_embedding, self._model_config
        )
        probs = self._model.predict_proba(vector.reshape(1, -1))[0]
        index = int(np.argmax(probs))
        label = _INDEX_TO_LABEL[index]
        confidence = float(probs[index])

        reasoning = (
            f"XGBoost ({self._model_version}): predicted class probabilities "
            f"{ {lbl.value: round(float(probs[i]), 3) for i, lbl in _INDEX_TO_LABEL.items()} }."
        )
        return ClassificationResult.new(
            thermal_event_id=enriched.event.id,
            label=label,
            confidence=confidence,
            reasoning=reasoning,
            model_source=ModelSource.XGBOOST_V1,
            model_version=self._model_version,
            model_precision=self._metrics.get("precision_macro"),
            model_recall=self._metrics.get("recall_macro"),
            model_accuracy=self._metrics.get("accuracy"),
            model_f1_macro=self._metrics.get("f1_macro"),
        )
