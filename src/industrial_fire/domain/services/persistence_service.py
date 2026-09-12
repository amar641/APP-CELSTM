"""Pure domain logic for the persistence signal (repeat detections at ~the same spot => fixed source, not a spreading fire)."""

from __future__ import annotations

from dataclasses import dataclass

from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.value_objects.coordinates import Coordinates


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    matched_event_count: int
    average_frp_mw: float

    def frp_deviation_pct(self, current_frp_mw: float) -> float | None:
        if self.average_frp_mw <= 0:
            return None
        return round(((current_frp_mw - self.average_frp_mw) / self.average_frp_mw) * 100, 1)


class PersistenceService:
    @staticmethod
    def count_nearby(
        location: Coordinates, history: list[ThermalEvent], radius_km: float
    ) -> PersistenceResult:
        """`history` is prior detections already scoped to the lookback window."""
        matches = [e for e in history if location.distance_km(e.location) <= radius_km]
        avg_frp = sum(m.frp_mw for m in matches) / len(matches) if matches else 0.0
        return PersistenceResult(matched_event_count=len(matches), average_frp_mw=avg_frp)
