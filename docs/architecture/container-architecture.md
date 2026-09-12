# Container / Layer Architecture

## Runtime containers (`compose.yaml`)

- **api** — FastAPI app (`industrial_fire.api.main:app`). Stateless; all
  state lives in Postgres/Qdrant.
- **postgres** — `postgis/postgis` image. System of record.
- **qdrant** — embedding similarity index only (see
  [ADR-002](decisions/ADR-002-qdrant.md)).

Offline (not in `compose.yaml`, run on demand):
- **ingestion scripts** (`scripts/ingest/*.py`) — pull FIRMS/OSM/weather.
- **training job** (`scripts/training/train_celstm.py`) — produces a
  versioned checkpoint under `MODEL_REGISTRY_DIR`.

## Code layers (`src/industrial_fire/`)

```
api            ← depends on → application ← depends on → domain
infrastructure ← depends on → domain              ^
ml             ← depends on → application, domain ┘
```

- **domain** — entities, value objects, repository *interfaces*, pure
  domain services. Zero dependencies on frameworks, DBs, or HTTP.
- **application** — use cases that orchestrate domain logic + repository/
  provider *interfaces* ("ports"). Defines the ports infrastructure
  implements (`ThermalEventProvider`, `FacilityProvider`, `WeatherProvider`,
  `SatelliteImageProvider`, `ClassificationStrategy`, ...).
- **infrastructure** — concrete adapters: SQLAlchemy/PostGIS repositories,
  FIRMS/Overpass/weather/STAC HTTP clients, the Qdrant client. Implements
  application-layer ports; never imported by `domain`.
- **ml** — datasets, feature schema, CELSTM model, training/inference/eval.
  `ml.inference.predict.CELSTMClassifier` implements the same
  `ClassificationStrategy` port as `application.classification.RuleBasedClassifier`,
  so swapping the model doesn't touch the API or persistence.
- **api** — FastAPI routes + Pydantic schemas + `dependencies.py`
  (the composition root wiring infrastructure into application use cases).

This is the "ports and adapters" / hexagonal shape applied with the
project's own naming, per [ADR-003](decisions/ADR-003-layered-architecture.md).

## Why this shape

- Swap FIRMS for another thermal source: implement `ThermalEventProvider`,
  change one line in `api/dependencies.py`.
- Swap the rule-based classifier for CELSTM: implement
  `ClassificationStrategy`, change one line in `api/dependencies.py`.
- Swap Qdrant for another vector store: implement the same repository
  shape in a new `infrastructure/<store>` package; `application` never
  imports `qdrant_client` directly (only `infrastructure.qdrant` does).
