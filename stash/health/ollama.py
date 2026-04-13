"""
Ollama health check — run on startup before the TUI launches.

Outcomes:
  OK                — Ollama running, selected model pulled and ready
  NO_MODEL_SELECTED — Ollama running, no model set in config → show picker
  MODEL_MISSING     — Ollama running, configured model not pulled → show picker
  (exception)       — Ollama not reachable → OllamaUnavailableError (hard exit)
"""

import logging

import ollama
from pydantic import BaseModel
from enum import Enum

log = logging.getLogger(__name__)


class HealthStatus(Enum):
    OK                = "ok"
    NO_MODEL_SELECTED = "no_model_selected"
    MODEL_MISSING     = "model_missing"


class HealthResult(BaseModel):
    status:           HealthStatus
    available_models: list[str]
    selected_model:   str | None
    message:          str


class OllamaUnavailableError(Exception):
    pass


async def fetch_models(endpoint: str) -> list[str]:
    """Return the names of all locally pulled models."""
    client = ollama.AsyncClient(host=endpoint)
    response = await client.list()
    return [m.model for m in response.models]


async def check(endpoint: str, selected_model: str | None) -> HealthResult:
    """
    Ping Ollama, fetch available models, and validate the selected model.
    Raises OllamaUnavailableError if Ollama isn't reachable.
    """
    try:
        models = await fetch_models(endpoint)
    except Exception as e:
        log.error("health.ollama_unreachable", extra={"endpoint": endpoint, "error": str(e)})
        raise OllamaUnavailableError(
            f"Cannot reach Ollama at {endpoint}.\n"
            "Make sure Ollama is running:  ollama serve"
        ) from e

    log.info("health.models_found", extra={"count": len(models), "models": models})

    if not selected_model:
        return HealthResult(
            status=HealthStatus.NO_MODEL_SELECTED,
            available_models=models,
            selected_model=None,
            message="No model configured. Please select one to continue.",
        )

    if selected_model not in models:
        log.warning(
            "health.model_missing",
            extra={"selected": selected_model, "available": models},
        )
        return HealthResult(
            status=HealthStatus.MODEL_MISSING,
            available_models=models,
            selected_model=selected_model,
            message=(
                f"Model '{selected_model}' is not available locally. "
                "Please select another or run: ollama pull " + selected_model
            ),
        )

    return HealthResult(
        status=HealthStatus.OK,
        available_models=models,
        selected_model=selected_model,
        message=f"Ollama is running. Model '{selected_model}' is ready.",
    )


async def pull_model(endpoint: str, model: str) -> None:
    """Pull a model from the Ollama registry."""
    client = ollama.AsyncClient(host=endpoint)
    await client.pull(model)
