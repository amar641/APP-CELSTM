# ADR-004: No LLM in the core pipeline (v1)

## Status
Accepted

## Context
The original pitch envisioned an LLM/multi-agent layer for narrative
explanation or fusion. LLM calls are slow, non-deterministic, costly, and
hard to make reproducible for a classification pipeline whose job is to
produce a defensible, auditable label + risk score from computable
signals (FRP, facility distance, persistence, weather, imagery).

## Decision
No LLM anywhere in the v1 core pipeline (ingestion → enrichment →
satellite → feature assembly → CELSTM → risk → API). `ClassificationResult.reasoning`
is generated deterministically by whichever `ClassificationStrategy` ran
(`RuleBasedClassifier` today, `CELSTMClassifier` later) from the same
computed features that drove the label — never from a model call.

## Consequences
- Every classification is reproducible: same inputs, same output, every
  time. Required for model evaluation and for defending a classification
  to an analyst.
- The design deliberately leaves room for an LLM *enrichment/explanation*
  service later — e.g. turning `ClassificationResult` + `RiskAssessment`
  into a longer natural-language brief for an analyst — as an additive
  service downstream of the API/domain, not a dependency of it. Adding
  one means a new `application`/`api` module that *reads* existing
  results; it does not touch `domain`, `ml`, or the classification path.
