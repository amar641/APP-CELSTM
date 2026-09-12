# System Context

Industrial Fire AI ingests data about thermal anomalies and the industrial
infrastructure/weather/imagery around them, and produces a classified,
risk-scored feed of events for analysts via a GIS API and dashboard.

## Actors

- **Analyst / operator** — consumes the GIS dashboard and API to triage
  thermal events (industrial fire vs. routine flare vs. wildfire vs. unknown).
- **Scheduler / ops** — runs ingestion scripts (`scripts/ingest/`) on a
  cadence to keep FIRMS/OSM/weather data current.
- **ML engineer** — trains and evaluates CELSTM checkpoints offline
  (`scripts/training/`), independent of the running API.

## External systems

| System | Role | Adapter |
|---|---|---|
| NASA FIRMS | Thermal hotspot detections (VIIRS/MODIS) | `infrastructure/firms` |
| OpenStreetMap / Overpass | Industrial facility geometry | `infrastructure/osm` |
| Weather provider (Open-Meteo default) | Wind/temperature/humidity context | `infrastructure/weather` |
| STAC catalog (Earth Search / Sentinel-2 default) | Satellite imagery discovery + download | `infrastructure/satellite` |
| PostgreSQL + PostGIS | System of record for all structured/geospatial data | `infrastructure/database` |
| Qdrant | Similarity index over satellite-image embeddings | `infrastructure/qdrant` |

Every external system is accessed through a narrow adapter implementing a
port defined in the `application` layer — see
[container-architecture.md](container-architecture.md) and
[ADR-003](decisions/ADR-003-layered-architecture.md).

## Out of scope for v1

- LLM-based enrichment/explanation — see
  [ADR-004](decisions/ADR-004-no-llm-v1.md).
- Mobile/Android client (API is designed to support one later; not built here).
- Multi-tenant auth — v1 assumes a single trusted deployment.
