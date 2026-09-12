"""
Vision feature extractor — implements `application.satellite.retrieve_satellite_imagery.VisionFeatureExtractor`.

v1 uses a frozen torchvision ResNet18 backbone (ImageNet weights) as a
generic embedding extractor, plus a few cheap band-ratio statistics as
structured features. Swappable for a remote-sensing-specific foundation
model later without touching the use case that calls this.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn
from torchvision.models import ResNet18_Weights, resnet18

from industrial_fire.application.satellite.retrieve_satellite_imagery import VisionFeatureExtractor
from industrial_fire.core.logging import get_logger

logger = get_logger(__name__)


class ResNetVisionEncoder(VisionFeatureExtractor):
    def __init__(self, device: str = "cpu") -> None:
        self._device = torch.device(device)
        backbone = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
        backbone.fc = nn.Identity()  # 512-dim pooled embedding
        backbone.eval()
        self._model = backbone.to(self._device)

    @torch.no_grad()
    def extract(self, image_array: np.ndarray) -> tuple[dict[str, float], np.ndarray]:
        """`image_array` is (bands, H, W); first 3 bands are treated as RGB-ish for the backbone."""
        rgb = image_array[:3]
        tensor = torch.from_numpy(rgb).unsqueeze(0).float().to(self._device)
        embedding = self._model(tensor).squeeze(0).cpu().numpy()

        structured_features = self._band_statistics(image_array)
        return structured_features, embedding

    @staticmethod
    def _band_statistics(image_array: np.ndarray) -> dict[str, float]:
        """Cheap, interpretable stats (e.g. NDVI-like ratio if a NIR band is present) alongside the embedding."""
        stats = {
            "mean_intensity": float(image_array.mean()),
            "std_intensity": float(image_array.std()),
        }
        if image_array.shape[0] >= 4:
            red, nir = image_array[0], image_array[3]
            denom = red + nir
            ndvi = np.divide(nir - red, denom, out=np.zeros_like(denom), where=denom != 0)
            stats["mean_ndvi"] = float(ndvi.mean())
        return stats


# Backwards-compatible alias used elsewhere in docs/scripts.
VisionEncoder = ResNetVisionEncoder
