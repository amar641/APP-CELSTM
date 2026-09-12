"""
CE-LSTM inference — implements `ClassificationStrategy` so it's a drop-in
replacement for `RuleBasedClassifier` at the `ClassifyEventUseCase` seam.

For a hotspot, pulls every satellite-image round assembled for it —
structured features from Postgres, embedding vectors from Qdrant, via
`AssembleFeaturesUseCase.execute_sequence` — and runs them through
`ml.models.celstm.CELSTM`. The result is a `ClassificationResult` exactly
like the rule-based strategy produces, so `ClassifyEventUseCase` persists
it to Postgres (`classification_results`) the same way regardless of
which strategy ran — see docs/ml/celstm.md.

Falls back to the rule-based classifier when no trained checkpoint exists
in `MODEL_REGISTRY_DIR` (fresh installs, before any training run) so the
API never breaks waiting on a model that hasn't been trained yet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from industrial_fire.application.classification.classify_event import ClassificationStrategy
from industrial_fire.application.classification.rule_based_classifier import RuleBasedClassifier
from industrial_fire.application.enrichment.spatial_enrichment import EnrichedThermalEvent
from industrial_fire.application.feature_assembly.assemble_features import (
    AssembleFeaturesUseCase,
    FeatureBundle,
)
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ClassificationLabel, ModelSource
from industrial_fire.domain.entities.classification_result import ClassificationResult
from industrial_fire.ml.features.source_signals import NUM_STRUCTURED_SOURCES, structured_signals
from industrial_fire.ml.models.celstm import CELSTM, CELSTMConfig

logger = get_logger(__name__)

_INDEX_TO_LABEL: dict[int, ClassificationLabel] = {
    0: ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL,
    1: ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE,
    2: ClassificationLabel.WILDFIRE,
    3: ClassificationLabel.UNKNOWN_NEEDS_REVIEW,
}

_MAX_ROUNDS = 8  # matches configs/model.yaml:architecture defaults for a trained checkpoint


def _latest_checkpoint(registry_dir: str) -> Path | None:
    root = Path(registry_dir)
    if not root.exists():
        return None
    candidates = sorted((p for p in root.iterdir() if (p / "model.pt").exists()), reverse=True)
    return candidates[0] if candidates else None


class CELSTMClassifier(ClassificationStrategy):
    def __init__(
        self,
        model_config: CELSTMConfig,
        registry_dir: str,
        feature_assembly: AssembleFeaturesUseCase,
        fallback: RuleBasedClassifier | None = None,
        device: str = "cpu",
    ) -> None:
        self._model_config = model_config
        self._feature_assembly = feature_assembly
        self._fallback = fallback or RuleBasedClassifier()
        self._device = torch.device(device)

        checkpoint_dir = _latest_checkpoint(registry_dir)
        self._model: CELSTM | None = None
        self._model_version = "none"
        if checkpoint_dir is not None:
            self._model = CELSTM(model_config).to(self._device)
            self._model.load_state_dict(torch.load(checkpoint_dir / "model.pt", map_location=self._device))
            self._model.eval()
            self._model_version = checkpoint_dir.name
        else:
            logger.warning(
                "no CELSTM checkpoint found in %s — falling back to rule-based classifier", registry_dir
            )

    async def classify(self, enriched: EnrichedThermalEvent) -> ClassificationResult:
        if self._model is None:
            return await self._fallback.classify(enriched)

        try:
            rounds = await self._feature_assembly.execute_sequence(enriched.event)
        except Exception as exc:  # noqa: BLE001
            logger.error("feature assembly failed, falling back to rule-based: %s", exc)
            return await self._fallback.classify(enriched)

        label, confidence, diagnostics = self._predict(rounds)
        reasoning = (
            f"CE-LSTM ({self._model_version}): {len(rounds)} round(s) of evidence; "
            f"final-round consensus={diagnostics['phi'][-1]:.2f}, "
            f"momentum={diagnostics['mu'][-1]:.2f}, entropy={diagnostics['eta'][-1]:.2f}, "
            f"update_scale={diagnostics['scale'][-1]:.2f} "
            f"(γ={diagnostics['gamma']:.2f}, ρ={diagnostics['rho']:.2f})."
        )
        return ClassificationResult.new(
            thermal_event_id=enriched.event.id,
            label=label,
            confidence=confidence,
            reasoning=reasoning,
            model_source=ModelSource.CELSTM_V1,
            model_version=self._model_version,
        )

    @torch.no_grad()
    def _predict(self, rounds: list[FeatureBundle]) -> tuple[ClassificationLabel, float, dict]:
        assert self._model is not None
        T = min(len(rounds), _MAX_ROUNDS)
        vision_dim = self._model_config.vision_embedding_dim

        decisions = np.zeros((1, T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        intensities = np.zeros((1, T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        availability = np.zeros((1, T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        vision = np.zeros((1, T, vision_dim), dtype=np.float32)
        vision_available = np.zeros((1, T), dtype=np.float32)

        for i, bundle in enumerate(rounds[-T:]):
            d, e, a = structured_signals(bundle.structured_features)
            decisions[0, i], intensities[0, i], availability[0, i] = d, e, a
            if bundle.vision_embedding is not None:
                vision[0, i] = bundle.vision_embedding
                vision_available[0, i] = 1.0

        logits, diagnostics = self._model(
            torch.from_numpy(decisions).to(self._device),
            torch.from_numpy(intensities).to(self._device),
            torch.from_numpy(availability).to(self._device),
            torch.from_numpy(vision).to(self._device),
            torch.from_numpy(vision_available).to(self._device),
        )
        probs = torch.softmax(logits, dim=-1).squeeze(0)
        index = int(probs.argmax().item())

        flat_diagnostics = {
            "phi": diagnostics["phi"].squeeze(0).cpu().tolist(),
            "mu": diagnostics["mu"].squeeze(0).cpu().tolist(),
            "eta": diagnostics["eta"].squeeze(0).cpu().tolist(),
            "scale": diagnostics["scale"].squeeze(0).cpu().tolist(),
            "gamma": float(diagnostics["gamma"]),
            "rho": float(diagnostics["rho"]),
        }
        return _INDEX_TO_LABEL[index], float(probs[index].item()), flat_diagnostics
