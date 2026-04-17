"""
Tool registry — manages the full tool set and issues session-scoped registries.

A SessionRegistry is locked to a specific approved tool list. Calling a tool
outside that list raises UnauthorisedToolError — not a warning, a hard stop.
Args are validated against the tool's Pydantic model before execution if a
validator is registered for that tool.
"""

from typing import Callable

from pydantic import BaseModel, ValidationError


class UnauthorisedToolError(Exception):
    pass


class SessionRegistry:
    """Immutable, session-scoped view of approved tools."""

    def __init__(self, tools: dict[str, Callable], validators: dict[str, type[BaseModel]] | None = None) -> None:
        self._tools = dict(tools)  # copy — mutations to the source dict don't affect this session
        self._validators = dict(validators or {})

    def call(self, name: str, args: dict) -> str:
        if name not in self._tools:
            raise UnauthorisedToolError(f"'{name}' was not approved for this session")
        if name in self._validators:
            try:
                validated = self._validators[name](**args)
                args = validated.model_dump()
            except (ValidationError, TypeError) as e:
                return f"error: invalid arguments for {name}: {e}"
        return self._tools[name](**args)

    @property
    def available(self) -> list[str]:
        return list(self._tools.keys())


class ToolRegistry:
    """Holds all registered tools and issues session-scoped registries."""

    def __init__(self, tools: dict[str, Callable], validators: dict[str, type[BaseModel]] | None = None) -> None:
        self._all_tools = tools
        self._validators = dict(validators or {})

    def session(self, approved: list[str]) -> SessionRegistry:
        return SessionRegistry(
            {k: self._all_tools[k] for k in approved if k in self._all_tools},
            validators={k: self._validators[k] for k in approved if k in self._validators},
        )

    @property
    def all_tools(self) -> list[str]:
        return list(self._all_tools.keys())
