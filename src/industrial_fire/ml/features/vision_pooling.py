"""
Deterministic reduction of the 512-dim satellite vision embedding for
tabular models (XGBoost) that have no natural way to consume a raw
high-dimensional embedding the way CE-LSTM's learned vision head does.

Mean-pooling over fixed contiguous chunks, not a fitted transform (PCA,
autoencoder, ...) — no second artifact to version/promote alongside the
model checkpoint, consistent with this project's preference for analytic
over learned squashing wherever the squash doesn't need to be learned
(see ml.features.source_signals).
"""

from __future__ import annotations

import numpy as np

DEFAULT_POOLED_DIM = 32


def pool_embedding(
    embedding: np.ndarray | None, source_dim: int, num_buckets: int = DEFAULT_POOLED_DIM
) -> np.ndarray:
    """Mean-pool `embedding` into `num_buckets` values; zeros if `embedding` is None."""
    if embedding is None:
        return np.zeros(num_buckets, dtype=np.float32)
    chunks = np.array_split(np.asarray(embedding, dtype=np.float32)[:source_dim], num_buckets)
    return np.array([chunk.mean() if chunk.size else 0.0 for chunk in chunks], dtype=np.float32)
