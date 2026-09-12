"""
Sanity checks for the CE-LSTM analytical modules — the parts ported
directly from the HMNN paper's equations (φ, µ, η, scale). These aren't
learned, so bugs here are pure implementation bugs, not training issues.
"""

import torch

from industrial_fire.ml.models.celstm import CELSTM, CELSTMConfig


def _model():
    return CELSTM(CELSTMConfig(num_structured_sources=4, vision_embedding_dim=8, hive_dim=8, num_classes=4))


def test_unanimous_available_sources_maximize_consensus_and_minimize_entropy():
    model = _model()
    B, T, N = 1, 1, 4
    decisions = torch.ones(B, T, N)  # every source agrees
    intensities = torch.ones(B, T, N)
    availability = torch.ones(B, T, N)
    vision = torch.zeros(B, T, 8)
    vision_avail = torch.zeros(B, T)  # vision source absent this round

    _, diag = model(decisions, intensities, availability, vision, vision_avail)
    assert diag["eta"][0, 0].item() < 1e-6  # unanimous -> zero entropy
    assert diag["phi"][0, 0].item() > 0.99  # unanimous -> near-max consensus


def test_perfect_split_maximizes_entropy_and_suppresses_scale():
    model = _model()
    B, T, N = 1, 1, 4
    decisions = torch.tensor([[[1.0, 1.0, 0.0, 0.0]]])  # 2-2 split
    intensities = torch.ones(B, T, N)
    availability = torch.ones(B, T, N)
    vision = torch.zeros(B, T, 8)
    vision_avail = torch.zeros(B, T)

    _, diag = model(decisions, intensities, availability, vision, vision_avail)
    assert diag["eta"][0, 0].item() > 0.99  # 50/50 -> max entropy
    assert diag["scale"][0, 0].item() < 1e-3  # high entropy suppresses the update


def test_unavailable_sources_are_excluded_from_consensus():
    model = _model()
    B, T, N = 1, 1, 4
    decisions = torch.tensor([[[1.0, 1.0, 1.0, 0.0]]])
    intensities = torch.ones(B, T, N)
    # Source 3 (the lone dissenter) is marked unavailable — with it excluded
    # the remaining 3 sources are unanimous.
    availability = torch.tensor([[[1.0, 1.0, 1.0, 0.0]]])
    vision = torch.zeros(B, T, 8)
    vision_avail = torch.zeros(B, T)

    _, diag = model(decisions, intensities, availability, vision, vision_avail)
    assert diag["eta"][0, 0].item() < 1e-6


def test_forward_is_differentiable_and_shapes_are_correct():
    model = _model()
    B, T, N = 3, 5, 4
    decisions = torch.rand(B, T, N)
    intensities = torch.rand(B, T, N)
    availability = torch.ones(B, T, N)
    vision = torch.randn(B, T, 8)
    vision_avail = torch.ones(B, T)

    logits, diag = model(decisions, intensities, availability, vision, vision_avail)
    assert logits.shape == (B, 4)
    for key in ("phi", "mu", "eta", "scale"):
        assert diag[key].shape == (B, T)

    loss = torch.nn.functional.cross_entropy(logits, torch.zeros(B, dtype=torch.long))
    loss.backward()
    assert model.Wc.weight.grad is not None
    assert model.raw_gamma.grad is not None
    assert model.raw_rho.grad is not None
    assert model.vision_head[0].weight.grad is not None
