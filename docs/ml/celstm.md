# CE-LSTM — Consensus-Entropy LSTM

`ml.models.celstm.CELSTM`. An adaptation of the **Hive Mind Neural
Network (HMNN)** architecture (Singh & Das, *Hive Mind Neural Network: A
Neural Architecture for Modeling Collective Decision Making via
Consensus, Emotion, and Social Influence*) to thermal-event
classification, kept on disk under this project's original working name,
CELSTM — it is not a convolutional LSTM.

## The paper's idea

HMNN replaces an LSTM's learned sigmoid gates with **analytically
computed** signals derived from a group of voters each round:

- **Consensus Pressure** φ(t) — large when voters agree, ~0 on a near-even
  split, controlled by one learned exponent γ.
- **Emotional Momentum** µ(t) — an EMA of group emotional intensity,
  controlled by one learned decay ρ.
- **Entropy Dampener** η(t) — Shannon entropy of the vote split; high
  uncertainty suppresses the update.

These multiply into `scale(t) = φ(t) · µ(t) · (1 − η(t)) ∈ [0,1]`, which
interpolates a "hive" memory state toward a candidate projected from an
influence-weighted centroid of the votes: `h(t) = h(t-1) + scale(t) ·
(c(t) − h(t-1))`. Only two weight matrices (`Wc/bc`, `Wo/bo`) and the two
scalars (γ, ρ) are learned — everything else is deterministic arithmetic
on the input. The paper's headline result: an LSTM baseline hit 1.00
train / 0.24 test accuracy (severe memorization); HMNN stayed at a much
more modest but *stable* 0.60 / 0.55, because it structurally can't
memorize individual sequences.

## The mapping to this project

| HMNN | This project |
|---|---|
| N=12 human voters | **Evidence sources** about one hotspot: thermal/FRP, facility-proximity, persistence, weather, satellite-vision (`ml.features.source_signals.SOURCE_ORDER` + vision) |
| T=5 decision rounds | **Satellite-image retrievals** for that hotspot over time — each STAC scene found by `RetrieveSatelliteImageryUseCase` is one round (`AssembleFeaturesUseCase.execute_sequence`) |
| voter's decision d_i(t) ∈ {0,1} | source's **decision** ∈ [0,1] — an analytic squash of that source's own signal (e.g. facility distance, wind speed); continuous rather than hard-binary so gradients aren't needed through it but multiple weak signals can still blend |
| voter's emotion e_i(t) ∈ [0,1] | source's **intensity** — the same squash's magnitude reading |
| voter's influence s_i(t) | a **learned per-source-type reliability** (softmaxed), masked by that round's availability (e.g. weather source gets 0 influence on a round with no weather match) instead of a per-round human score |
| group outcome y(t) ∈ {0,1} | one of 4 `ClassificationLabel`s |

The four structured sources (`ml.features.source_signals.structured_signals`)
are pure functions with no learned weights, exactly matching the paper's
"no weight matrix in the consensus/entropy/momentum path" design. The
**vision source is the one necessary deviation**: a raw 512-dim satellite
embedding has no natural analytic squash, so a small learned head
(`CELSTM.vision_head`, two linear layers) projects it to a (decision,
intensity) pair before it enters the same analytic math as every other
source. This is the one place gradients flow into a per-round signal
rather than only through `Wc`/`Wo` — a deliberate, documented departure
from the paper, required to make "feed the embeddings from Qdrant into
the model" mean something.

## Missing sources

Real hotspots don't always have weather, a nearby facility, or (early on)
any satellite imagery. `structured_signals` marks each source
`available: bool`; the model's consensus/entropy math (`ml.models.celstm.CELSTM.forward`)
excludes unavailable sources from the vote count entirely — an "N=4"
round degrades gracefully to "N=2" rather than treating a missing
signal as a vote of 0. Verified in `tests/unit/test_celstm_model.py`.

## Wiring: Qdrant → CE-LSTM → Postgres

1. `RetrieveSatelliteImageryUseCase` writes embeddings to Qdrant, keyed by
   `SatelliteImage.id` (see [ADR-002](../architecture/decisions/ADR-002-qdrant.md)).
2. `AssembleFeaturesUseCase.execute_sequence(event)` reads every
   satellite image for that hotspot, pulls each one's embedding back out
   of Qdrant, and returns one `FeatureBundle` per round.
3. `ml.inference.predict.CELSTMClassifier` converts each round to
   (decisions, intensities, availability, vision embedding) tensors and
   runs `CELSTM.forward`, producing a `ClassificationResult` exactly like
   `RuleBasedClassifier` does.
4. `ClassifyEventUseCase` persists that `ClassificationResult` to Postgres
   (`classification_results`) the same way regardless of which strategy
   ran — CE-LSTM output is cached there identically to rule-based output,
   distinguished only by `model_source`/`model_version`.

Select it with `CLASSIFICATION_STRATEGY=celstm` in `.env`
(`api/dependencies.py:get_classification_strategy`). `CELSTMClassifier`
falls back to `RuleBasedClassifier` automatically when
`MODEL_REGISTRY_DIR` has no checkpoint yet, so flipping this before
training is safe.

## Training vs. inference

- **Training** (`scripts/training/train_celstm.py` → `ml.training.train.train_celstm`):
  bootstraps a labeled set from every thermal event that already has a
  `classification_results` row (rule-based output today; analyst-corrected
  labels later — see [dataset.md](dataset.md)), builds its round sequence
  via `execute_sequence`, and trains with Adam/cross-entropy per
  `configs/model.yaml:training` (mirrors the paper's Table 2: lr=0.001,
  Adam defaults).
- **Inference**: `CELSTMClassifier`, as above.

## Status

Architecture implemented and unit-tested (forward pass, gradient flow,
and the consensus/entropy edge cases — unanimous sources, a perfect
split, and excluded-unavailable-sources — all verified in
`tests/unit/test_celstm_model.py`). No checkpoint has been trained on
real labeled data yet — see [dataset.md](dataset.md) and
[evaluation.md](evaluation.md) for the promotion bar before this replaces
the rule-based classifier as the default.

Runs alongside — not instead of — a second classifier, XGBoost (see
[xgboost.md](xgboost.md)): the continuous pipeline classifies every
hotspot with both, independently, and the dashboard shows both results.
