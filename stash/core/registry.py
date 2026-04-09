"""
Tool registry — manages the full tool set and issues session-scoped registries.

A SessionRegistry is locked to a specific approved tool list. Calling a tool
outside that list raises UnauthorisedToolError — not a warning, a hard stop.
"""

from typing import Callable


class UnauthorisedToolError(Exception):
    pass


class SessionRegistry:
    """Immutable, session-scoped view of approved tools."""

    def __init__(self, tools: dict[str, Callable]) -> None:
        self._tools = tools

    def call(self, name: str, args: dict) -> str:
        if name not in self._tools:
            raise UnauthorisedToolError(f"'{name}' was not approved for this session")
        return self._tools[name](**args)

    @property
    def available(self) -> list[str]:
        return list(self._tools.keys())


class ToolRegistry:
    """Holds all registered tools and issues session-scoped registries."""

    def __init__(self, tools: dict[str, Callable]) -> None:
        self._all_tools = tools

    def session(self, approved: list[str]) -> SessionRegistry:
        return SessionRegistry({k: self._all_tools[k] for k in approved if k in self._all_tools})

    @property
    def all_tools(self) -> list[str]:
        return list(self._all_tools.keys())
