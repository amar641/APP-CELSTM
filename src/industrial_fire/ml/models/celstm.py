"""
CELSTM — Consensus-Entropy LSTM.

An adaptation of the Hive Mind Neural Network (HMNN) architecture
(Singh & Das, "Hive Mind Neural Network: A Neural Architecture for
Modeling Collective Decision Making via Consensus, Emotion, and Social
Influence") to thermal-event classification. HMNN was designed for human
voting rounds; here the "voters" are independent evidence *sources* about
one hotspot, and the "rounds" are that hotspot's satellite-image
retrievals over time (see docs/ml/celstm.md for the full mapping and the
paper reference).

Per round t, each source i contributes (d_i(t), e_i(t)) — an analytic
"decision" and "intensity" derived deterministically from that source's
own signal (see `ml.features.source_signals`) for the four structured
sources, plus a learned projection of the satellite-vision embedding for
the fifth. These combine into three analytically-computed signals, exactly
as in the paper, with NO learned weights:

  - Consensus Pressure  φ(t) — sources agree strongly  -> large
  - Emotional Momentum  µ(t) — sustained signal strength -> large (EMA)
  - Entropy Dampener    η(t) — sources are split/uncertain -> suppresses

scale(t) = φ(t) · µ(t) · (1 − η(t)) ∈ [0, 1] interpolates the hive state
h(t) toward a candidate c(t) projected from the influence-weighted
decision/intensity centroid D(t). Only `Wc, bc, Wo, bo`, the consensus
exponent γ, the momentum decay ρ, per-source reliability weights, and the
vision projection head are learned — everything else is deterministic
arithmetic on the inputs, which is the paper's core anti-overfitting
argument (its LSTM baseline hit 1.00 train / 0.24 test accuracy; HMNN
stayed at 0.60 / 0.55 with no such collapse).
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

from industrial_fire.ml.features.source_signals import NUM_STRUCTURED_SOURCES

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class CELSTMConfig:
    num_structured_sources: int = NUM_STRUCTURED_SOURCES  # thermal, facility, persistence, weather
    vision_embedding_dim: int = 512
    hive_dim: int = 32  # H, per the paper's default
    num_classes: int = 4
    dropout: float = 0.1

    @property
    def total_sources(self) -> int:
        return self.num_structured_sources + 1  # + vision

    @classmethod
    def from_yaml_dict(cls, arch: dict) -> CELSTMConfig:
        return cls(
            num_structured_sources=arch.get("num_structured_sources", NUM_STRUCTURED_SOURCES),
            vision_embedding_dim=arch.get("vision_embedding_dim", 512),
            hive_dim=arch.get("hive_dim", 32),
            num_classes=arch.get("num_classes", 4),
            dropout=arch.get("dropout", 0.1),
        )


class CELSTM(nn.Module):
    def __init__(self, config: CELSTMConfig) -> None:
        super().__init__()
        self.config = config
        n_struct = config.num_structured_sources
        n_total = config.total_sources

        # Vision "voter": projects a raw embedding into (decision, intensity) ∈ [0,1]²,
        # the same shape every other source produces analytically. This is the one
        # place a learned weight touches a per-round signal before the analytic math —
        # necessary because, unlike vote/emotion scalars, a 512-dim embedding has no
        # natural squash.
        self.vision_head = nn.Sequential(
            nn.Linear(config.vision_embedding_dim, 32),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(32, 2),
        )

        # Per-source reliability prior (paper's s_i is a per-voter score fed through
        # softmax; our sources aren't humans with a dynamic influence score, so this
        # is a single learned reliability-per-source-type, softmaxed and masked by
        # that round's availability — see forward()).
        self.source_reliability = nn.Parameter(torch.zeros(n_total))

        # Consensus sensitivity γ = softplus(raw_gamma), init softplus(0) = ln 2,
        # and momentum decay ρ = sigmoid(raw_rho), init sigmoid(0.5) ≈ 0.62 —
        # both exactly the paper's initialization.
        self.raw_gamma = nn.Parameter(torch.tensor(0.0))
        self.raw_rho = nn.Parameter(torch.tensor(0.5))

        # Candidate projection c(t) = ReLU(D(t) Wc + bc), D(t) ∈ R^2 (decision, intensity).
        self.Wc = nn.Linear(2, config.hive_dim)
        # Output readout.
        self.Wo = nn.Linear(config.hive_dim, config.num_classes)

    def forward(
        self,
        structured_decisions: torch.Tensor,  # (B, T, n_struct)
        structured_intensities: torch.Tensor,  # (B, T, n_struct)
        structured_availability: torch.Tensor,  # (B, T, n_struct) in {0,1}
        vision_embeddings: torch.Tensor,  # (B, T, vision_embedding_dim)
        vision_availability: torch.Tensor,  # (B, T) in {0,1}
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        batch, seq_len, _ = structured_decisions.shape
        device = structured_decisions.device
        gamma = nn.functional.softplus(self.raw_gamma)
        rho = torch.sigmoid(self.raw_rho)

        vision_logits = self.vision_head(vision_embeddings)  # (B, T, 2)
        vision_decision = torch.sigmoid(vision_logits[..., 0]) * vision_availability
        vision_intensity = torch.sigmoid(vision_logits[..., 1]) * vision_availability

        decisions = torch.cat([structured_decisions, vision_decision.unsqueeze(-1)], dim=-1)  # (B,T,N)
        intensities = torch.cat([structured_intensities, vision_intensity.unsqueeze(-1)], dim=-1)
        availability = torch.cat([structured_availability, vision_availability.unsqueeze(-1)], dim=-1)

        base_reliability = torch.softmax(self.source_reliability, dim=0)  # (N,)

        h = torch.zeros(batch, self.config.hive_dim, device=device)
        mu_prev: torch.Tensor | None = None
        diagnostics = {"phi": [], "mu": [], "eta": [], "scale": []}

        for t in range(seq_len):
            d_t, e_t, avail_t = decisions[:, t, :], intensities[:, t, :], availability[:, t, :]  # (B,N)
            n_eff = avail_t.sum(dim=-1).clamp(min=1.0)  # (B,) — sources actually present this round

            # Module 2: Consensus Pressure Gate.
            g = (d_t * avail_t).sum(dim=-1)  # "green" vote mass
            r = n_eff - g
            phi = torch.pow((r - g).abs() / n_eff + _EPS, gamma)

            # Module 3: Emotional Momentum (renamed "Signal Momentum" here — see docs/ml/celstm.md).
            e_bar = (e_t * avail_t).sum(dim=-1) / n_eff
            mu = e_bar if mu_prev is None else rho * mu_prev + (1 - rho) * e_bar
            mu_prev = mu

            # Module 4: Vote/Source Entropy Dampener.
            pg = (g / n_eff).clamp(_EPS, 1 - _EPS)
            pr = 1 - pg
            eta = -(pr * torch.log2(pr + _EPS) + pg * torch.log2(pg + _EPS))

            # Module 1: Influence Diffusion — reliability-weighted centroid in (decision, intensity) space.
            w = base_reliability.unsqueeze(0) * avail_t  # (B,N)
            w = w / (w.sum(dim=-1, keepdim=True) + _EPS)
            centroid = torch.stack([d_t, e_t], dim=-1)  # (B,N,2)
            D_t = (w.unsqueeze(-1) * centroid).sum(dim=1)  # (B,2)

            scale = (phi * mu * (1 - eta)).clamp(0.0, 1.0)  # (B,)

            c_t = torch.relu(self.Wc(D_t))  # (B,H)
            h = h + scale.unsqueeze(-1) * (c_t - h)

            diagnostics["phi"].append(phi)
            diagnostics["mu"].append(mu)
            diagnostics["eta"].append(eta)
            diagnostics["scale"].append(scale)

        logits = self.Wo(h)
        diagnostics = {k: torch.stack(v, dim=1) for k, v in diagnostics.items()}  # each (B, T)
        diagnostics["gamma"] = gamma.detach()
        diagnostics["rho"] = rho.detach()
        return logits, diagnostics
