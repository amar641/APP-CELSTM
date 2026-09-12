"""Structured logging setup, shared by the API, ingestion scripts, and ML jobs."""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "logging.yaml"

_configured = False


def configure_logging() -> None:
    """Idempotently apply configs/logging.yaml. Call once at process startup."""
    global _configured
    if _configured:
        return
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open("r", encoding="utf-8") as f:
            logging.config.dictConfig(yaml.safe_load(f))
    else:
        logging.basicConfig(level=logging.INFO)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced logger. Ensures logging is configured first."""
    configure_logging()
    return logging.getLogger(name)
