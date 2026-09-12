# Dataset

`ml.datasets.thermal_sequence_dataset.ThermalSequenceDataset` wraps a list
of `LabeledSequence(rounds: list[FeatureBundle], label: ClassificationLabel)`
— one `FeatureBundle` per **round** (a satellite-image retrieval for that
hotspot), not per calendar day. See [celstm.md](celstm.md) for why rounds
map to satellite retrievals rather than a fixed lookback window.

## Building training data

`scripts/training/train_celstm.py:_load_labeled_sequences` does this end
to end today as a bootstrap:

1. Query every thermal event that already has a `classification_results`
   row — currently rule-based output, since no analyst-reviewed labels
   exist yet. This is a legitimate but weak label source: training CE-LSTM
   to imitate the rule-based classifier bounds it at that classifier's
   own accuracy. Replace with analyst-corrected labels as they accumulate.
2. For each, call `AssembleFeaturesUseCase.execute_sequence(event)` — one
   `FeatureBundle` per satellite image retrieved for that hotspot, oldest
   → newest, each carrying that round's own vision embedding (pulled from
   Qdrant) plus the event's shared structured signals.
3. Wrap in a `LabeledSequence` and hand the list to `ThermalSequenceDataset`.

A hotspot with zero satellite imagery still yields a valid one-round
sample (`execute_sequence` returns a single vision-less round rather than
an empty list) — see `ml.features.source_signals` for how a round with no
vision source degrades gracefully instead of crashing.

## Padding

Sequences shorter than `sequence_length` are zero-padded at the *front*
(`ThermalSequenceDataset.__getitem__`), keeping the most recent round
last — CE-LSTM reads out its classification from the hive state after the
final round, so the newest, most informative round must land there.

## Class balance

v1 has four classes (`ClassificationLabel`); gas flares/normal industrial
heat will vastly outnumber confirmed fires in most AOIs. Address with
class-weighted loss or oversampling in `ml.training.train` before relying
on raw accuracy — see [evaluation.md](evaluation.md) for why macro-F1 is
tracked alongside accuracy.
