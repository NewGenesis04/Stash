"""
Ollama health check — run on startup before the TUI launches.

Outcomes:
  - Running + model configured + pulled  → OK, fully operational
  - Running + no model configured        → NO_MODEL_SELECTED, show picker
  - Running + model configured but gone  → MODEL_MISSING, show picker
  - Ollama not running                   → raise OllamaUnavailableError (hard block)
"""

import logging
from enum import Enum

import httpx
from pydantic import BaseModel

log = logging.getLogger(__name__)


class HealthStatus(Enum):
    OK = "ok"
    NO_MODEL_SELECTED = "no_model_selected"
    MODEL_MISSING = "model_missing"


class HealthResult(BaseModel):
    status: HealthStatus
    available_models: list[str]
    selected_model: str | None
    message: str


class OllamaUnavailableError(Exception):
    pass


async def check(endpoint: str, selected_model: str | None) -> HealthResult:
    """
    Ping Ollama, fetch available models, and validate the selected model.
    Raises OllamaUnavailableError if Ollama isn't running.
    """
    raise NotImplementedError


async def fetch_models(endpoint: str) -> list[str]:
    """Return the names of all locally pulled models."""
    raise NotImplementedError


async def pull_model(endpoint: str, model: str) -> None:
    raise NotImplementedError
