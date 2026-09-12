# ADR-003: Layered (ports-and-adapters) architecture

## Status
Accepted

## Context
The platform combines several independently-evolving concerns: multiple
external data providers, a relational+geospatial store, a vector store,
a PyTorch model that will be retrained and re-versioned, and a public
API/dashboard. Coupling these together (as the original MVP's
`app/main.py` importing `firms_client`, `facilities`, `scoring` directly
did) makes every provider swap, model swap, or storage swap a rewrite.

## Decision
Split the codebase into five layers with one-directional dependencies:

```
api → application → domain
infrastructure → domain
ml → application, domain
```

- `domain` defines entities, value objects, and repository *interfaces*.
  It has no dependency on any other layer.
- `application` defines use cases and the *ports* (abstract provider/
  strategy interfaces) that external systems must implement, e.g.
  `ThermalEventProvider`, `ClassificationStrategy`.
- `infrastructure` implements those ports concretely (SQLAlchemy repos,
  HTTP clients, Qdrant client). It depends on `domain` and `application`
  interfaces, never the other way around.
- `ml` implements `ClassificationStrategy` (CELSTM) the same way
  `application.classification.RuleBasedClassifier` does, so the model can
  be swapped without touching `api` or persistence.
- `api` wires concrete `infrastructure` classes into `application` use
  cases in `api/dependencies.py` (the composition root) — routes only
  ever depend on use cases.

## Consequences
- Any external dependency (FIRMS, Overpass, weather provider, STAC
  catalog, Qdrant, the classifier itself) can be replaced by adding a new
  adapter and changing one line in `api/dependencies.py`.
- Unit tests for `domain`/`application` need no database, no HTTP, no
  GPU — they run against fakes implementing the same interfaces.
- More files and indirection than a script-per-task approach; justified
  by this being a multi-year platform, not a one-off demo.
