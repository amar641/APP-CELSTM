"""
PyTorch `Dataset` over labeled per-hotspot round sequences for CE-LSTM.

Each sample is the sequence of `FeatureBundle`s produced by
`AssembleFeaturesUseCase.execute_sequence` for one hotspot — one round per
satellite image retrieved for it (see docs/ml/dataset.md and
docs/ml/celstm.md). `ml.features.source_signals` turns each round's
structured features into the (decision, intensity, availability) triples
CE-LSTM's analytic modules consume; the vision embedding is passed through
unprocessed for the model's learned vision head to project.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch
from torch.utils.data import Dataset

from industrial_fire.application.feature_assembly.assemble_features import FeatureBundle
from industrial_fire.core.types import ClassificationLabel
from industrial_fire.ml.features.source_signals import NUM_STRUCTURED_SOURCES, structured_signals

_LABEL_TO_INDEX: dict[ClassificationLabel, int] = {
    ClassificationLabel.GAS_FLARE_NORMAL_INDUSTRIAL: 0,
    ClassificationLabel.POTENTIAL_INDUSTRIAL_FIRE: 1,
    ClassificationLabel.WILDFIRE: 2,
    ClassificationLabel.UNKNOWN_NEEDS_REVIEW: 3,
}


@dataclass(frozen=True, slots=True)
class LabeledSequence:
    rounds: list[FeatureBundle]  # oldest -> newest, one per satellite-image round
    label: ClassificationLabel


class ThermalSequenceDataset(Dataset):
    def __init__(self, samples: list[LabeledSequence], sequence_length: int, vision_embedding_dim: int) -> None:
        self._samples = samples
        self._sequence_length = sequence_length
        self._vision_embedding_dim = vision_embedding_dim

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(
        self, index: int
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        sample = self._samples[index]
        T = self._sequence_length

        decisions = np.zeros((T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        intensities = np.zeros((T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        availability = np.zeros((T, NUM_STRUCTURED_SOURCES), dtype=np.float32)
        vision = np.zeros((T, self._vision_embedding_dim), dtype=np.float32)
        vision_available = np.zeros(T, dtype=np.float32)

        # Zero-padded at the front (oldest), most recent round last — CE-LSTM's
        # hive state is read out after the final round, so the newest, most
        # informative round should always land at index T-1.
        offset = max(0, T - len(sample.rounds))
        for i, bundle in enumerate(sample.rounds[-T:]):
            d, e, a = structured_signals(bundle.structured_features)
            decisions[offset + i] = d
            intensities[offset + i] = e
            availability[offset + i] = a
            if bundle.vision_embedding is not None:
                vision[offset + i] = bundle.vision_embedding
                vision_available[offset + i] = 1.0

        label_index = _LABEL_TO_INDEX[sample.label]
        return (
            torch.from_numpy(decisions),
            torch.from_numpy(intensities),
            torch.from_numpy(availability),
            torch.from_numpy(vision),
            torch.from_numpy(vision_available),
            torch.tensor(label_index, dtype=torch.long),
        )
