"""
Tests for ToolRegistry and SessionRegistry.

Key behaviour:
  - ToolRegistry.session() issues a locked view of approved tools only
  - SessionRegistry.call() executes approved tools
  - SessionRegistry.call() raises UnauthorisedToolError for anything outside the approved set
  - Tools not in the registry at all are also blocked (not just unapproved ones)
"""

import pytest

from stash.core.registry import ToolRegistry, SessionRegistry, UnauthorisedToolError


# ---------------------------------------------------------------------------
# Helpers — lightweight fake tools so we don't touch the filesystem
# ---------------------------------------------------------------------------

def _add(a: int, b: int) -> str:
    return str(a + b)


def _echo(msg: str) -> str:
    return msg


def _multiply(x: int, y: int) -> str:
    return str(x * y)


ALL = {"add": _add, "echo": _echo, "multiply": _multiply}


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_session_contains_approved_tools(self):
        reg = ToolRegistry(ALL)
        session = reg.session(["add", "echo"])
        assert "add" in session.available
        assert "echo" in session.available

    def test_session_excludes_unapproved_tools(self):
        reg = ToolRegistry(ALL)
        session = reg.session(["add"])
        assert "multiply" not in session.available
        assert "echo" not in session.available

    def test_session_ignores_unknown_tool_names(self):
        """Approved list may name tools that don't exist — silently dropped."""
        reg = ToolRegistry(ALL)
        session = reg.session(["add", "nonexistent"])
        assert "add" in session.available
        assert "nonexistent" not in session.available

    def test_session_empty_approved_list(self):
        reg = ToolRegistry(ALL)
        session = reg.session([])
        assert session.available == []

    def test_all_tools_lists_everything(self):
        reg = ToolRegistry(ALL)
        assert set(reg.all_tools) == {"add", "echo", "multiply"}


# ---------------------------------------------------------------------------
# SessionRegistry — calling tools
# ---------------------------------------------------------------------------

class TestSessionRegistry:
    def test_calls_approved_tool(self):
        session = SessionRegistry({"add": _add, "echo": _echo})
        result = session.call("add", {"a": 2, "b": 3})
        assert result == "5"

    def test_calls_echo_tool(self):
        session = SessionRegistry({"echo": _echo})
        result = session.call("echo", {"msg": "hello"})
        assert result == "hello"

    def test_raises_for_unapproved_tool(self):
        session = SessionRegistry({"add": _add})
        with pytest.raises(UnauthorisedToolError, match="multiply"):
            session.call("multiply", {"x": 2, "y": 3})

    def test_raises_for_completely_unknown_tool(self):
        session = SessionRegistry({"add": _add})
        with pytest.raises(UnauthorisedToolError, match="ghost"):
            session.call("ghost", {})

    def test_raises_for_empty_registry(self):
        session = SessionRegistry({})
        with pytest.raises(UnauthorisedToolError):
            session.call("add", {"a": 1, "b": 2})

    def test_available_reflects_session_scope(self):
        session = SessionRegistry({"add": _add, "echo": _echo})
        assert set(session.available) == {"add", "echo"}

    def test_source_not_approved_does_not_bleed_into_session(self):
        """Modifying the original dict after session creation has no effect."""
        tools = {"add": _add}
        session = SessionRegistry(tools)
        tools["echo"] = _echo  # mutate original after session created
        with pytest.raises(UnauthorisedToolError):
            session.call("echo", {"msg": "hi"})
