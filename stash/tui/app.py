"""
Stash TUI — Textual app root.

Owns all cross-layer message types and orchestrates the chat→plan→approve→run
state machine. Agent and Scheduler push updates here via post_message /
call_from_thread. Nothing in tui/ touches the filesystem directly.

State machine:
  IDLE → PLANNING → AWAITING_APPROVAL → RUNNING → IDLE
"""

import asyncio
import logging
import sqlite3
import uuid
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message

from stash.core.agent import Agent, AgentFactory, ReActStep
from stash.core.callbacks import AuditLogger, TUIUpdater
from stash.core.registry import SessionRegistry
from stash.health.ollama import HealthResult, HealthStatus
from stash.persistence.tinydb import RulesDB
from stash.scheduler.runner import StashScheduler
from stash.tui.screens.main import MainScreen
import stash.persistence.sqlite as db

if TYPE_CHECKING:
    from stash.tui.widgets.chat import ChatWidget
    from stash.tui.widgets.sidebar import Sidebar

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cross-layer message types
# ---------------------------------------------------------------------------

class ReactStepReady(Message):
    """Posted by Agent (via TUIUpdater callback) as each step completes."""
    def __init__(self, step: ReActStep) -> None:
        self.step = step
        super().__init__()


class RuleCompleted(Message):
    """Posted by Scheduler after a scheduled rule finishes."""
    def __init__(self, rule_id: str, status: str) -> None:
        self.rule_id = rule_id
        self.status = status
        super().__init__()


class OllamaStatusChanged(Message):
    """Posted by health check if Ollama availability changes."""
    def __init__(self, available: bool) -> None:
        self.available = available
        super().__init__()


class TaskSubmitted(Message):
    """Posted by ChatWidget when the user submits a task."""
    def __init__(self, task: str) -> None:
        self.task = task
        super().__init__()


class PlanApproved(Message):
    """Posted by the approve button / Enter keybinding."""
    pass


class PlanRejected(Message):
    """Posted by the reject button / Esc keybinding."""
    pass


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class RunState(Enum):
    IDLE               = "idle"
    PLANNING           = "planning"
    AWAITING_APPROVAL  = "awaiting_approval"
    RUNNING            = "running"


class PendingRun(BaseModel):
    """Holds context between plan approval and execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    run_id: str
    agent: Agent
    registry: SessionRegistry
    task: str


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class StashApp(App):
    TITLE = "Stash"
    SUB_TITLE = "local-first file agent"
    THEME = "nord"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+t", "app.toggle_theme", "Theme"),
        Binding("ctrl+n", "new_rule", "New rule"),
        Binding("ctrl+l", "focus_audit_log", "Audit log"),
        Binding("ctrl+r", "focus_rules", "Rules"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config: dict,
        config_path: Path,
        scheduler: StashScheduler,
        rules_db: RulesDB,
        sqlite_conn: sqlite3.Connection,
        agent_factory: AgentFactory,
        health_result: HealthResult | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._config_path = config_path
        self._scheduler = scheduler
        self._rules_db = rules_db
        self._sqlite_conn = sqlite_conn
        self._agent_factory = agent_factory
        self._health_result = health_result
        self._run_state = RunState.IDLE
        self._pending_run: PendingRun | None = None
        self._ollama_available: bool | None = None  # None = unknown, not yet polled

    def compose(self) -> ComposeResult:
        yield MainScreen()

    # --- lifecycle ---

    async def on_mount(self) -> None:
        self._scheduler.start()
        self.set_interval(30, self._poll_ollama)
        await self._poll_ollama()
        self.query_one("Sidebar").load_rules(self._rules_db.all())
        if self._health_result is not None and self._health_result.status in (
            HealthStatus.NO_MODEL_SELECTED,
            HealthStatus.MODEL_MISSING,
        ):
            from stash.tui.screens.model_picker import ModelPickerScreen
            self.push_screen(ModelPickerScreen(self.config, self._config_path))
        log.info("app.mounted", extra={"initial_health": self._health_result.status.value if self._health_result else "unknown"})

    async def on_unmount(self) -> None:
        self._scheduler.stop()
        self._sqlite_conn.close()
        log.info("app.unmounted")

    # --- health check ---

    async def _poll_ollama(self) -> None:
        from stash.health.ollama import check, HealthStatus, OllamaUnavailableError
        endpoint = self.config.get("ollama", {}).get("host", "http://localhost:11434")
        model = self.config.get("model")
        try:
            result = await check(endpoint, model)
            available = result.status == HealthStatus.OK
        except OllamaUnavailableError:
            available = False
        except NotImplementedError:
            return  # health check not yet implemented — skip silently

        if available != self._ollama_available:
            self._ollama_available = available
            self.post_message(OllamaStatusChanged(available))
            log.info("app.ollama_status_changed", extra={"available": available})

    # --- chat → plan → approve → run ---

    async def on_task_submitted(self, message: TaskSubmitted) -> None:
        if self._run_state != RunState.IDLE:
            log.warning("app.task_ignored", extra={"state": self._run_state.value, "task": message.task})
            return

        self._run_state = RunState.PLANNING
        task = message.task
        run_id = str(uuid.uuid4())
        log.info("app.task_submitted", extra={"run_id": run_id, "task": task})

        db.begin_run(self._sqlite_conn, run_id, task)
        db.add_message(self._sqlite_conn, "user", task)

        callbacks = [AuditLogger(self._sqlite_conn, run_id), TUIUpdater(self)]
        agent, registry = self._agent_factory.build(self._sqlite_conn, callbacks)

        try:
            loop = asyncio.get_event_loop()
            steps = await loop.run_in_executor(None, agent.plan, task, registry, run_id)
        except Exception as e:
            log.error("app.plan_failed", extra={"run_id": run_id, "error": str(e)}, exc_info=True)
            db.finish_run(self._sqlite_conn, run_id, "failed")
            self._run_state = RunState.IDLE
            return

        self._pending_run = PendingRun(run_id=run_id, agent=agent, registry=registry, task=task)
        self._run_state = RunState.AWAITING_APPROVAL
        log.info("app.plan_ready", extra={"run_id": run_id, "steps": len(steps)})
        self.query_one("ChatWidget").show_plan(steps)

    async def on_plan_approved(self, message: PlanApproved) -> None:
        if self._run_state != RunState.AWAITING_APPROVAL or self._pending_run is None:
            return

        self._run_state = RunState.RUNNING
        pending = self._pending_run
        log.info("app.plan_approved", extra={"run_id": pending.run_id})

        try:
            loop = asyncio.get_event_loop()
            steps = await loop.run_in_executor(
                None, pending.agent.run, pending.task, pending.registry, pending.run_id
            )
            final = next((s for s in steps if s.type == "final"), None)
            if final:
                db.add_message(self._sqlite_conn, "assistant", final.content)
            db.finish_run(self._sqlite_conn, pending.run_id, "completed")
            log.info("app.run_complete", extra={"run_id": pending.run_id})
        except Exception as e:
            log.error("app.run_failed", extra={"run_id": pending.run_id, "error": str(e)}, exc_info=True)
            db.finish_run(self._sqlite_conn, pending.run_id, "failed")
        finally:
            self._pending_run = None
            self._run_state = RunState.IDLE

    async def on_plan_rejected(self, message: PlanRejected) -> None:
        if self._run_state != RunState.AWAITING_APPROVAL or self._pending_run is None:
            return

        run_id = self._pending_run.run_id
        db.finish_run(self._sqlite_conn, run_id, "failed")
        log.info("app.plan_rejected", extra={"run_id": run_id})
        self._pending_run = None
        self._run_state = RunState.IDLE
        self.query_one("ChatWidget").append_rejection()

    # --- cross-layer message handlers ---

    def on_react_step_ready(self, message: ReactStepReady) -> None:
        self.query_one("ChatWidget").append_step(message.step)

    def on_rule_completed(self, message: RuleCompleted) -> None:
        log.info("app.rule_completed", extra={"rule_id": message.rule_id, "status": message.status})
        self.query_one("Sidebar").update_rule_status(message.rule_id, message.status)

    def on_ollama_status_changed(self, message: OllamaStatusChanged) -> None:
        self.query_one("TitleBar").set_ollama_status(message.available)

    # --- action handlers ---

    def action_new_rule(self) -> None:
        from stash.tui.screens.rule_editor import RuleEditorScreen
        self.push_screen(RuleEditorScreen())

    def action_focus_audit_log(self) -> None:
        self.query_one("Sidebar").focus_audit_log()

    def action_focus_rules(self) -> None:
        self.query_one("Sidebar").focus_rules()
