"""
XGBoost training. Invoked via `scripts/training/train_xgboost.py`, never
imported by the API — training is an offline job, same as
`ml.training.train.train_celstm`. Every run writes a versioned checkpoint
(`model.joblib` + `metrics.json`) under `MODEL_REGISTRY_DIR`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier

from industrial_fire.core.logging import get_logger
from industrial_fire.ml.evaluation.metrics import evaluate_sklearn
from industrial_fire.ml.models.xgboost_classifier import XGBoostConfig

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class XGBoostTrainingConfig:
    val_split: float = 0.2
    seed: int = 42

    @classmethod
    def from_yaml_dict(cls, training: dict) -> XGBoostTrainingConfig:
        return cls(val_split=training.get("val_split", 0.2), seed=training.get("seed", 42))


def train_xgboost(
    features: np.ndarray,
    labels: np.ndarray,
    model_config: XGBoostConfig,
    training_config: XGBoostTrainingConfig,
    registry_dir: str,
) -> Path:
    x_train, x_val, y_train, y_val = train_test_split(
        features,
        labels,
        test_size=training_config.val_split,
        random_state=training_config.seed,
        stratify=labels if len(set(labels.tolist())) > 1 else None,
    )
    # Class-weighted, not resampled — gas-flare/normal-industrial will vastly
    # outnumber confirmed fires (see docs/ml/dataset.md); weighting keeps every
    # row without needing to duplicate/synthesize rare-class examples.
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

    model = XGBClassifier(
        n_estimators=model_config.n_estimators,
        max_depth=model_config.max_depth,
        learning_rate=model_config.learning_rate,
        subsample=model_config.subsample,
        colsample_bytree=model_config.colsample_bytree,
        objective="multi:softprob",
        num_class=4,
        random_state=training_config.seed,
        eval_metric="mlogloss",
    )
    model.fit(x_train, y_train, sample_weight=sample_weight)

    y_pred = model.predict(x_val)
    metrics = evaluate_sklearn(y_val.tolist(), y_pred.tolist())
    logger.info(
        "xgboost val_accuracy=%.4f val_f1_macro=%.4f", metrics["accuracy"], metrics["f1_macro"]
    )

    version = datetime.utcnow().strftime("xgboost-%Y%m%d%H%M%S")
    checkpoint_dir = Path(registry_dir) / version
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, checkpoint_dir / "model.joblib")
    (checkpoint_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    logger.info("training complete, checkpoint at %s", checkpoint_dir)
    return checkpoint_dir
