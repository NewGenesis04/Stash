"""
Tests for the Agent ReAct loop (Agent.run and Agent.plan).

Ollama is mocked throughout — these tests verify loop logic, not model quality.
The mock returns controlled response strings so we can drive the agent down
specific paths: happy path, plan mode, max steps, parse errors, auth errors.
"""

from unittest.mock import MagicMock, patch, call

import pytest

from stash.core.agent import Agent, ReActStep
from stash.core.registry import SessionRegistry, ToolRegistry, UnauthorisedToolError
from stash.tools import ALL_TOOLS, ALL_SCHEMAS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFIG = {"ollama": {"model": "test-model", "max_steps": 20}}
CONFIG_LOW_STEPS = {"ollama": {"model": "test-model", "max_steps": 2}}


def _resp(content: str) -> dict:
    """Wrap a string in the shape ollama.Client.chat returns."""
    return {"message": {"content": content}}


def _make_agent(config=CONFIG, callbacks=None) -> Agent:
    with patch("stash.core.agent.ollama.Client"):
        return Agent(config, callbacks or [], ALL_SCHEMAS)


def _full_registry() -> SessionRegistry:
    return ToolRegistry(ALL_TOOLS).session(list(ALL_TOOLS.keys()))


def _readonly_registry() -> SessionRegistry:
    return ToolRegistry(ALL_TOOLS).session(["ls", "glob"])


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
    def test_thought_action_observation_final(self, tmp_path):
        (tmp_path / "notes.txt").write_text("hi")
        responses = [
            _resp(f"Thought: List the files\nAction: ls\nAction Input: {{\"path\": \"{tmp_path.as_posix()}\"}}"),
            _resp("Thought: I can see the files\nFinal Answer: Found notes.txt."),
        ]
        agent = _make_agent()
        agent._client.chat.side_effect = responses

        steps = agent.run("what files are here?", _full_registry())

        types = [s.type for s in steps]
        assert types == ["thought", "action", "observation", "thought", "final"]

    def test_final_answer_immediately(self):
        """Model returns a Final Answer without calling any tool."""
        agent = _make_agent()
        agent._client.chat.return_value = _resp(
            "Thought: I don't need tools\nFinal Answer: Nothing to do."
        )
        steps = agent.run("do nothing", _full_registry())
        types = [s.type for s in steps]
        assert types == ["thought", "final"]
        assert steps[-1].content == "Nothing to do."

    def test_multiple_tool_calls_before_final(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data")
        dst = tmp_path / "b.txt"

        responses = [
            _resp(f"Thought: First list\nAction: ls\nAction Input: {{\"path\": \"{tmp_path.as_posix()}\"}}"),
            _resp(f"Thought: Now move\nAction: mv\nAction Input: {{\"src\": \"{src.as_posix()}\", \"dst\": \"{dst.as_posix()}\"}}"),
            _resp("Thought: Done\nFinal Answer: Moved a.txt to b.txt."),
        ]
        agent = _make_agent()
        agent._client.chat.side_effect = responses

        steps = agent.run("move the file", _full_registry())
        types = [s.type for s in steps]
        assert types == ["thought", "action", "observation", "thought", "action", "observation", "thought", "final"]
        assert dst.exists()
        assert not src.exists()

    def test_observation_content_in_step(self, tmp_path):
        (tmp_path / "report.txt").write_text("")
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _resp(f"Thought: Check\nAction: ls\nAction Input: {{\"path\": \"{tmp_path.as_posix()}\"}}"),
            _resp("Thought: Done\nFinal Answer: Seen."),
        ]
        steps = agent.run("list", _full_registry())
        obs = next(s for s in steps if s.type == "observation")
        assert "report.txt" in obs.content
        assert obs.tool == "ls"

    def test_run_id_passed_through(self, tmp_path):
        agent = _make_agent()
        agent._client.chat.return_value = _resp(
            "Thought: Done\nFinal Answer: OK."
        )
        # should not raise — run_id accepted and used internally
        steps = agent.run("task", _full_registry(), run_id="my-run-123")
        assert any(s.type == "final" for s in steps)


# ---------------------------------------------------------------------------
# Plan mode — plan()
# ---------------------------------------------------------------------------

class TestAgentPlan:
    def test_readonly_tool_executes_in_plan_mode(self, tmp_path):
        (tmp_path / "file.txt").write_text("")
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _resp(f"Thought: List\nAction: ls\nAction Input: {{\"path\": \"{tmp_path.as_posix()}\"}}"),
            _resp("Thought: Done\nFinal Answer: Listed."),
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
            _resp(f"Thought: Move it\nAction: mv\nAction Input: {{\"src\": \"{src.as_posix()}\", \"dst\": \"{dst.as_posix()}\"}}"),
            _resp("Thought: Done\nFinal Answer: Moved."),
        ]
        steps = agent.plan("move file", _full_registry())
        obs = next(s for s in steps if s.type == "observation")
        assert obs.content == "[plan mode — not executed]"
        assert src.exists()  # file untouched

    def test_plan_does_not_load_history(self):
        """plan() (dry_run=True) skips history injection."""
        agent = _make_agent()
        agent._client.chat.return_value = _resp(
            "Thought: Done\nFinal Answer: OK."
        )
        # chat should be called with only system + user messages, no history
        agent.plan("task", _full_registry())
        messages_sent = agent._client.chat.call_args[1]["messages"]
        roles = [m["role"] for m in messages_sent]
        assert roles == ["system", "user"]


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestAgentErrors:
    def test_parse_error_adds_error_step_and_stops(self):
        agent = _make_agent()
        agent._client.chat.return_value = _resp("this is not the right format at all")
        steps = agent.run("task", _full_registry())
        assert steps[-1].type == "error"
        assert "no Thought" in steps[-1].content
        assert agent._client.chat.call_count == 1  # stopped after first bad response

    def test_unauthorised_tool_adds_error_step_and_stops(self):
        # registry only has ls — agent tries to call mv
        registry = ToolRegistry(ALL_TOOLS).session(["ls"])
        agent = _make_agent()
        agent._client.chat.side_effect = [
            _resp("Thought: Move it\nAction: mv\nAction Input: {\"src\": \"/a\", \"dst\": \"/b\"}"),
        ]
        steps = agent.run("move file", registry)
        assert steps[-1].type == "error"
        assert "mv" in steps[-1].content

    def test_max_steps_reached_adds_error_step(self):
        agent = _make_agent(CONFIG_LOW_STEPS)
        # always return an action — never a final answer
        agent._client.chat.return_value = _resp(
            "Thought: Still thinking\nAction: ls\nAction Input: {\"path\": \"/tmp\"}"
        )
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
            _resp(f"Thought: List\nAction: ls\nAction Input: {{\"path\": \"{tmp_path.as_posix()}\"}}"),
            _resp("Thought: Done\nFinal Answer: OK."),
        ]
        agent.run("list", _full_registry())

        cb.on_before.assert_called_once_with("ls", {"path": tmp_path.as_posix()})
        cb.on_after.assert_called_once()
        tool_arg = cb.on_after.call_args[0][0]
        assert tool_arg == "ls"

    def test_on_error_called_when_tool_raises(self, tmp_path):
        cb = MagicMock()
        cb.on_before = MagicMock()
        cb.on_after = MagicMock()
        cb.on_error = MagicMock()

        # ls on a nonexistent path returns an error string, it doesn't raise.
        # To trigger on_error we need a tool that actually raises.
        def _boom(**kwargs) -> str:
            raise RuntimeError("disk on fire")

        registry = SessionRegistry({"boom": _boom})
        schemas = [{"name": "boom", "description": "explodes"}]

        with patch("stash.core.agent.ollama.Client"):
            agent = Agent(CONFIG, [cb], schemas)

        agent._client.chat.side_effect = [
            _resp("Thought: Boom\nAction: boom\nAction Input: {}"),
            _resp("Thought: Done\nFinal Answer: OK."),
        ]
        agent.run("task", registry)
        cb.on_error.assert_called_once()
        assert "boom" in cb.on_error.call_args[0][0]
