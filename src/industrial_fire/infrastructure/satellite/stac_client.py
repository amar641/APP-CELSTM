"""
STAC adapter — implements the `SatelliteImageProvider` port using `pystac-client`
against a public catalog (Earth Search / Sentinel-2 L2A by default).

`download` fetches the visible+NIR bands needed by `ml.encoders` and caches
them under `SATELLITE_IMAGE_CACHE_DIR`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import rasterio
from pystac_client import Client
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from industrial_fire.application.satellite.retrieve_satellite_imagery import SatelliteImageProvider
from industrial_fire.core.exceptions import ExternalServiceError
from industrial_fire.core.logging import get_logger
from industrial_fire.domain.entities.satellite_image import SatelliteImage
from industrial_fire.domain.value_objects.bounding_box import BoundingBox

logger = get_logger(__name__)

# Sentinel-2 band code -> Earth Search (element84) v1 sentinel-2-l2a asset key.
# The catalog names its assets by color/purpose, not by band code, so a
# literal `item.assets.get("B04")` always misses. Local cache files still
# use the band-code names (`B04.tif`, ...) so config/preprocessing stay in
# one consistent vocabulary; only the STAC lookup needs this mapping.
_BAND_CODE_TO_EARTH_SEARCH_ASSET: dict[str, str] = {
    "B01": "coastal",
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B08": "nir",
    "B8A": "nir08",
    "B09": "nir09",
    "B11": "swir16",
    "B12": "swir22",
}


class StacSatelliteImageProvider(SatelliteImageProvider):
    def __init__(self, api_url: str, collection: str, cache_dir: str, bands: list[str] | None = None) -> None:
        self._api_url = api_url
        self._collection = collection
        self._cache_dir = Path(cache_dir)
        self._bands = bands or ["B04", "B03", "B02", "B08"]
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def search(self, footprint: BoundingBox, max_cloud_cover_pct: float) -> list[SatelliteImage]:
        try:
            client = Client.open(self._api_url)
            search = client.search(
                collections=[self._collection],
                bbox=[footprint.west, footprint.south, footprint.east, footprint.north],
                query={"eo:cloud_cover": {"lt": max_cloud_cover_pct}},
                max_items=5,
            )
            items = list(search.items())
        except Exception as exc:  # noqa: BLE001 - pystac-client raises a mix of exception types
            raise ExternalServiceError("STAC", f"search failed: {exc}") from exc

        images = []
        for item in items:
            images.append(
                SatelliteImage.new(
                    thermal_event_id=uuid4(),  # placeholder — overwritten by the use case before persisting
                    stac_item_id=item.id,
                    collection=self._collection,
                    footprint=footprint,
                    acquired_at=item.datetime,
                    cloud_cover_pct=item.properties.get("eo:cloud_cover"),
                )
            )
        return images

    async def download(self, image: SatelliteImage) -> str:
        """
        Downloads configured bands for `image.stac_item_id`, cropped to
        `image.footprint` (the small area around the hotspot, set in
        `search()` — see `BoundingBox.around`), not the full Sentinel-2
        tile (~110x110km, 100MB+ per band). Requires re-resolving the STAC
        item's asset hrefs.
        """
        target_dir = self._cache_dir / image.stac_item_id
        target_dir.mkdir(parents=True, exist_ok=True)

        client = Client.open(self._api_url)
        item = client.get_collection(self._collection).get_item(image.stac_item_id)
        if item is None:
            raise ExternalServiceError("STAC", f"item not found: {image.stac_item_id}")

        for band in self._bands:
            asset_key = _BAND_CODE_TO_EARTH_SEARCH_ASSET.get(band, band)
            asset = item.assets.get(asset_key) or item.assets.get(band)
            if asset is None:
                logger.warning(
                    "band %s (asset key %r) not found on STAC item %s — available: %s",
                    band, asset_key, item.id, sorted(item.assets.keys()),
                )
                continue
            dest = target_dir / f"{band}.tif"
            if not dest.exists():
                await asyncio.to_thread(self._download_windowed, asset.href, dest, image.footprint)

        return str(target_dir)

    @retry(
        retry=retry_if_exception_type(rasterio.errors.RasterioIOError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _download_windowed(self, url: str, dest: Path, footprint: BoundingBox) -> None:
        """
        Crops directly from the remote Cloud-Optimized GeoTIFF via HTTP
        range requests (GDAL's /vsicurl/), so only the pixels covering
        `footprint` are transferred — a few hundred KB instead of the
        full band file. Runs in a worker thread since rasterio/GDAL I/O
        is blocking (see `asyncio.to_thread` call site).
        """
        with rasterio.Env(
            GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
            GDAL_HTTP_MULTIPLEX="YES",
        ):
            with rasterio.open(f"/vsicurl/{url}") as src:
                west, south, east, north = transform_bounds(
                    "EPSG:4326", src.crs,
                    footprint.west, footprint.south, footprint.east, footprint.north,
                )
                window = from_bounds(west, south, east, north, transform=src.transform)
                data = src.read(1, window=window)
                profile = src.profile.copy()
                profile.update(
                    height=data.shape[0],
                    width=data.shape[1],
                    transform=src.window_transform(window),
                )

            with rasterio.open(dest, "w", **profile) as dst:
                dst.write(data, 1)
