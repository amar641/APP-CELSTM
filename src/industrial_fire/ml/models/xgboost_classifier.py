"""
XGBoost — the second, independent classifier next to CE-LSTM (see
docs/ml/xgboost.md). A gradient-boosted tree ensemble over a flat feature
vector: the same structured features CE-LSTM's structured branch reads
(`ml.features.feature_schema.FEATURE_ORDER`), plus a deterministic
mean-pooled reduction of the satellite vision embedding
(`ml.features.vision_pooling.pool_embedding`). No sequence/rounds — one
row per thermal event, the natural shape for a tree model, and a
genuinely different inductive bias from CE-LSTM's sequential consensus
math (see docs/ml/xgboost.md for why both are kept rather than picking one).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from industrial_fire.ml.features.feature_schema import FEATURE_ORDER, structured_features_to_vector
from industrial_fire.ml.features.vision_pooling import DEFAULT_POOLED_DIM, pool_embedding

VISION_COLUMN_PREFIX = "vision_pooled_"


@dataclass(frozen=True, slots=True)
class XGBoostConfig:
    vision_embedding_dim: int = 512
    vision_pooled_dim: int = DEFAULT_POOLED_DIM
    n_estimators: int = 200
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8

    @property
    def feature_names(self) -> list[str]:
        vision_columns = [f"{VISION_COLUMN_PREFIX}{i}" for i in range(self.vision_pooled_dim)]
        return list(FEATURE_ORDER) + vision_columns

    @classmethod
    def from_yaml_dict(cls, arch: dict) -> XGBoostConfig:
        return cls(
            vision_embedding_dim=arch.get("vision_embedding_dim", 512),
            vision_pooled_dim=arch.get("vision_pooled_dim", DEFAULT_POOLED_DIM),
            n_estimators=arch.get("n_estimators", 200),
            max_depth=arch.get("max_depth", 4),
            learning_rate=arch.get("learning_rate", 0.05),
            subsample=arch.get("subsample", 0.8),
            colsample_bytree=arch.get("colsample_bytree", 0.8),
        )


def build_feature_vector(
    structured_features: dict[str, float],
    vision_embedding: np.ndarray | None,
    config: XGBoostConfig,
) -> np.ndarray:
    structured = structured_features_to_vector(structured_features)
    pooled_vision = pool_embedding(
        vision_embedding, config.vision_embedding_dim, config.vision_pooled_dim
    )
    return np.concatenate([structured, pooled_vision]).astype(np.float32)
