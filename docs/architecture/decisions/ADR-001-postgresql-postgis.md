# ADR-001: PostgreSQL + PostGIS as the system of record

## Status
Accepted

## Context
The platform's core entities (thermal events, facilities, weather
observations, satellite image metadata, classification/risk results) are
all geospatial and relational: they need joins, transactional writes,
strong schemas, and proximity/containment queries (nearest facility,
detections within a radius, images intersecting a footprint).

## Decision
Use PostgreSQL with the PostGIS extension as the single system of record
for all structured and geospatial data. `GEOGRAPHY` columns back distance
queries in real-world meters; GIST indexes keep them fast.

## Consequences
- One transactional store for everything except embeddings — no
  eventual-consistency concerns between "the data" and "the geometry."
- SQLAlchemy 2.x + GeoAlchemy2 + Alembic give typed models and versioned
  migrations (see [database-architecture.md](../database-architecture.md)).
- Horizontal read scaling later (read replicas, Citus) is a deployment
  change, not an architecture change.
