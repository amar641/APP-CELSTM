# XGBoost — the second classifier

`ml.models.xgboost_classifier` / `ml.inference.predict_xgboost.XGBoostClassifier`.
Runs alongside CE-LSTM in the continuous pipeline
(`application.pipeline.continuous_pipeline.ContinuousPipeline`) — every
hotspot gets classified by both, independently, and both
`ClassificationResult` rows are persisted (`model_source` distinguishes
them). Neither replaces the other; the dashboard shows both.

## Why a second, deliberately different model

CE-LSTM's sequential consensus/entropy machinery is designed for a
hotspot with several evidence *rounds* (satellite retrievals) whose
signals actually change round to round. In practice most of the
structured signals (thermal, facility proximity, persistence, weather)
are the **same value repeated on every round** — only the vision
embedding varies — and most hotspots get 0-1 satellite passes before
classification is needed (see [celstm.md](celstm.md#missing-sources) and
[feature-contract.md](feature-contract.md)). A gradient-boosted tree
ensemble has no need for that sequence structure at all, handles missing
sources (no facility, no weather, no imagery) natively without the
availability-masking CE-LSTM needs, and gives feature importances for
free — a genuinely different inductive bias and a useful second opinion,
not just an ensemble of near-identical models.

## Inputs

One flat feature vector per event, no rounds/sequence:

- Structured features, same order as CE-LSTM's structured branch
  (`ml.features.feature_schema.FEATURE_ORDER`): `frp_mw`,
  `facility_distance_km`, `persistence_count`, `frp_deviation_pct`,
  `temperature_c`, `wind_speed_ms`, `wind_direction_deg`,
  `relative_humidity_pct`.
- A deterministic mean-pooled reduction of the satellite vision embedding
  (`ml.features.vision_pooling.pool_embedding`, default 32 buckets from
  the 512-dim embedding) — zeros when no imagery has been retrieved yet.
  Deliberately *not* a fitted transform (PCA, autoencoder): no second
  artifact to version/promote alongside the model checkpoint, consistent
  with this project's general preference for analytic-over-learned
  reduction wherever the reduction doesn't need to be learned.

See `ml.models.xgboost_classifier.build_feature_vector`.

## Training vs. inference

- **Training** (`scripts/training/train_xgboost.py` →
  `ml.training.train_xgboost.train_xgboost`): same weak-label bootstrap as
  CE-LSTM — every thermal event with an existing `classification_results`
  row becomes one labeled example (see [dataset.md](dataset.md)). Trains
  an `XGBClassifier` with `class_weight="balanced"` sample weights (not
  oversampling) to handle the same class imbalance CE-LSTM's dataset docs
  describe. Writes `model.joblib` + `metrics.json` to a timestamped
  `MODEL_REGISTRY_DIR/xgboost-<ts>/` directory.
- **Inference**: `XGBoostClassifier.classify()` — falls back to
  `RuleBasedClassifier` when no checkpoint exists yet, identically to
  `CELSTMClassifier`.

## Status

Implemented and wired into the continuous pipeline; falls back to
rule-based until `scripts/training/train_xgboost.py` has produced a
checkpoint. Same promotion bar as CE-LSTM applies before either replaces
the rule-based classifier as anything more than "a second opinion shown
alongside it" — see [evaluation.md](evaluation.md).
