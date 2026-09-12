"""
Maps a `FeatureBundle` (application.feature_assembly) to the per-round
"voter" signals CE-LSTM's analytical modules consume — see
`ml.models.celstm` and docs/ml/celstm.md.

HMNN's original voters are humans producing (decision, emotion, influence)
each round. Here the "voters" are independent evidence sources about a
single hotspot — thermal, facility-proximity, persistence, weather — each
squashed into the same (decision, intensity) ∈ [0,1]² shape. The vision
source (satellite embedding) is handled separately in `ml.models.celstm`
via a learned projection head, since raw embeddings have no natural
analytic squash. `SOURCE_ORDER` fixes the column order everywhere a
source tensor is built or consumed — changing it is a breaking change to
any trained checkpoint, same as `ml.features.feature_schema.FEATURE_ORDER`.
"""

from __future__ import annotations

import numpy as np

# Structured (non-vision) sources, in tensor-column order. "vision" is
# appended as a 5th, model-internal source — see ml.models.celstm.CELSTM.
SOURCE_ORDER: tuple[str, ...] = ("thermal", "facility_proximity", "persistence", "weather")
NUM_STRUCTURED_SOURCES = len(SOURCE_ORDER)
TOTAL_SOURCES = NUM_STRUCTURED_SOURCES + 1  # + vision

# Squash scales — tuned to plausible real-world magnitudes, not learned.
# Keeping these analytic (not weight matrices) is the point of the paper's
# design: the model can't memorize by overfitting these.
_FRP_SCALE_MW = 50.0
_FRP_DEVIATION_SCALE_PCT = 100.0
_FACILITY_CLOSE_RADIUS_KM = 5.0
_PERSISTENCE_SCALE_COUNT = 8.0
_WIND_SPEED_SCALE_MS = 15.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _thermal_signal(features: dict[str, float]) -> tuple[float, float, bool]:
    """decision = how far FRP has deviated from this location's own history; intensity = raw FRP magnitude."""
    frp_mw = features.get("frp_mw", 0.0)
    intensity = _clamp01(frp_mw / _FRP_SCALE_MW)
    deviation_pct = features.get("frp_deviation_pct")
    decision = _clamp01(deviation_pct / _FRP_DEVIATION_SCALE_PCT) if deviation_pct else intensity
    return decision, intensity, True  # FRP is always present — this source is never "missing"


def _facility_proximity_signal(features: dict[str, float]) -> tuple[float, float, bool]:
    """decision/intensity = closeness to nearest known facility; unavailable if no facility was found at all."""
    distance_km = features.get("facility_distance_km", -1.0)
    if distance_km < 0:
        return 0.0, 0.0, False
    closeness = _clamp01(1.0 - distance_km / _FACILITY_CLOSE_RADIUS_KM)
    return closeness, closeness, True


def _persistence_signal(features: dict[str, float]) -> tuple[float, float, bool]:
    """decision/intensity = how often this exact hotspot has recurred recently — the "fixed source" signal."""
    count = features.get("persistence_count", 0.0)
    value = _clamp01(count / _PERSISTENCE_SCALE_COUNT)
    return value, value, True


def _weather_signal(features: dict[str, float]) -> tuple[float, float, bool]:
    """decision/intensity = wind speed, a proxy for fire-spread conduciveness; unavailable if no weather joined."""
    if "wind_speed_ms" not in features:
        return 0.0, 0.0, False
    value = _clamp01(features["wind_speed_ms"] / _WIND_SPEED_SCALE_MS)
    return value, value, True


_SIGNAL_FNS = {
    "thermal": _thermal_signal,
    "facility_proximity": _facility_proximity_signal,
    "persistence": _persistence_signal,
    "weather": _weather_signal,
}


def structured_signals(features: dict[str, float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    One round's structured-source signals, in `SOURCE_ORDER`.
    Returns (decisions, intensities, availability), each shape (NUM_STRUCTURED_SOURCES,).
    """
    decisions = np.zeros(NUM_STRUCTURED_SOURCES, dtype=np.float32)
    intensities = np.zeros(NUM_STRUCTURED_SOURCES, dtype=np.float32)
    availability = np.zeros(NUM_STRUCTURED_SOURCES, dtype=np.float32)
    for i, name in enumerate(SOURCE_ORDER):
        d, e, available = _SIGNAL_FNS[name](features)
        decisions[i] = d
        intensities[i] = e
        availability[i] = 1.0 if available else 0.0
    return decisions, intensities, availability
