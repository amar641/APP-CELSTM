"""
The frozen contract between `application.feature_assembly.FeatureBundle` and
`ml.models.celstm.CELSTM`'s structured-feature input. See docs/ml/feature-contract.md
— any change here is a breaking change to trained model checkpoints.
"""

from __future__ import annotations

import numpy as np

# Order matters — this is the column order fed into the model's structured branch.
FEATURE_ORDER: tuple[str, ...] = (
    "frp_mw",
    "facility_distance_km",
    "persistence_count",
    "frp_deviation_pct",
    "temperature_c",
    "wind_speed_ms",
    "wind_direction_deg",
    "relative_humidity_pct",
)


def structured_features_to_vector(features: dict[str, float]) -> np.ndarray:
    """Missing keys default to 0.0 so partially-enriched events don't crash assembly."""
    return np.array([features.get(name, 0.0) for name in FEATURE_ORDER], dtype=np.float32)
