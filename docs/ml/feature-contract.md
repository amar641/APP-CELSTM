# Feature Contract

The frozen boundary between `application.feature_assembly.FeatureBundle`
and CE-LSTM's inputs (`ml.models.celstm.CELSTM`). Defined in
`ml.features.source_signals`. **Changing this is a breaking change to any
existing trained checkpoint** — bump `configs/model.yaml:model.name` and
retrain rather than editing in place. See [celstm.md](celstm.md) for the
full HMNN-paper-to-project mapping this contract implements.

## Structured sources (`SOURCE_ORDER`)

Each of the 4 structured sources is squashed into `(decision, intensity,
available) ∈ [0,1]² × {0,1}` by a pure function in
`ml.features.source_signals` — no learned weights, matching the paper's
"analytic, not gated" design:

| # | Source | Derived from | Unavailable when |
|---|---|---|---|
| 0 | `thermal` | `frp_mw`, `frp_deviation_pct` | never (FIRMS data is always present) |
| 1 | `facility_proximity` | `facility_distance_km` | no facility found in the AOI at all |
| 2 | `persistence` | `persistence_count` | never (always computed, even if 0) |
| 3 | `weather` | `wind_speed_ms` | no weather observation matched in space/time |

A 5th, **vision** source is appended by the model itself
(`CELSTM.vision_head`), projected from the raw satellite embedding rather
than an analytic squash — see [celstm.md](celstm.md) for why.

Unavailable sources are excluded from the consensus/entropy computation
entirely (not treated as a vote of 0) — see
`tests/unit/test_celstm_model.py::test_unavailable_sources_are_excluded_from_consensus`.

## Vision embedding

512-dim vector (`configs/model.yaml:architecture.vision_embedding_dim`)
from `ml.encoders.VisionEncoder`, one per `SatelliteImage`, fetched from
Qdrant by `AssembleFeaturesUseCase.execute_sequence`. Zero-filled with
`vision_available=False` for a round with no imagery.

## Rounds (formerly "timesteps")

CE-LSTM consumes up to `sequence_length` (default 8) **rounds** —
one per satellite-image retrieval for a hotspot, oldest first, most
recent last (see [celstm.md](celstm.md#the-mapping-to-this-project)).
[dataset.md](dataset.md) covers how training sequences are built;
`ml.inference.predict.CELSTMClassifier` covers zero-padding at inference
when fewer rounds exist than `sequence_length`.
