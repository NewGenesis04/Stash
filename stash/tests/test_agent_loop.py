"""
Tests for the Agent native tool-calling loop (Agent.run and Agent.plan).

Ollama is mocked throughout — these tests verify loop logic, not model quality.
Mocks return structured tool_calls or plain content responses to drive the agent
down specific paths: happy path, plan mode, max steps, auth errors.
"""

from unittest.mock import MagicMock, patch

import pytest

from stash.core.agent import Agent, ReActStep
from stash.core.registry import SessionRegistry, ToolRegistry, UnauthorisedToolError
from stash.tools import ALL_TOOLS, ALL_SCHEMAS, ALL_VALIDATORS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = {"ollama": {"model": "test-model", "max_steps": 20}}
CONFIG_LOW_STEPS = {"ollama": {"model": "test-model", "max_steps": 2}}


def _final_resp(content: str) -> dict:
    """Model responds without tool_calls — could be a completion, question, or explanation."""
    return {"message": {"role": "assistant", "content": content, "tool_calls": None}}


def _tool_resp(name: str, arguments: dict, content: str = "") -> dict:
    """Model returns a tool call, optionally with a thought in content."""
    return {
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
        }
    }


def _make_agent(config=CONFIG, callbacks=None) -> Agent:
    with patch("stash.core.agent.ollama.Client"):
        return Agent(config, callbacks or [], ALL_SCHEMAS)


def _full_registry() -> SessionRegistry:
    return ToolRegistry(ALL_TOOLS, ALL_VALIDATORS).session(list(ALL_TOOLS.keys()))


def _readonly_registry() -> SessionRegistry:
    return ToolRegistry(ALL_TOOLS, ALL_VALIDATORS).session(["ls", "glob"])


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestAgentInit:
    def test_raises_if_no_model_in_config(self):
        with patch("stash.core.agent.ollama.Client"):
            with pytest.raises(ValueError, match="No model selected"):
                Agent({"ollama": {}}, [], ALL_SCHEMAS)

    def test_raises_if_ollama_key_missing(self):
        with patch("stash.core.agent.ollama.Client"):
            with pytest.raises(ValueError, match="No model selected"):
                Agent({}, [], ALL_SCHEMAS)

    def test_reads_max_steps_from_config(self):
        agent = _make_agent({"ollama": {"model": "m", "max_steps": 5}})
        assert agent._max_steps == 5

    def test_default_max_steps(self):
        agent = _make_agent({"ollama": {"model": "m"}})
        assert agent._max_steps == 20


# ---------------------------------------------------------------------------
# Happy path — run()
# ---------------------------------------------------------------------------

class TestAgentRun:
    def test_action_observation_final(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hi")
        responses = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}),
            _final_resp("Found notes.txt."),
        ]
        agent = _make_agent()
        agent._client.chat.side_effect = responses

        steps = agent.run("what files are here?", _full_registry())

        types = [s.type for s in steps]
        assert types == ["action", "observation", "response"]

    def test_thought_emitted_when_content_alongside_tool_call(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hi")
        responses = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}, content="I should list first."),
            _final_resp("Found notes.txt."),
        ]
        agent = _make_agent()
        agent._client.chat.side_effect = responses

        steps = agent.run("what files are here?", _full_registry())
        types = [s.type for s in steps]
        assert types == ["thought", "action", "observation", "response"]

    def test_response_without_tool_calls(self):
        """Model responds without calling any tool."""
        agent = _make_agent()
        agent._client.chat.return_value = _final_resp("Nothing to do.")

        steps = agent.run("do nothing", _full_registry())
        types = [s.type for s in steps]
        assert types == ["response"]
        assert steps[-1].content == "Nothing to do."

    def test_multiple_tool_calls_before_final(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data")
        dst = tmp_path / "b.txt"

        responses = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}),
            _tool_resp("mv", {"src": src.as_posix(), "dst": dst.as_posix()}),
            _final_resp("Moved a.txt to b.txt."),
        ]
        agent = _make_agent()
        agent._client.chat.side_effect = responses

        steps = agent.run("move the file", _full_registry())
        types = [s.type for s in steps]
        assert types == ["action", "observation", "action", "observation", "response"]
        assert dst.exists()
        assert not src.exists()

    def test_observation_content_in_step(self, tmp_path):
        (tmp_path / "report.txt").write_text("")
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}),
            _final_resp("Seen."),
        ]
        steps = agent.run("list", _full_registry())
        obs = next(s for s in steps if s.type == "observation")
        assert "report.txt" in obs.content
        assert obs.tool == "ls"

    def test_run_id_passed_through(self):
        agent = _make_agent()
        agent._client.chat.return_value = _final_resp("OK.")
        steps = agent.run("task", _full_registry(), run_id="my-run-123")
        assert any(s.type == "response" for s in steps)


# ---------------------------------------------------------------------------
# Plan mode — plan()
# ---------------------------------------------------------------------------

class TestAgentPlan:
    def test_readonly_tool_executes_in_plan_mode(self, tmp_path):
        (tmp_path / "file.txt").write_text("")
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}),
            _final_resp("Listed."),
        ]
        steps = agent.plan("list files", _readonly_registry())
        obs = next(s for s in steps if s.type == "observation")
        assert "file.txt" in obs.content  # ls actually ran

    def test_write_tool_skipped_in_plan_mode(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data")
        dst = tmp_path / "b.txt"

        agent = _make_agent()
        agent._client.chat.side_effect = [
            _tool_resp("mv", {"src": src.as_posix(), "dst": dst.as_posix()}),
            _final_resp("Moved."),
        ]
        steps = agent.plan("move file", _full_registry())
        obs = next(s for s in steps if s.type == "observation")
        assert obs.content == "[plan mode — not executed]"
        assert src.exists()  # file untouched

    def test_plan_does_not_load_history(self):
        """plan() (dry_run=True) skips history injection."""
        agent = _make_agent()
        agent._client.chat.return_value = _final_resp("OK.")
        agent.plan("task", _full_registry())
        messages_sent = agent._client.chat.call_args[1]["messages"]
        roles = [m["role"] for m in messages_sent]
        assert roles == ["system", "user"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestAgentErrors:
    def test_unauthorised_tool_adds_error_step_and_stops(self):
        # registry only has ls — agent tries to call mv
        registry = ToolRegistry(ALL_TOOLS, ALL_VALIDATORS).session(["ls"])
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _tool_resp("mv", {"src": "/a", "dst": "/b"}),
        ]
        steps = agent.run("move file", registry)
        assert steps[-1].type == "error"
        assert "mv" in steps[-1].content

    def test_max_steps_reached_adds_error_step(self):
        agent = _make_agent(CONFIG_LOW_STEPS)
        # always return a tool call — never a plain response
        agent._client.chat.return_value = _tool_resp("ls", {"path": "/tmp"})
        steps = agent.run("task", _full_registry())
        assert steps[-1].type == "error"
        assert "max_steps" in steps[-1].content
        assert agent._client.chat.call_count == 2  # CONFIG_LOW_STEPS has max_steps=2


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

class TestAgentCallbacks:
    def test_on_after_called_for_each_tool_call(self, tmp_path):
        (tmp_path / "x.txt").write_text("")
        cb = MagicMock()
        cb.on_before = MagicMock()
        cb.on_after = MagicMock()
        cb.on_error = MagicMock()

        agent = _make_agent(callbacks=[cb])
        agent._client.chat.side_effect = [
            _tool_resp("ls", {"path": tmp_path.as_posix()}),
            _final_resp("OK."),
        ]
        agent.run("list", _full_registry())

        cb.on_before.assert_called_once_with("ls", {"path": tmp_path.as_posix()})
        cb.on_after.assert_called_once()
        assert cb.on_after.call_args[0][0] == "ls"

    def test_on_error_called_when_tool_raises(self):
        cb = MagicMock()
        cb.on_before = MagicMock()
        cb.on_after = MagicMock()
        cb.on_error = MagicMock()

        def _boom(**kwargs) -> str:
            raise RuntimeError("disk on fire")

        registry = SessionRegistry({"boom": _boom})
        schemas = [{
            "type": "function",
            "function": {"name": "boom", "description": "explodes", "parameters": {}},
        }]

        with patch("stash.core.agent.ollama.Client"):
            agent = Agent(CONFIG, [cb], schemas)

        agent._client.chat.side_effect = [
            _tool_resp("boom", {}),
            _final_resp("OK."),
        ]
        agent.run("task", registry)
        cb.on_error.assert_called_once()
        assert "boom" in cb.on_error.call_args[0][0]
