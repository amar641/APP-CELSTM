"""
The continuous, in-process pipeline: detects new hotspots and drives them
end to end (facility/weather ingestion scoped to that hotspot, spatial
enrichment, satellite retrieval, both classifiers, risk scoring) without
any request triggering it — see docs/architecture/data-flow.md.

`ContinuousPipeline.build(settings)` is this module's composition root,
the same role `scripts/training/*.py` play for training jobs (see
`api/dependencies.py`'s module docstring for the project's wiring
convention) — it's the one place this module is allowed to import
concrete `infrastructure` classes directly, since a long-lived background
loop needs to open its own short-lived session per tick rather than
receive one via FastAPI's per-request `Depends`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from industrial_fire.application.classification.classify_event import ClassifyEventUseCase
from industrial_fire.application.enrichment.spatial_enrichment import (
    EnrichedThermalEvent,
    SpatialEnrichmentUseCase,
)
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.application.ingestion.ingest_facilities import IngestFacilitiesUseCase
from industrial_fire.application.ingestion.ingest_thermal_events import IngestThermalEventsUseCase
from industrial_fire.application.ingestion.ingest_weather import IngestWeatherUseCase
from industrial_fire.application.risk.assess_risk import AssessRiskUseCase
from industrial_fire.application.satellite.retrieve_satellite_imagery import (
    RetrieveSatelliteImageryUseCase,
)
from industrial_fire.core.config import Settings, get_settings
from industrial_fire.core.exceptions import ExternalServiceError, UseCaseError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.value_objects.bounding_box import BoundingBox
from industrial_fire.infrastructure.database.repositories.classification_repository import (
    SqlClassificationRepository,
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
from industrial_fire.infrastructure.firms.client import FirmsClient
from industrial_fire.infrastructure.osm.overpass_client import OverpassFacilityProvider
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.infrastructure.satellite.preprocessor import RasterioImagePreprocessor
from industrial_fire.infrastructure.satellite.stac_client import StacSatelliteImageProvider
from industrial_fire.infrastructure.weather.client import OpenMeteoWeatherProvider
from industrial_fire.ml.encoders.vision_encoder import ResNetVisionEncoder
from industrial_fire.ml.inference.predict import CELSTMClassifier
from industrial_fire.ml.inference.predict_xgboost import XGBoostClassifier
from industrial_fire.ml.models.celstm import CELSTMConfig
from industrial_fire.ml.models.xgboost_classifier import XGBoostConfig

logger = get_logger(__name__)


@dataclass
class PipelineStatus:
    running: bool = False
    last_poll_at: datetime | None = None
    events_seen_last_tick: int = 0
    new_hotspots_last_tick: int = 0
    total_hotspots_processed: int = 0
    last_error: str | None = None

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "last_poll_at": self.last_poll_at.isoformat() if self.last_poll_at else None,
            "events_seen_last_tick": self.events_seen_last_tick,
            "new_hotspots_last_tick": self.new_hotspots_last_tick,
            "total_hotspots_processed": self.total_hotspots_processed,
            "last_error": self.last_error,
        }


@dataclass
class _PipelineConfig:
    poll_interval_seconds: float = 120.0
    facility_search_radius_km: float = 10.0
    weather_search_radius_km: float = 25.0
    satellite_search_radius_km: float = 5.0

    @classmethod
    def from_settings(cls, settings: Settings) -> _PipelineConfig:
        cfg = settings.app_config.get("ingestion", {}).get("pipeline", {})
        return cls(
            poll_interval_seconds=cfg.get("poll_interval_seconds", 120.0),
            facility_search_radius_km=cfg.get("facility_search_radius_km", 10.0),
            weather_search_radius_km=cfg.get("weather_search_radius_km", 25.0),
            satellite_search_radius_km=cfg.get("satellite_search_radius_km", 5.0),
        )


class ContinuousPipeline:
    def __init__(
        self, settings: Settings, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._config = _PipelineConfig.from_settings(settings)
        self.status = PipelineStatus()

        self._firms_client = FirmsClient(
            map_key=settings.firms_map_key or "",
            base_url=settings.data_config.get("firms", {}).get(
                "base_url", "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
            ),
            source=settings.firms_source,
        )
        self._facility_provider = OverpassFacilityProvider(
            api_url=settings.overpass_api_url,
            timeout_seconds=settings.overpass_timeout_seconds,
            facility_tags=settings.data_config.get("osm", {}).get(
                "facility_tags", ["landuse=industrial"]
            ),
        )
        self._weather_provider = OpenMeteoWeatherProvider(
            base_url=settings.weather_api_base_url, api_key=settings.weather_api_key
        )
        satellite_cfg = settings.model_config_yaml.get("architecture", {})
        bands = satellite_cfg.get("bands", ["B04", "B03", "B02", "B08"])
        self._satellite_provider = StacSatelliteImageProvider(
            api_url=settings.stac_api_url,
            collection=settings.stac_collection,
            cache_dir=settings.satellite_image_cache_dir,
            bands=bands,
        )
        self._preprocessor = RasterioImagePreprocessor(bands=bands)
        self._vision_extractor = ResNetVisionEncoder(device=settings.model_device)
        self._embedding_repository = QdrantEmbeddingRepository(
            get_qdrant_client(), settings.qdrant_collection
        )

    @classmethod
    def build(cls, settings: Settings | None = None) -> ContinuousPipeline:
        return cls(settings or get_settings(), get_session_factory())

    async def run_forever(self) -> None:
        self.status.running = True
        logger.info(
            "continuous pipeline started (poll_interval=%ss)", self._config.poll_interval_seconds
        )
        try:
            while True:
                try:
                    await self._tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - keep the loop alive across any tick failure
                    logger.exception("pipeline tick failed")
                    self.status.last_error = str(exc)
                await asyncio.sleep(self._config.poll_interval_seconds)
        finally:
            self.status.running = False
            logger.info("continuous pipeline stopped")

    async def _tick(self) -> None:
        aoi_bbox = BoundingBox.from_csv(self._settings.aoi_bbox)

        async with self._session_factory() as session:
            try:
                thermal_event_repo = SqlThermalEventRepository(session)
                facility_repo = SqlFacilityRepository(session)
                weather_repo = SqlWeatherRepository(session)
                satellite_repo = SqlSatelliteImageRepository(session)
                classification_repo = SqlClassificationRepository(session)

                ingest_events = IngestThermalEventsUseCase(self._firms_client, thermal_event_repo)
                ingest_facilities = IngestFacilitiesUseCase(self._facility_provider, facility_repo)
                ingest_weather = IngestWeatherUseCase(self._weather_provider, weather_repo)
                enrichment = SpatialEnrichmentUseCase(facility_repo, thermal_event_repo)
                feature_assembly = AssembleFeaturesUseCase(
                    enrichment, weather_repo, satellite_repo, self._embedding_repository
                )
                satellite_retrieval = RetrieveSatelliteImageryUseCase(
                    self._satellite_provider,
                    self._preprocessor,
                    self._vision_extractor,
                    satellite_repo,
                    self._embedding_repository,
                )
                assess_risk = AssessRiskUseCase(classification_repo)
                celstm_strategy = self._build_celstm(feature_assembly)
                xgboost_strategy = self._build_xgboost(feature_assembly)

                events = await ingest_events.execute(aoi_bbox, days_back=0)
                self.status.last_poll_at = datetime.utcnow()
                self.status.events_seen_last_tick = len(events)

                new_count = 0
                for event in events:
                    if await classification_repo.exists_for_event(event.id):
                        continue
                    new_count += 1
                    try:
                        await self._process_new_hotspot(
                            event,
                            ingest_facilities,
                            ingest_weather,
                            enrichment,
                            satellite_retrieval,
                            celstm_strategy,
                            xgboost_strategy,
                            classification_repo,
                            assess_risk,
                        )
                        self.status.total_hotspots_processed += 1
                    except Exception:  # noqa: BLE001 - one bad hotspot must not sink the tick
                        logger.exception("failed to process new hotspot %s", event.id)

                self.status.new_hotspots_last_tick = new_count
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _process_new_hotspot(
        self,
        event: ThermalEvent,
        ingest_facilities: IngestFacilitiesUseCase,
        ingest_weather: IngestWeatherUseCase,
        enrichment: SpatialEnrichmentUseCase,
        satellite_retrieval: RetrieveSatelliteImageryUseCase,
        celstm_strategy: CELSTMClassifier,
        xgboost_strategy: XGBoostClassifier,
        classification_repo: SqlClassificationRepository,
        assess_risk: AssessRiskUseCase,
    ) -> None:
        # Per-hotspot bounding boxes, not the whole AOI — this is the "only
        # those locations" ingestion scoping (see docs/architecture/data-flow.md).
        facility_bbox = BoundingBox.around(event.location, self._config.facility_search_radius_km)
        weather_bbox = BoundingBox.around(event.location, self._config.weather_search_radius_km)
        satellite_bbox = BoundingBox.around(event.location, self._config.satellite_search_radius_km)

        try:
            await ingest_facilities.execute(facility_bbox)
        except (ExternalServiceError, UseCaseError) as exc:
            logger.warning("facility ingestion failed for hotspot %s: %s", event.id, exc)

        try:
            await ingest_weather.execute(weather_bbox)
        except (ExternalServiceError, UseCaseError) as exc:
            logger.warning("weather ingestion failed for hotspot %s: %s", event.id, exc)

        enriched: EnrichedThermalEvent = await enrichment.execute(event)

        try:
            await satellite_retrieval.execute(event, satellite_bbox)
        except Exception as exc:  # noqa: BLE001 - satellite evidence is best-effort
            logger.warning("satellite retrieval failed for hotspot %s: %s", event.id, exc)

        for strategy in (celstm_strategy, xgboost_strategy):
            classify = ClassifyEventUseCase(strategy, classification_repo)
            classification = await classify.execute(enriched)
            await assess_risk.execute(classification)

        logger.info("classified new hotspot %s with 2 models", event.id)

    def _build_celstm(self, feature_assembly: AssembleFeaturesUseCase) -> CELSTMClassifier:
        arch_cfg = self._settings.model_config_yaml.get("architecture", {})
        model_cfg = CELSTMConfig.from_yaml_dict(arch_cfg)
        return CELSTMClassifier(
            model_config=model_cfg,
            registry_dir=self._settings.model_registry_dir,
            feature_assembly=feature_assembly,
            device=self._settings.model_device,
        )

    def _build_xgboost(self, feature_assembly: AssembleFeaturesUseCase) -> XGBoostClassifier:
        xgb_cfg = self._settings.model_config_yaml.get("xgboost", {}).get("architecture", {})
        model_cfg = XGBoostConfig.from_yaml_dict(xgb_cfg)
        return XGBoostClassifier(
            model_config=model_cfg,
            registry_dir=self._settings.model_registry_dir,
            feature_assembly=feature_assembly,
        )
