#!/usr/bin/env python
"""
Train a CELSTM checkpoint from labeled thermal events already in Postgres.

    uv run python scripts/training/train_celstm.py

See docs/ml/dataset.md for how labeled sequences are expected to be
sourced — this script assumes `classification_results` already contains
analyst-confirmed (or rule-based bootstrap) labels to train against.

TODO (before this produces a usable checkpoint):
  - Replace `_load_labeled_sequences` with a real query building one
    `LabeledSequence` per confirmed label, walking each event's location
    history via `AssembleFeaturesUseCase`.
  - Add class-weighting/oversampling once real label distribution is known.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ClassificationLabel
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.infrastructure.database.models.classification_result import ClassificationResultModel
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository
from industrial_fire.infrastructure.database.repositories.satellite_image_repository import (
    SqlSatelliteImageRepository,
)
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.repositories.weather_repository import SqlWeatherRepository
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.ml.datasets.thermal_sequence_dataset import LabeledSequence, ThermalSequenceDataset
from industrial_fire.ml.models.celstm import CELSTMConfig
from industrial_fire.ml.training.train import TrainingConfig, train_celstm

logger = get_logger(__name__)


async def _load_labeled_sequences() -> list[LabeledSequence]:
    """
    Bootstrap training set: every thermal event that already has a
    `classification_results` row (rule-based output today; analyst-
    corrected labels later — see docs/ml/dataset.md) becomes one labeled
    sample, its rounds assembled the same way live inference does.
    """
    settings = get_settings()
    session_factory = get_session_factory()
    samples: list[LabeledSequence] = []

    async with session_factory() as session:
        thermal_event_repository = SqlThermalEventRepository(session)
        facility_repository = SqlFacilityRepository(session)
        weather_repository = SqlWeatherRepository(session)
        satellite_image_repository = SqlSatelliteImageRepository(session)
        embedding_reader = QdrantEmbeddingRepository(get_qdrant_client(), settings.qdrant_collection)

        enrichment = SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)
        feature_assembly = AssembleFeaturesUseCase(enrichment, weather_repository, satellite_image_repository, embedding_reader)

        rows = (
            await session.execute(
                select(ClassificationResultModel.thermal_event_id, ClassificationResultModel.label)
            )
        ).all()

        for thermal_event_id, label in rows:
            event = await thermal_event_repository.get(thermal_event_id)
            if event is None:
                continue
            rounds = await feature_assembly.execute_sequence(event)
            samples.append(LabeledSequence(rounds=rounds, label=ClassificationLabel(label)))

    return samples


async def main() -> None:
    settings = get_settings()
    model_cfg = CELSTMConfig.from_yaml_dict(settings.model_config_yaml.get("architecture", {}))
    training_cfg = TrainingConfig.from_yaml_dict(settings.model_config_yaml.get("training", {}))
    sequence_length = settings.model_config_yaml.get("architecture", {}).get("sequence_length", 8)

    samples = await _load_labeled_sequences()
    if not samples:
        logger.error(
            "no labeled training data available — need thermal_events with a classification_results "
            "row (run the API/ingest scripts first so rule-based classifications exist)"
        )
        return

    dataset = ThermalSequenceDataset(
        samples, sequence_length=sequence_length, vision_embedding_dim=model_cfg.vision_embedding_dim
    )
    checkpoint_dir = train_celstm(
        dataset, model_cfg, training_cfg, registry_dir=settings.model_registry_dir, device=settings.model_device
    )
    logger.info("checkpoint written to %s", checkpoint_dir)


if __name__ == "__main__":
    ensure_selector_event_loop()
    asyncio.run(main())
