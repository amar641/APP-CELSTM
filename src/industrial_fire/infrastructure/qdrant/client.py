"""Process-wide Qdrant client factory. Qdrant is a similarity index, never the system of record — see ADR-002."""

from __future__ import annotations

from functools import lru_cache

from qdrant_client import AsyncQdrantClient

from industrial_fire.core.config import get_settings


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    settings = get_settings()
    return AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
