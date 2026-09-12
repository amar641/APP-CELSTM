"""
Shared exception hierarchy.

Each layer raises the most specific subclass relevant to it. The API layer
(`api/main.py` exception handlers) maps these to HTTP responses, so
`infrastructure`/`application` code should never raise raw `HTTPException`.
"""

from __future__ import annotations


class IndustrialFireError(Exception):
    """Base class for all application-raised errors."""


# --- Domain -----------------------------------------------------------
class DomainError(IndustrialFireError):
    """Invalid domain state or business-rule violation."""


class EntityNotFoundError(DomainError):
    """A requested domain entity does not exist."""


# --- Application / use case --------------------------------------------
class UseCaseError(IndustrialFireError):
    """An application use case could not complete."""


# --- Infrastructure -----------------------------------------------------
class InfrastructureError(IndustrialFireError):
    """A dependency (DB, external API, vector store) failed."""


class ExternalServiceError(InfrastructureError):
    """An upstream data provider (FIRMS, Overpass, weather, STAC) failed or is unavailable."""

    def __init__(self, service: str, message: str) -> None:
        self.service = service
        super().__init__(f"{service}: {message}")


class RepositoryError(InfrastructureError):
    """A persistence operation (Postgres or Qdrant) failed."""


# --- ML -----------------------------------------------------------------
class MLError(IndustrialFireError):
    """Model loading, inference, or training failure."""


class ModelNotFoundError(MLError):
    """No trained model artifact found in the model registry."""


class FeatureAssemblyError(MLError):
    """Required features could not be assembled for inference/training."""
