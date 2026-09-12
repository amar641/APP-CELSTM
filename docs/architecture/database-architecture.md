# Database Architecture

PostgreSQL + PostGIS is the **system of record** for every entity in the
domain layer (see [ADR-001](decisions/ADR-001-postgresql-postgis.md)).
Qdrant holds *only* embedding vectors, keyed by the same UUIDs Postgres
uses — see [ADR-002](decisions/ADR-002-qdrant.md).

## Tables (`migrations/versions/0001_initial_schema.py`)

| Table | Purpose | Geometry |
|---|---|---|
| `thermal_events` | FIRMS detections | `location GEOGRAPHY(POINT)` |
| `facilities` | OSM industrial infrastructure | `location GEOGRAPHY(POINT)` |
| `weather_observations` | Weather joined by space/time | `location GEOGRAPHY(POINT)` |
| `satellite_images` | STAC image metadata + structured vision features (JSONB) | `footprint GEOGRAPHY(POLYGON)` |
| `classification_results` | Model output + provenance (`model_source`, `model_version`) | — |
| `risk_assessments` | Risk score/level derived from a classification | — |

All geometry columns use `GEOGRAPHY` (not `GEOMETRY`) so distance queries
(`ST_DWithin`, `ST_Distance`) return real-world meters directly without
manual projection — this is what backs `ProximityService` and
`PersistenceService` in the domain layer. GIST indexes on every geometry
column keep those queries fast at scale.

## Idempotent ingestion

`thermal_events` has a unique index on `(acquired_at, source, location)`;
ingestion upserts with `ON CONFLICT DO NOTHING`. `facilities` uniques on
`osm_id` and upserts with `ON CONFLICT DO UPDATE` so re-running OSM
ingestion refreshes name/location without creating duplicates.

## Migrations

Alembic (`migrations/`) is the only way schema changes ship — no
`Base.metadata.create_all()` in application code. `migrations/env.py`
reads `DATABASE_URL` from `core.config.Settings`, so app config and
migration config never drift apart.
