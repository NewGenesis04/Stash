"""
Agent core — pure, stateless ReAct loop.

Each run is independent: takes a task + session registry + callbacks,
runs Thought → Action → Observation until a final answer is reached,
and returns the full step log.
"""

from datetime import datetime, UTC
from typing import Literal

from pydantic import BaseModel, Field

from stash.core.registry import SessionRegistry
from stash.core.callbacks import Callback


class ReActStep(BaseModel):
    type: Literal["thought", "action", "observation", "final"]
    content: str
    tool: str | None = None
    args: dict | None = None
    result: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class Agent:
    """Runs a single ReAct loop for a given task."""

    def __init__(self, config: dict, callbacks: list[Callback]) -> None:
        self.config = config
        self.callbacks = callbacks

    def plan(self, task: str, registry: SessionRegistry) -> list[ReActStep]:
        """Generate a full plan without executing. Used for HITL approval."""
        raise NotImplementedError

    def run(self, task: str, registry: SessionRegistry) -> list[ReActStep]:
        """Execute the ReAct loop against an approved session registry."""
        raise NotImplementedError
