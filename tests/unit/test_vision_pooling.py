import numpy as np

from industrial_fire.ml.features.vision_pooling import pool_embedding


def test_none_embedding_pools_to_zeros():
    pooled = pool_embedding(None, source_dim=512, num_buckets=32)
    assert pooled.shape == (32,)
    assert np.all(pooled == 0.0)


def test_pooling_shape_matches_num_buckets():
    embedding = np.arange(512, dtype=np.float32)
    pooled = pool_embedding(embedding, source_dim=512, num_buckets=32)
    assert pooled.shape == (32,)


def test_pooling_is_deterministic():
    embedding = np.random.default_rng(0).random(512).astype(np.float32)
    first = pool_embedding(embedding, source_dim=512, num_buckets=32)
    second = pool_embedding(embedding, source_dim=512, num_buckets=32)
    assert np.array_equal(first, second)


def test_constant_embedding_pools_to_same_constant():
    embedding = np.full(512, 3.0, dtype=np.float32)
    pooled = pool_embedding(embedding, source_dim=512, num_buckets=32)
    assert np.allclose(pooled, 3.0)
