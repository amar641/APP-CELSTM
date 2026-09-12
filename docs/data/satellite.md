# Satellite Imagery

**Adapter:** `infrastructure.satellite.stac_client.StacSatelliteImageProvider`
(implements `application.satellite.retrieve_satellite_imagery.SatelliteImageProvider`)

## Source
Any STAC-compatible catalog via `pystac-client`; default
`STAC_API_URL=https://earth-search.aws.element84.com/v1`,
`STAC_COLLECTION=sentinel-2-l2a`.

## Search → download → preprocess → extract
1. `search()` — STAC item search over the thermal event's footprint,
   filtered by `configs/data.yaml:satellite.max_cloud_cover_pct`.
2. `download()` — fetches configured bands
   (`configs/data.yaml:satellite.bands`, default `B04,B03,B02,B08` =
   red/green/blue/NIR) to `SATELLITE_IMAGE_CACHE_DIR`.
3. Preprocessing (`application.satellite.ImagePreprocessor` port) —
   normalization/cropping before the vision encoder runs.
4. `ml.encoders.VisionEncoder.extract()` — produces structured features
   (band statistics, NDVI-like ratios) stored in Postgres, and an
   embedding vector stored in Qdrant.

## Storage split
Structured features live on `SatelliteImage.structured_features` (JSONB,
Postgres). The embedding vector is written separately to Qdrant, keyed by
`SatelliteImage.id` — see [ADR-002](../architecture/decisions/ADR-002-qdrant.md).
`SatelliteImage.has_embedding` flags whether that write has happened.
