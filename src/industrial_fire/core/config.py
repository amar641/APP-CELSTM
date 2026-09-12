"""
Centralized, environment-driven configuration.

Secrets and environment-specific values come from environment variables
(`.env` locally, real env vars in deployment). Non-secret defaults and
tunables live in `configs/*.yaml` and are merged in as fallback values so
the two never drift into duplicate sources of truth.

Every other layer depends on `Settings` via dependency injection
(`core.config.get_settings`) — never on `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parents[3] / "configs"


def _load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Settings(BaseSettings):
    """Environment-backed settings. Field names match `.env.example`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_port: int = Field(default=8000, alias="API_PORT")

    database_url: str = Field(
        default="postgresql+psycopg://industrial_fire:change_me@localhost:5432/industrial_fire",
        alias="DATABASE_URL",
    )

    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="satellite_image_embeddings", alias="QDRANT_COLLECTION")

    firms_map_key: str | None = Field(default=None, alias="FIRMS_MAP_KEY")
    aoi_bbox: str = Field(default="68.0,20.0,78.0,28.0", alias="AOI_BBOX")
    firms_source: str = Field(default="VIIRS_SNPP_NRT", alias="FIRMS_SOURCE")
    history_days: int = Field(default=7, alias="HISTORY_DAYS")

    overpass_api_url: str = Field(
        default="https://overpass-api.de/api/interpreter", alias="OVERPASS_API_URL"
    )
    overpass_timeout_seconds: int = Field(default=60, alias="OVERPASS_TIMEOUT_SECONDS")

    weather_provider: str = Field(default="open-meteo", alias="WEATHER_PROVIDER")
    weather_api_key: str | None = Field(default=None, alias="WEATHER_API_KEY")
    weather_api_base_url: str = Field(
        default="https://api.open-meteo.com/v1", alias="WEATHER_API_BASE_URL"
    )

    stac_api_url: str = Field(
        default="https://earth-search.aws.element84.com/v1", alias="STAC_API_URL"
    )
    stac_collection: str = Field(default="sentinel-2-l2a", alias="STAC_COLLECTION")
    satellite_image_cache_dir: str = Field(
        default="./.cache/satellite", alias="SATELLITE_IMAGE_CACHE_DIR"
    )

    model_registry_dir: str = Field(default="./.models", alias="MODEL_REGISTRY_DIR")
    model_device: str = Field(default="cpu", alias="MODEL_DEVICE")
    # "rule_based" (default, always available) or "celstm" (falls back to
    # rule_based automatically if no checkpoint exists yet — see
    # ml.inference.predict.CELSTMClassifier).
    classification_strategy: str = Field(default="rule_based", alias="CLASSIFICATION_STRATEGY")

    @property
    def aoi_bbox_tuple(self) -> tuple[float, float, float, float]:
        west, south, east, north = (float(x) for x in self.aoi_bbox.split(","))
        return west, south, east, north

    # --- non-secret config merged from configs/*.yaml -----------------
    @property
    def app_config(self) -> dict[str, Any]:
        return _load_yaml("app.yaml")

    @property
    def data_config(self) -> dict[str, Any]:
        return _load_yaml("data.yaml")

    @property
    def model_config_yaml(self) -> dict[str, Any]:
        return _load_yaml("model.yaml")


@lru_cache
def get_settings() -> Settings:
    """Process-wide cached settings instance. Safe to call repeatedly."""
    return Settings()
