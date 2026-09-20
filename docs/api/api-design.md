# API Design

FastAPI app: `industrial_fire.api.main:app`. All routes are versioned
under `/api/v1` (`API_PREFIX` in `main.py`) so a future `/api/v2` can
coexist during a breaking change.

## Endpoints (v1)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| GET | `/api/v1/events` | Reads already-ingested/classified events from Postgres (the continuous pipeline keeps this current — see [data-flow.md](../architecture/data-flow.md)); `days_back` filters on `acquired_at`. Sorted highest-risk first. Each event carries a `classifications` list — one entry per model that has run (CELSTM, XGBoost, or the rule-based fallback) |
| GET | `/api/v1/events/{id}` | Full detail for one event: fire representation, satellite evidence, temporal history, and the same `classifications` list — backs the dashboard's click panel |
| GET | `/api/v1/facilities` | Facilities already ingested into Postgres, within the AOI |
| POST | `/api/v1/facilities/refresh` | Re-fetches facilities from OSM/Overpass and upserts (manual, whole-AOI — the continuous pipeline only ever ingests facilities/weather scoped to a single hotspot) |
| GET | `/api/v1/aoi` | The configured AOI as a GeoJSON polygon (from `AOI_BBOX`), for the dashboard's boundary overlay |
| GET | `/api/v1/pipeline/status` | Continuous-pipeline health: last poll time, hotspots processed, last error |

Interactive docs at `/docs` (Swagger) and `/redoc`.

**Note**: `/events` and `/events/{id}` no longer trigger live ingestion —
that's now the continuous background pipeline's job
(`application.pipeline.continuous_pipeline.ContinuousPipeline`, started
from `api/main.py`'s lifespan). These routes are now cheap, poll-friendly
DB reads.

## Composition root

`api/dependencies.py` is the only place concrete `infrastructure` classes
are imported into the API layer. Routes depend on `application` use cases
via `Depends(...)`, never on repositories or provider clients directly —
see [container-architecture.md](../architecture/container-architecture.md).

## Error handling

`core.exceptions` defines a typed hierarchy; `api/main.py` registers
exception handlers mapping them to HTTP status codes:

| Exception | HTTP status |
|---|---|
| `EntityNotFoundError` | 404 |
| `ExternalServiceError` | 502 |
| `RepositoryError` | 503 |
| `IndustrialFireError` (catch-all) | 500 |

Route handlers never raise raw `HTTPException` for domain/infrastructure
failures — they let the typed exception propagate and the global handler
maps it, keeping error semantics consistent across every route.

## Schemas

Request/response models live in `api/schemas/`, separate from domain
entities — the API's wire format is allowed to diverge from the domain
model (e.g. flattening `Coordinates` into `latitude`/`longitude` fields)
without that leaking into `domain`.

## GIS dashboard

`frontend/` is a MapLibre GL JS + Vite dashboard, built and served
directly by this app (`StaticFiles` mount in `api/main.py`) — no separate
frontend service or backend-for-frontend. It's a pure client of the API
above; see [frontend/README.md](../../frontend/README.md).
