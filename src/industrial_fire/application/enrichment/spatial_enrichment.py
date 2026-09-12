"""
Use case: attach facility-proximity and persistence signals to a raw `ThermalEvent`.

Orchestrates the pure `ProximityService`/`PersistenceService` domain logic
with repository reads. This is the shared enrichment step both the
rule-based classifier and the CELSTM feature-assembly pipeline consume.
"""

from __future__ import annotations

from dataclasses import dataclass

from industrial_fire.core.config import get_settings
from industrial_fire.domain.entities.facility import Facility
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.repositories.facility_repository import FacilityRepository
from industrial_fire.domain.repositories.thermal_event_repository import ThermalEventRepository
from industrial_fire.domain.services.persistence_service import PersistenceResult, PersistenceService
from industrial_fire.domain.services.proximity_service import ProximityResult, ProximityService
from industrial_fire.domain.value_objects.time_range import TimeRange


@dataclass(frozen=True, slots=True)
class EnrichedThermalEvent:
    event: ThermalEvent
    proximity: ProximityResult
    persistence: PersistenceResult
    history_window_days: int


class SpatialEnrichmentUseCase:
    def __init__(
        self,
        facility_repository: FacilityRepository,
        thermal_event_repository: ThermalEventRepository,
    ) -> None:
        self._facility_repository = facility_repository
        self._thermal_event_repository = thermal_event_repository

    async def execute(self, event: ThermalEvent) -> EnrichedThermalEvent:
        settings = get_settings()
        app_cfg = settings.app_config.get("enrichment", {})
        facility_radius_km = app_cfg.get("facility_proximity_km", 5.0)
        same_hotspot_radius_km = app_cfg.get("same_hotspot_radius_km", 2.0)
        window_days = app_cfg.get("persistence_window_days", 7)

        candidate_facilities: list[Facility] = await self._facility_repository.find_nearest(
            event.location, limit=5
        )
        proximity = ProximityService.nearest_facility(event.location, candidate_facilities)
        if proximity.distance_km is not None and proximity.distance_km > facility_radius_km:
            # nearest match is outside the "close" radius; keep it for reporting but
            # downstream logic decides what "close" means via ProximityResult.is_within
            pass

        time_range = TimeRange.last_n_days(window_days)
        history = await self._thermal_event_repository.find_near(
            event.location, radius_km=same_hotspot_radius_km, time_range=time_range
        )
        history = [e for e in history if e.id != event.id]
        persistence = PersistenceService.count_nearby(event.location, history, same_hotspot_radius_km)

        return EnrichedThermalEvent(
            event=event,
            proximity=proximity,
            persistence=persistence,
            history_window_days=window_days,
        )
