# Evaluation

`ml.evaluation.metrics.evaluate` runs during training validation and can
be reused standalone for offline evaluation of a saved checkpoint against
a held-out labeled set.

## Metrics tracked

- `loss` — mean cross-entropy over the eval set.
- `accuracy`
- `precision_macro`, `recall_macro`, `f1_macro` — macro-averaged so the
  (likely dominant) gas-flare/normal-industrial class doesn't drown out
  performance on the rarer, higher-stakes classes.
- `confusion_matrix` — full 4x4 breakdown; check this before trusting
  aggregate accuracy on an imbalanced dataset.

## Risk thresholds

`configs/model.yaml:evaluation.risk_thresholds` (`low`/`medium`/`high`)
feed `application.risk.AssessRiskUseCase`, not the classifier itself —
they control the confidence-weighted score → `RiskLevel` mapping and can
be tuned independently of retraining CELSTM.

## Promotion bar

Before `CELSTMClassifier` replaces `RuleBasedClassifier` as the default
in `api/dependencies.py`, a checkpoint should be evaluated against:
1. A held-out set with `f1_macro` and per-class recall at least matching
   the rule-based baseline's, computed on the same set.
2. Manual review of a sample of disagreements between the two
   classifiers — the rule-based reasoning strings make this
   straightforward to audit.

Reproducibility comes from `model_version` (the checkpoint's
timestamped directory name) being recorded on every
`ClassificationResult` — see [ADR-004](../architecture/decisions/ADR-004-no-llm-v1.md).
