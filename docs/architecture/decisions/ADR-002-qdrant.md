# ADR-002: Qdrant for embeddings, never the system of record

## Status
Accepted

## Context
CELSTM needs a vision embedding per satellite image, and a future
"find visually similar past events" feature needs fast approximate
nearest-neighbor search over those embeddings. Neither is a good fit for
Postgres at scale, but both are exactly what a purpose-built vector
database does well.

## Decision
Use Qdrant to store and search embedding vectors only. Every vector is
keyed by the same `SatelliteImage.id` UUID that Postgres uses — Qdrant
never stores anything Postgres doesn't already know exists.
`infrastructure.qdrant.embedding_repository.QdrantEmbeddingRepository` is
the only code outside `infrastructure/qdrant` that imports `qdrant_client`.

## Consequences
- Qdrant can be wiped and rebuilt from Postgres + cached rasters at any
  time — it holds no data that doesn't have an authoritative source
  elsewhere. This is the boundary that keeps Qdrant *not* the system of
  record.
- If Qdrant is unavailable, structured features and classification still
  work (CELSTM degrades to zero-vector input; the rule-based classifier
  is unaffected) — see `ml.inference.predict.CELSTMClassifier`'s fallback.
- Swapping Qdrant for another vector store means implementing the same
  narrow repository interface in a new `infrastructure/<store>` package.
