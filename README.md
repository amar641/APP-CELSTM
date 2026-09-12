# Industrial Fire AI

AI-based detection and classification of industrial fires and persistent thermal
sources, built on NASA FIRMS thermal detections, OpenStreetMap industrial
infrastructure, weather observations, and satellite imagery.

This is an **architecture-first, layered platform** — not a script collection.
See [`docs/architecture/`](docs/architecture/) for the full design and
[Architecture Decision Records](docs/architecture/decisions/) for why key
choices (PostGIS as system of record, Qdrant as a similarity index only, no
LLM in the v1 core pipeline) were made.

## Pipeline

```
Data sources (FIRMS, OSM, Weather, STAC satellite)
        -> Ingestion
        -> PostgreSQL + PostGIS (system of record)
        -> Spatial enrichment (facility proximity, persistence)
        -> Satellite retrieval + preprocessing
        -> Vision feature extractor -> structured features (Postgres) + embeddings (Qdrant)
        -> Feature assembly (multimodal, temporal)
        -> CELSTM classification + risk scoring
        -> GIS API -> GIS dashboard
```

See [docs/architecture/data-flow.md](docs/architecture/data-flow.md) for the
detailed flow and [docs/architecture/container-architecture.md](docs/architecture/container-architecture.md)
for how the containers/services fit together.

## Repository layout

```
src/industrial_fire/
├── core/            # config, logging, exceptions, shared types
├── domain/          # entities, value objects, repository interfaces, domain services
├── application/     # use cases: ingestion, enrichment, satellite, feature assembly,
│                     classification, risk — orchestrates domain + infrastructure
├── infrastructure/   # concrete adapters: Postgres/PostGIS, FIRMS, OSM, weather,
│                     satellite/STAC, Qdrant
├── ml/               # datasets, feature encoders, CELSTM model, training/inference/eval
└── api/              # FastAPI app, routes, request/response schemas
```

`application` depends on `domain` interfaces, never on concrete `infrastructure`
classes directly — wiring happens in `api/dependencies.py` and `scripts/`.
This lets any provider (FIRMS -> another thermal source, Qdrant -> another
vector DB, the rule-based classifier -> CELSTM) be swapped without touching
the layers around it.

## Getting started

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker + Docker Compose (for Postgres/PostGIS + Qdrant)

### Setup

```bash
cp .env.example .env        # fill in FIRMS_MAP_KEY and any other secrets
uv sync --extra dev
docker compose up -d postgres qdrant
uv run alembic upgrade head
```

### Run the API

```bash
uv run uvicorn industrial_fire.api.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API docs, or
http://127.0.0.1:8000/api/v1/events for classified thermal events.

### Run tests / lint / typecheck

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

### Ingest data manually

```bash
uv run python scripts/ingest/ingest_firms.py
uv run python scripts/ingest/ingest_osm.py
uv run python scripts/seed/seed_facilities.py
```

## Status

The v1 slice ported from the original MVP is a **rule-based classifier**
(facility proximity + persistence + FRP deviation) running through the same
domain/application/infrastructure boundaries the CELSTM model will use once
trained — see [docs/ml/celstm.md](docs/ml/celstm.md) for the model design and
[docs/architecture/decisions/ADR-004-no-llm-v1.md](docs/architecture/decisions/ADR-004-no-llm-v1.md)
for why an LLM is intentionally excluded from the core pipeline in v1.

## License

See [LICENSE](LICENSE).
