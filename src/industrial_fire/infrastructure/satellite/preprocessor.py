"""
Concrete `ImagePreprocessor` — implements `application.satellite.retrieve_satellite_imagery.ImagePreprocessor`.

Reads the per-band GeoTIFFs `StacSatelliteImageProvider.download()` cached
under a directory, stacks them in the configured band order, and
normalizes to [0, 1] float32 so `ml.encoders.VisionEncoder` always sees a
consistent input regardless of the raw sensor's bit depth.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from industrial_fire.application.satellite.retrieve_satellite_imagery import ImagePreprocessor
from industrial_fire.core.exceptions import FeatureAssemblyError
from industrial_fire.core.logging import get_logger

logger = get_logger(__name__)

# Sentinel-2 L2A surface reflectance is scaled by 10000; clamp instead of
# assuming a fixed sensor max so other collections' band depths don't blow up.
_REFLECTANCE_SCALE = 10000.0


class RasterioImagePreprocessor(ImagePreprocessor):
    def __init__(self, bands: list[str], target_size: tuple[int, int] = (224, 224)) -> None:
        self._bands = bands
        self._target_size = target_size

    def preprocess(self, local_path: str) -> np.ndarray:
        band_dir = Path(local_path)
        arrays: list[np.ndarray] = []

        for band in self._bands:
            band_path = band_dir / f"{band}.tif"
            if not band_path.exists():
                logger.warning("band %s missing at %s — filling with zeros", band, band_path)
                arrays.append(np.zeros(self._target_size, dtype=np.float32))
                continue
            with rasterio.open(band_path) as src:
                data = src.read(1).astype(np.float32)
            arrays.append(self._normalize(self._resize(data)))

        if not arrays:
            raise FeatureAssemblyError(f"no bands could be read from {local_path}")

        return np.stack(arrays, axis=0)  # (bands, H, W)

    def _resize(self, array: np.ndarray) -> np.ndarray:
        if array.shape == self._target_size:
            return array
        # Nearest-neighbor resize with no extra imaging dependency — adequate
        # for the vision encoder's fixed input size; swap for a proper
        # resampler (e.g. rasterio's warp) if quality becomes a concern.
        row_idx = np.linspace(0, array.shape[0] - 1, self._target_size[0]).astype(int)
        col_idx = np.linspace(0, array.shape[1] - 1, self._target_size[1]).astype(int)
        return array[row_idx][:, col_idx]

    @staticmethod
    def _normalize(array: np.ndarray) -> np.ndarray:
        return np.clip(array / _REFLECTANCE_SCALE, 0.0, 1.0)
