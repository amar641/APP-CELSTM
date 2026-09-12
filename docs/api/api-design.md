# API Design

FastAPI app: `industrial_fire.api.main:app`. All routes are versioned
under `/api/v1` (`API_PREFIX` in `main.py`) so a future `/api/v2` can
coexist during a breaking change.

## Endpoints (v1)

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/health` | Liveness check |
| GET | `/api/v1/events` | Pulls today's FIRMS detections for the AOI, enriches, classifies, scores risk; sorted highest-risk first |
| GET | `/api/v1/facilities` | Facilities already ingested into Postgres, within the AOI |
| POST | `/api/v1/facilities/refresh` | Re-fetches facilities from OSM/Overpass and upserts |

Interactive docs at `/docs` (Swagger) and `/redoc`.

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

## Future: GIS dashboard

`frontend/` is a placeholder for a Leaflet/Mapbox dashboard that consumes
`/api/v1/events` and `/api/v1/facilities` directly — no separate
backend-for-frontend is planned; the dashboard is a pure client of this API.
