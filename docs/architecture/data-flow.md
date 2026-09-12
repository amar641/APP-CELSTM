# Data Flow

```
NASA FIRMS ──┐
OSM/Overpass ─┼─> Ingestion use cases ─> PostgreSQL/PostGIS (system of record)
Weather ─────┘

PostgreSQL (thermal_events, facilities)
        │
        ▼
Spatial enrichment (application.enrichment.SpatialEnrichmentUseCase)
   - ProximityService: nearest facility + distance
   - PersistenceService: repeat-detection count + FRP deviation
        │
        ▼
Satellite retrieval (application.satellite.RetrieveSatelliteImageryUseCase)
   - STAC search + download (infrastructure.satellite)
   - Preprocessing (ml.features / infrastructure.satellite)
   - Vision feature extraction (ml.encoders.VisionEncoder)
        │              │
        ▼              ▼
Structured features   Embedding vector
(Postgres:             (Qdrant, keyed by
 satellite_images)      SatelliteImage.id)
        │              │
        └──────┬───────┘
               ▼
Feature assembly (application.feature_assembly.AssembleFeaturesUseCase)
   - joins structured features + weather + vision embedding into a
     FeatureBundle per timestep
               ▼
Classification (application.classification.ClassifyEventUseCase)
   - v1: RuleBasedClassifier (transparent thresholds)
   - v2: ml.inference.predict.CELSTMClassifier (same ClassificationStrategy port)
               ▼
Risk assessment (application.risk.AssessRiskUseCase)
               ▼
GIS API (api.routes.events) ─> GIS dashboard (frontend/)
```

## Idempotency & provenance

- `ThermalEvent.natural_key` (lat/lon rounded, `acquired_at`, `source`)
  backs a unique index so re-running ingestion never duplicates rows —
  see `infrastructure.database.repositories.thermal_event_repository`'s
  `ON CONFLICT DO NOTHING` upsert.
- Every `ClassificationResult` records `model_source` + `model_version`,
  so rule-based and CELSTM outputs remain distinguishable and comparable
  even after CELSTM becomes the default.
