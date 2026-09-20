# Data Flow

The pipeline runs continuously in-process, not per-request — see
[`application.pipeline.continuous_pipeline.ContinuousPipeline`](../../src/industrial_fire/application/pipeline/continuous_pipeline.py),
started from `api/main.py`'s FastAPI `lifespan` and polling on
`configs/app.yaml:ingestion.pipeline.poll_interval_seconds`. The API's
`GET /api/v1/events`/`GET /api/v1/events/{id}` are pure reads of what
this loop has already written to Postgres.

```
Every poll_interval_seconds:
  NASA FIRMS (whole AOI) ─> IngestThermalEventsUseCase ─> thermal_events (Postgres)
        │
        ▼
  For each event with NO classification_results row yet (the "new hotspot" gate):
        │
        ├─> OSM/Overpass, scoped to a small BoundingBox.around(event.location)
        │       ─> IngestFacilitiesUseCase ─> facilities (Postgres)
        │   Weather, same per-hotspot scoping ─> IngestWeatherUseCase ─> weather_observations
        │   (never the whole AOI — that stays a manual-only operation via
        │   POST /facilities/refresh)
        │
        ▼
  Spatial enrichment (application.enrichment.SpatialEnrichmentUseCase)
     - ProximityService: nearest facility + distance
     - PersistenceService: repeat-detection count + FRP deviation
        │
        ▼
  Satellite retrieval (application.satellite.RetrieveSatelliteImageryUseCase), best-effort
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
               ▼
  Classification — BOTH run, independently, every hotspot:
     - ml.inference.predict.CELSTMClassifier       ─┐
     - ml.inference.predict_xgboost.XGBoostClassifier ┴─> ClassifyEventUseCase
       (each falls back to RuleBasedClassifier until its own checkpoint is trained)
               ▼
  Risk assessment (application.risk.AssessRiskUseCase), once per classification result
               ▼
  classification_results + risk_assessments (Postgres)
               ▼
  GIS API (api.routes.events) ─> GIS dashboard (frontend/, served by this same app)
```

## Idempotency & provenance

- `ThermalEvent.natural_key` (lat/lon rounded, `acquired_at`, `source`)
  backs a unique index so re-running ingestion never duplicates rows —
  see `infrastructure.database.repositories.thermal_event_repository`'s
  `ON CONFLICT DO UPDATE` upsert (touches `ingested_at` so the caller
  always gets back the row's real, persisted id — see that file's
  docstring for why `DO NOTHING` would silently break every downstream
  foreign key).
- Every `ClassificationResult` records `model_source` + `model_version`
  (`rule_based_v1`, `celstm_v1`, `xgboost_v1`), plus that checkpoint's
  offline `model_precision`/`recall`/`accuracy`/`f1_macro` and a derived
  `is_abnormal` flag — so CELSTM and XGBoost outputs for the same hotspot
  stay independently comparable and auditable on the dashboard, not just
  in the database.
