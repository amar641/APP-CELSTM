"""
Use case: find satellite imagery covering a thermal event, preprocess it, extract
vision features, and persist structured features (Postgres) + embedding (Qdrant).

Three ports keep this orchestration independent of *which* STAC catalog,
preprocessing library, or vision model is used:
  - SatelliteImageProvider: STAC search + download (infrastructure.satellite)
  - ImagePreprocessor: cloud-masking/normalization/cropping (infrastructure.satellite or ml.features)
  - VisionFeatureExtractor: CNN/foundation-model embedding + structured features (ml.encoders)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

import numpy as np

from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.satellite_image import SatelliteImage
from industrial_fire.domain.entities.thermal_event import ThermalEvent
from industrial_fire.domain.repositories.satellite_image_repository import SatelliteImageRepository
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

logger = get_logger(__name__)


class SatelliteImageProvider(ABC):
    @abstractmethod
    async def search(self, footprint: BoundingBox, max_cloud_cover_pct: float) -> list[SatelliteImage]:
        ...

    @abstractmethod
    async def download(self, image: SatelliteImage) -> str:
        """Returns a local file path to the downloaded raster."""


class ImagePreprocessor(ABC):
    @abstractmethod
    def preprocess(self, local_path: str) -> np.ndarray:
        """Returns a normalized, model-ready array (bands, H, W)."""


class VisionFeatureExtractor(ABC):
    @abstractmethod
    def extract(self, image_array: np.ndarray) -> tuple[dict[str, float], np.ndarray]:
        """Returns (structured_features, embedding_vector)."""


class RetrieveSatelliteImageryUseCase:
    def __init__(
        self,
        provider: SatelliteImageProvider,
        preprocessor: ImagePreprocessor,
        extractor: VisionFeatureExtractor,
        repository: SatelliteImageRepository,
        embedding_writer: Any,  # infrastructure.qdrant.embedding_repository.EmbeddingRepository
        max_cloud_cover_pct: float = 20.0,
    ) -> None:
        self._provider = provider
        self._preprocessor = preprocessor
        self._extractor = extractor
        self._repository = repository
        self._embedding_writer = embedding_writer
        self._max_cloud_cover_pct = max_cloud_cover_pct

    async def execute(self, thermal_event: ThermalEvent, footprint: BoundingBox) -> list[SatelliteImage]:
        candidates = await self._provider.search(footprint, self._max_cloud_cover_pct)
        results: list[SatelliteImage] = []

        for image in candidates:
            local_path = await self._provider.download(image)
            array = self._preprocessor.preprocess(local_path)
            structured_features, embedding = self._extractor.extract(array)

            image.local_path = local_path
            image.structured_features = structured_features
            image.thermal_event_id = thermal_event.id
            saved = await self._repository.upsert(image)

            await self._write_embedding(saved.id, embedding)
            saved.has_embedding = True
            results.append(saved)

        logger.info(
            "retrieved %d satellite images for thermal_event_id=%s", len(results), thermal_event.id
        )
        return results

    async def _write_embedding(self, image_id: UUID, embedding: np.ndarray) -> None:
        await self._embedding_writer.upsert(vector_id=image_id, vector=embedding)
