"""
Embedding storage/retrieval for `SatelliteImage` vectors, and the similarity
search used by the (future) "find visually similar past events" feature.

Deliberately narrow: this is the only place `qdrant_client` is imported
outside `infrastructure.qdrant.client`. Postgres remains the system of
record for which images/events exist — Qdrant only ever answers
"what's similar to vector X", keyed by the same `SatelliteImage.id` UUID
used in Postgres (see ADR-002).
"""

from __future__ import annotations

from uuid import UUID

import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from industrial_fire.core.logging import get_logger

logger = get_logger(__name__)


class QdrantEmbeddingRepository:
    def __init__(self, client: AsyncQdrantClient, collection: str, vector_size: int = 512) -> None:
        self._client = client
        self._collection = collection
        self._vector_size = vector_size

    async def ensure_collection(self) -> None:
        collections = await self._client.get_collections()
        if self._collection not in {c.name for c in collections.collections}:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._vector_size, distance=Distance.COSINE),
            )
            logger.info("created Qdrant collection %s", self._collection)

    async def upsert(self, vector_id: UUID, vector: np.ndarray, payload: dict | None = None) -> None:
        await self._client.upsert(
            collection_name=self._collection,
            points=[PointStruct(id=str(vector_id), vector=vector.tolist(), payload=payload or {})],
        )

    async def get(self, vector_id: UUID) -> np.ndarray | None:
        points = await self._client.retrieve(
            collection_name=self._collection, ids=[str(vector_id)], with_vectors=True
        )
        if not points:
            return None
        return np.array(points[0].vector)

    async def search_similar(self, vector: np.ndarray, limit: int = 10) -> list[tuple[UUID, float]]:
        """Returns [(satellite_image_id, similarity_score), ...] nearest-first."""
        results = await self._client.search(
            collection_name=self._collection, query_vector=vector.tolist(), limit=limit
        )
        return [(UUID(str(r.id)), r.score) for r in results]
