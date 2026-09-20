#!/usr/bin/env python
"""
Train an XGBoost checkpoint from labeled thermal events already in Postgres.

    uv run python scripts/training/train_xgboost.py

Same bootstrap-label source as `train_celstm.py` (every thermal event that
already has a `classification_results` row) — see docs/ml/dataset.md. Unlike
CELSTM, XGBoost consumes one flat feature vector per event (no rounds), via
`AssembleFeaturesUseCase.execute` + `ml.models.xgboost_classifier.build_feature_vector`.
"""

from __future__ import annotations

import asyncio

import numpy as np
from sqlalchemy import select

from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.core.config import get_settings
from industrial_fire.core.logging import get_logger
from industrial_fire.core.types import ClassificationLabel
from industrial_fire.core.windows_compat import ensure_selector_event_loop
from industrial_fire.infrastructure.database.models.classification_result import (
    ClassificationResultModel,
)
from industrial_fire.infrastructure.database.repositories.facility_repository import (
    SqlFacilityRepository,
)
from industrial_fire.infrastructure.database.repositories.satellite_image_repository import (
    SqlSatelliteImageRepository,
)
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.repositories.weather_repository import (
    SqlWeatherRepository,
)
from industrial_fire.infrastructure.database.session import get_session_factory
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.ml.models.xgboost_classifier import XGBoostConfig, build_feature_vector
from industrial_fire.ml.training.train_xgboost import XGBoostTrainingConfig, train_xgboost

logger = get_logger(__name__)

_LABEL_TO_INDEX: dict[ClassificationLabel, int] = {
    ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL: 0,
    ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE: 1,
    ClassificationLabel.WILDFIRE: 2,
    ClassificationLabel.UNKNOWN_NEEDS_REVIEW: 3,
}


async def _load_labeled_examples(model_config: XGBoostConfig) -> tuple[np.ndarray, np.ndarray]:
    settings = get_settings()
    session_factory = get_session_factory()
    rows_x: list[np.ndarray] = []
    rows_y: list[int] = []

    async with session_factory() as session:
        thermal_event_repository = SqlThermalEventRepository(session)
        facility_repository = SqlFacilityRepository(session)
        weather_repository = SqlWeatherRepository(session)
        satellite_image_repository = SqlSatelliteImageRepository(session)
        embedding_reader = QdrantEmbeddingRepository(
            get_qdrant_client(), settings.qdrant_collection
        )

        enrichment = SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)
        feature_assembly = AssembleFeaturesUseCase(
            enrichment, weather_repository, satellite_image_repository, embedding_reader
        )

        labeled = (
            await session.execute(
                select(ClassificationResultModel.thermal_event_id, ClassificationResultModel.label)
            )
        ).all()

        for thermal_event_id, label in labeled:
            event = await thermal_event_repository.get(thermal_event_id)
            if event is None:
                continue
            bundle = await feature_assembly.execute(event)
            vector = build_feature_vector(
                bundle.structured_features, bundle.vision_embedding, model_config
            )
            rows_x.append(vector)
            rows_y.append(_LABEL_TO_INDEX[ClassificationLabel(label)])

    x = np.stack(rows_x) if rows_x else np.empty((0, len(model_config.feature_names)))
    return x, np.array(rows_y)


async def main() -> None:
    settings = get_settings()
    xgb_cfg = settings.model_config_yaml.get("xgboost", {})
    model_cfg = XGBoostConfig.from_yaml_dict(xgb_cfg.get("architecture", {}))
    training_cfg = XGBoostTrainingConfig.from_yaml_dict(xgb_cfg.get("training", {}))

    features, labels = await _load_labeled_examples(model_cfg)
    if len(labels) == 0:
        logger.error(
            "no labeled training data available — need thermal_events with a "
            "classification_results row (run the API so the continuous pipeline has "
            "classified some events first)"
        )
        return

    checkpoint_dir = train_xgboost(
        features, labels, model_cfg, training_cfg, registry_dir=settings.model_registry_dir
    )
    logger.info("checkpoint written to %s", checkpoint_dir)


if __name__ == "__main__":
    ensure_selector_event_loop()
    asyncio.run(main())
