"""
Composition root: wires concrete `infrastructure` adapters into `domain`
interfaces and `application` use cases, and exposes them as FastAPI
dependencies. This is the ONLY place the API layer is allowed to import
concrete infrastructure classes — routes depend on use cases, never on
repositories or provider clients directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from industrial_fire.application.classification.classify_event import (
    ClassificationStrategy,
    ClassifyEventUseCase,
)
from industrial_fire.application.classification.rule_based_classifier import RuleBasedClassifier
from industrial_fire.application.enrichment.spatial_enrichment import SpatialEnrichmentUseCase
from industrial_fire.application.feature_assembly.assemble_features import AssembleFeaturesUseCase
from industrial_fire.application.ingestion.ingest_facilities import IngestFacilitiesUseCase
from industrial_fire.application.ingestion.ingest_thermal_events import IngestThermalEventsUseCase
from industrial_fire.application.risk.assess_risk import AssessRiskUseCase
from industrial_fire.core.config import Settings, get_settings
from industrial_fire.infrastructure.database.repositories.classification_repository import (
    SqlClassificationRepository,
)
from industrial_fire.infrastructure.database.repositories.facility_repository import SqlFacilityRepository
from industrial_fire.infrastructure.database.repositories.satellite_image_repository import (
    SqlSatelliteImageRepository,
)
from industrial_fire.infrastructure.database.repositories.thermal_event_repository import (
    SqlThermalEventRepository,
)
from industrial_fire.infrastructure.database.repositories.weather_repository import SqlWeatherRepository
from industrial_fire.infrastructure.database.session import get_session
from industrial_fire.infrastructure.firms.client import FirmsClient
from industrial_fire.infrastructure.osm.overpass_client import OverpassFacilityProvider
from industrial_fire.infrastructure.qdrant.client import get_qdrant_client
from industrial_fire.infrastructure.qdrant.embedding_repository import QdrantEmbeddingRepository
from industrial_fire.ml.inference.predict import CELSTMClassifier
from industrial_fire.ml.models.celstm import CELSTMConfig

SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_thermal_event_repository(session: SessionDep) -> SqlThermalEventRepository:
    return SqlThermalEventRepository(session)


def get_facility_repository(session: SessionDep) -> SqlFacilityRepository:
    return SqlFacilityRepository(session)


def get_classification_repository(session: SessionDep) -> SqlClassificationRepository:
    return SqlClassificationRepository(session)


def get_weather_repository(session: SessionDep) -> SqlWeatherRepository:
    return SqlWeatherRepository(session)


def get_satellite_image_repository(session: SessionDep) -> SqlSatelliteImageRepository:
    return SqlSatelliteImageRepository(session)


@lru_cache
def get_embedding_repository() -> QdrantEmbeddingRepository:
    settings = get_settings()
    return QdrantEmbeddingRepository(get_qdrant_client(), settings.qdrant_collection)


def get_firms_client(settings: SettingsDep) -> FirmsClient:
    data_cfg = settings.data_config.get("firms", {})
    return FirmsClient(
        map_key=settings.firms_map_key or "",
        base_url=data_cfg.get("base_url", "https://firms.modaps.eosdis.nasa.gov/api/area/csv"),
        source=settings.firms_source,
    )


def get_facility_provider(settings: SettingsDep) -> OverpassFacilityProvider:
    data_cfg = settings.data_config.get("osm", {})
    return OverpassFacilityProvider(
        api_url=settings.overpass_api_url,
        timeout_seconds=settings.overpass_timeout_seconds,
        facility_tags=data_cfg.get("facility_tags", ["landuse=industrial"]),
    )


def get_spatial_enrichment_use_case(
    facility_repository: Annotated[SqlFacilityRepository, Depends(get_facility_repository)],
    thermal_event_repository: Annotated[SqlThermalEventRepository, Depends(get_thermal_event_repository)],
) -> SpatialEnrichmentUseCase:
    return SpatialEnrichmentUseCase(facility_repository, thermal_event_repository)


def get_assemble_features_use_case(
    enrichment: Annotated[SpatialEnrichmentUseCase, Depends(get_spatial_enrichment_use_case)],
    weather_repository: Annotated[SqlWeatherRepository, Depends(get_weather_repository)],
    satellite_image_repository: Annotated[SqlSatelliteImageRepository, Depends(get_satellite_image_repository)],
) -> AssembleFeaturesUseCase:
    return AssembleFeaturesUseCase(
        enrichment, weather_repository, satellite_image_repository, get_embedding_repository()
    )


def get_classification_strategy(
    settings: SettingsDep,
    feature_assembly: Annotated[AssembleFeaturesUseCase, Depends(get_assemble_features_use_case)],
) -> ClassificationStrategy:
    """
    `CLASSIFICATION_STRATEGY=rule_based` (default) or `celstm` in `.env`.
    CELSTMClassifier itself falls back to the rule-based classifier when no
    trained checkpoint exists yet, so switching this before a model is
    trained is safe — it's a no-op until `scripts/training/train_celstm.py`
    has produced a checkpoint.
    """
    if settings.classification_strategy == "celstm":
        model_cfg = CELSTMConfig.from_yaml_dict(settings.model_config_yaml.get("architecture", {}))
        return CELSTMClassifier(
            model_config=model_cfg,
            registry_dir=settings.model_registry_dir,
            feature_assembly=feature_assembly,
            device=settings.model_device,
        )
    return RuleBasedClassifier()


def get_classify_use_case(
    strategy: Annotated[ClassificationStrategy, Depends(get_classification_strategy)],
    classification_repository: Annotated[SqlClassificationRepository, Depends(get_classification_repository)],
) -> ClassifyEventUseCase:
    return ClassifyEventUseCase(strategy, classification_repository)


def get_assess_risk_use_case(
    classification_repository: Annotated[SqlClassificationRepository, Depends(get_classification_repository)],
) -> AssessRiskUseCase:
    return AssessRiskUseCase(classification_repository)


def get_ingest_thermal_events_use_case(
    firms_client: Annotated[FirmsClient, Depends(get_firms_client)],
    thermal_event_repository: Annotated[SqlThermalEventRepository, Depends(get_thermal_event_repository)],
) -> IngestThermalEventsUseCase:
    return IngestThermalEventsUseCase(firms_client, thermal_event_repository)


def get_ingest_facilities_use_case(
    facility_provider: Annotated[OverpassFacilityProvider, Depends(get_facility_provider)],
    facility_repository: Annotated[SqlFacilityRepository, Depends(get_facility_repository)],
) -> IngestFacilitiesUseCase:
    return IngestFacilitiesUseCase(facility_provider, facility_repository)
