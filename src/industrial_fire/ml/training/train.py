"""
CELSTM training loop. Invoked via `scripts/training/train_celstm.py`, never
imported by the API — training is an offline job, not a request-path
concern. Config comes from `configs/model.yaml:training`; every run writes
a versioned checkpoint + metrics under `MODEL_REGISTRY_DIR` for reproducibility.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import torch
from torch import nn, optim
from torch.utils.data import DataLoader, random_split

from industrial_fire.core.logging import get_logger
from industrial_fire.ml.datasets.thermal_sequence_dataset import ThermalSequenceDataset
from industrial_fire.ml.evaluation.metrics import evaluate
from industrial_fire.ml.models.celstm import CELSTM, CELSTMConfig

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    batch_size: int = 32
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    max_epochs: int = 50
    early_stopping_patience: int = 5
    val_split: float = 0.2
    seed: int = 42

    @classmethod
    def from_yaml_dict(cls, training: dict) -> TrainingConfig:
        return cls(
            batch_size=training.get("batch_size", 32),
            learning_rate=training.get("learning_rate", 1e-3),
            weight_decay=training.get("weight_decay", 1e-4),
            max_epochs=training.get("max_epochs", 50),
            early_stopping_patience=training.get("early_stopping_patience", 5),
            val_split=training.get("val_split", 0.2),
            seed=training.get("seed", 42),
        )


def train_celstm(
    dataset: ThermalSequenceDataset,
    model_config: CELSTMConfig,
    training_config: TrainingConfig,
    registry_dir: str,
    device: str = "cpu",
) -> Path:
    torch.manual_seed(training_config.seed)
    dev = torch.device(device)

    val_size = int(len(dataset) * training_config.val_split)
    train_set, val_set = random_split(dataset, [len(dataset) - val_size, val_size])
    train_loader = DataLoader(train_set, batch_size=training_config.batch_size, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=training_config.batch_size)

    model = CELSTM(model_config).to(dev)
    optimizer = optim.Adam(
        model.parameters(), lr=training_config.learning_rate, weight_decay=training_config.weight_decay
    )
    criterion = nn.CrossEntropyLoss()

    best_val_loss = float("inf")
    epochs_without_improvement = 0
    version = datetime.utcnow().strftime("celstm-%Y%m%d%H%M%S")
    checkpoint_dir = Path(registry_dir) / version
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(training_config.max_epochs):
        model.train()
        for decisions, intensities, availability, vision, vision_available, labels in train_loader:
            decisions, intensities, availability = (
                decisions.to(dev), intensities.to(dev), availability.to(dev),
            )
            vision, vision_available, labels = vision.to(dev), vision_available.to(dev), labels.to(dev)

            optimizer.zero_grad()
            logits, _diagnostics = model(decisions, intensities, availability, vision, vision_available)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

        metrics = evaluate(model, val_loader, dev)
        logger.info("epoch=%d val_loss=%.4f val_accuracy=%.4f", epoch, metrics["loss"], metrics["accuracy"])

        if metrics["loss"] < best_val_loss:
            best_val_loss = metrics["loss"]
            epochs_without_improvement = 0
            torch.save(model.state_dict(), checkpoint_dir / "model.pt")
            (checkpoint_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= training_config.early_stopping_patience:
                logger.info("early stopping at epoch=%d", epoch)
                break

    logger.info("training complete, best checkpoint at %s", checkpoint_dir)
    return checkpoint_dir
