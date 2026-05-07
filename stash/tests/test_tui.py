"""
TUI tests — state machine, message routing, and widget updates.

Uses Textual's headless test runner (App.run_test / Pilot).

Key challenge: Textual collects ALL on_mount handlers across the MRO and calls
them all — it doesn't stop at the first match. Subclassing StashApp and
overriding on_mount does NOT prevent StashApp.on_mount from also firing,
which would push the real LoadingScreen and its 5-second timer.

Fix: monkeypatch.setattr(StashApp, 'on_mount', ...) replaces the method at the
class level before the app runs. Textual finds only the patched version in
StashApp.__dict__, so the real LoadingScreen is never pushed.

Async tests use pytest.mark.anyio (anyio is installed as a transitive dep).
"""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import stash.persistence.sqlite as db
from stash.core.agent import Agent, ReActStep
from stash.core.registry import SessionRegistry
from stash.health.ollama import HealthResult, HealthStatus
from stash.persistence.tinydb import FolderRule, LocationsDB, RulesDB
from stash.tools import ALL_SCHEMAS
from stash.tui.app import (
    OllamaStatusChanged,
    RuleCompleted,
    RunState,
    StashApp,
)
from stash.tui.messages import PlanApproved, PlanRejected, TaskSubmitted


# ---------------------------------------------------------------------------
# Shared test health result
# ---------------------------------------------------------------------------

_OK_HEALTH = HealthResult(
    status=HealthStatus.OK,
    available_models=["test-model"],
    selected_model="test-model",
    message="OK",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_scheduler():
    s = MagicMock()
    s.start = MagicMock()
    s.stop = MagicMock()
    return s


_PLAN_STEPS = [
    ReActStep(type="thought", content="I will check the files"),
    ReActStep(type="action", content="ls", tool="ls", args={"path": "/tmp"}),
    ReActStep(type="observation", content="file.txt", tool="ls", args={"path": "/tmp"}, result="file.txt"),
    ReActStep(type="response", content="Found file.txt"),
]

_RUN_STEPS = [
    ReActStep(type="thought", content="Executing"),
    ReActStep(type="response", content="Done."),
]


@pytest.fixture
def mock_agent_factory():
    """
    Returns a factory whose .build() yields real Agent and SessionRegistry instances.

    PendingRun is a Pydantic BaseModel with `agent: Agent` and
    `registry: SessionRegistry` fields. Even with arbitrary_types_allowed=True,
    Pydantic validates via is_instance_of, so MagicMock objects fail validation.
    We build a real Agent (with ollama.Client patched out) and a real
    SessionRegistry, then replace .plan() and .run() with controlled mocks.
    """
    with patch("stash.core.agent.ollama.Client"):
        agent = Agent(
            {"ollama": {"model": "test-model", "max_steps": 20}},
            [],
            ALL_SCHEMAS,
        )
    agent.plan = MagicMock(return_value=(_PLAN_STEPS, []))
    agent.run = MagicMock(return_value=_RUN_STEPS)

    registry = SessionRegistry({})  # empty but a real instance — type check passes

    factory = MagicMock()
    factory.build.return_value = (agent, registry)
    return factory


@pytest.fixture
def make_app(tmp_path, mock_scheduler, mock_agent_factory, monkeypatch):
    """
    Returns a factory that builds a test-ready StashApp.

    monkeypatch.setattr replaces StashApp.on_mount at the class level so
    Textual only finds the test version — the real LoadingScreen is never pushed.
    The replacement calls _on_loading_done directly with a known-good HealthResult.
    """
    async def _test_on_mount(self):
        # Bypass LoadingScreen. Wire up the app the same way _on_loading_done does,
        # but skip _poll_ollama (needs a live Ollama) and set_interval (noise in tests).
        from stash.tui.screens.main import MainScreen
        self.push_screen(MainScreen(model="test-model"))
        self._scheduler.start()
        # push_screen schedules mounting; SidebarWidget children aren't composed yet.
        # Defer load_rules to after the next refresh so the widget tree is ready.
        def _load_rules():
            try:
                self.screen.query_one("SidebarWidget").load_rules(self._rules_db.all())
            except Exception:
                pass
        self.call_after_refresh(_load_rules)

    monkeypatch.setattr(StashApp, "on_mount", _test_on_mount)

    def _factory(rules=None):
        conn = sqlite3.connect(":memory:")
        db._migrate(conn)
        rules_db = RulesDB(tmp_path / "rules.json")
        locations_db = LocationsDB(tmp_path / "locations.json")
        if rules:
            for r in rules:
                rules_db.upsert(r)
        return StashApp(
            config={"ollama": {"model": "test-model", "max_steps": 20}},
            config_path=tmp_path / "config.toml",
            scheduler=mock_scheduler,
            rules_db=rules_db,
            locations_db=locations_db,
            sqlite_conn=conn,
            agent_factory=mock_agent_factory,
        )
    return _factory


def _sample_rule(rule_id="rule-1") -> FolderRule:
    return FolderRule(
        id=rule_id,
        name="Test Rule",
        target_path="/tmp/test",
        instructions="Do something",
        allowed_tools=["ls"],
        interval_hours=6,
    )


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_initial_state_is_idle(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        assert pilot.app._run_state == RunState.IDLE


@pytest.mark.anyio
async def test_task_submitted_transitions_to_awaiting_approval(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(TaskSubmitted("sort my downloads"))
        await pilot.pause(0.5)
        assert pilot.app._run_state == RunState.AWAITING_APPROVAL


@pytest.mark.anyio
async def test_task_ignored_when_not_idle(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app._run_state = RunState.RUNNING
        pilot.app.post_message(TaskSubmitted("another task"))
        await pilot.pause(0.2)
        assert pilot.app._run_state == RunState.RUNNING


@pytest.mark.anyio
async def test_plan_rejected_returns_to_idle(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(TaskSubmitted("sort my downloads"))
        await pilot.pause(0.5)
        assert pilot.app._run_state == RunState.AWAITING_APPROVAL
        pilot.app.post_message(PlanRejected())
        await pilot.pause(0.2)
        assert pilot.app._run_state == RunState.IDLE


@pytest.mark.anyio
async def test_plan_approved_runs_and_returns_to_idle(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(TaskSubmitted("sort my downloads"))
        await pilot.pause(0.5)
        pilot.app.post_message(PlanApproved())
        await pilot.pause(0.5)
        assert pilot.app._run_state == RunState.IDLE


@pytest.mark.anyio
async def test_pending_run_cleared_after_rejection(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(TaskSubmitted("task"))
        await pilot.pause(0.5)
        pilot.app.post_message(PlanRejected())
        await pilot.pause(0.2)
        assert pilot.app._pending_run is None


@pytest.mark.anyio
async def test_pending_run_cleared_after_approval(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(TaskSubmitted("task"))
        await pilot.pause(0.5)
        pilot.app.post_message(PlanApproved())
        await pilot.pause(0.5)
        assert pilot.app._pending_run is None


# ---------------------------------------------------------------------------
# Ollama status → title bar
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_ollama_online_shows_badge(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(OllamaStatusChanged(available=True))
        await pilot.pause()
        badge = pilot.app.screen.query_one("#ollama-badge")
        assert badge.display


@pytest.mark.anyio
async def test_ollama_offline_shows_badge(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        pilot.app.post_message(OllamaStatusChanged(available=False))
        await pilot.pause()
        badge = pilot.app.screen.query_one("#ollama-badge")
        assert badge.display


# ---------------------------------------------------------------------------
# Rule completed → sidebar
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_rule_completed_updates_sidebar(make_app):
    rule = _sample_rule("rule-99")
    async with make_app(rules=[rule]).run_test() as pilot:
        await pilot.pause(0.5)
        # Should not raise — sidebar finds the rule item and updates its dot
        pilot.app.post_message(RuleCompleted("rule-99", "completed"))
        await pilot.pause(0.5)
        
        pilot.app.screen.query_one("#rule_rule_99")

# ---------------------------------------------------------------------------
# Input interaction
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_typing_and_entering_task_submits(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        # pilot.type() does not exist in Textual 8.x. Post Input.Submitted directly
        # with a non-empty value — equivalent to the user typing and pressing Enter.
        # We're testing our message handler, not Textual's keyboard plumbing.
        from textual.widgets import Input as _Input
        input_widget = pilot.app.screen.query_one("#task-input")
        input_widget.post_message(_Input.Submitted(input_widget, value="sort my downloads"))
        await pilot.pause(0.5)
        # Successfully transitioned out of IDLE confirms TaskSubmitted was handled
        assert pilot.app._run_state != RunState.IDLE


@pytest.mark.anyio
async def test_empty_input_does_not_submit(make_app):
    async with make_app().run_test() as pilot:
        await pilot.pause()
        await pilot.click("#task-input")
        await pilot.press("enter")
        await pilot.pause(0.2)
        assert pilot.app._run_state == RunState.IDLE


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_scheduler_started_on_mount(make_app, mock_scheduler):
    async with make_app().run_test():
        pass
    mock_scheduler.start.assert_called_once()


@pytest.mark.anyio
async def test_scheduler_stopped_on_unmount(make_app, mock_scheduler):
    async with make_app().run_test():
        pass
    mock_scheduler.stop.assert_called_once()
