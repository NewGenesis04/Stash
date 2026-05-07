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
import threading
import uuid
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from textual.app import App
from textual.binding import Binding
from textual.message import Message

from stash.core.agent import Agent, AgentFactory, ReActStep
from stash.core.callbacks import AuditLogger, TUIUpdater
from stash.core.registry import SessionRegistry
from stash.health.ollama import HealthResult, HealthStatus
from stash.persistence.tinydb import LocationsDB, RulesDB
from stash.scheduler.runner import StashScheduler
from stash.tui.messages import PlanApproved, PlanRejected, TaskSubmitted
from stash.tui.screens.main import MainScreen
import stash.persistence.sqlite as db


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


# TaskSubmitted, PlanApproved, PlanRejected are imported from stash.tui.messages
# (shared with ChatWidget to avoid circular imports).


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
    messages: list[dict] = Field(default_factory=list)


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
        Binding("ctrl+o", "change_model", "Change model"),
        Binding("ctrl+p", "open_locations", "Locations"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config: dict,
        config_path: Path,
        scheduler: StashScheduler,
        rules_db: RulesDB,
        locations_db: LocationsDB,
        sqlite_conn: sqlite3.Connection,
        agent_factory: AgentFactory,
        health_result: HealthResult | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._config_path = config_path
        self._scheduler = scheduler
        self._rules_db = rules_db
        self._locations_db = locations_db
        self._sqlite_conn = sqlite_conn
        self._agent_factory = agent_factory
        self._health_result = health_result
        self._run_state = RunState.IDLE
        self._pending_run: PendingRun | None = None
        self._ollama_available: bool | None = None  # None = unknown, not yet polled

    # --- lifecycle ---

    def on_mount(self) -> None:
        from stash.tui.screens.loading import LoadingScreen
        model = self.config.get("ollama", {}).get("model", "")
        self.push_screen(MainScreen(model=model))
        self.push_screen(LoadingScreen(self._health_result), self._on_loading_done)

    def _on_loading_done(self, health_result: HealthResult | None) -> None:
        self._scheduler.start()
        self.set_interval(30, self._poll_ollama)
        self.screen.query_one("SidebarWidget").load_rules(self._rules_db.all())
        if health_result is not None and health_result.status in (
            HealthStatus.NO_MODEL_SELECTED,
            HealthStatus.MODEL_MISSING,
        ):
            from stash.tui.screens.model_picker import ModelPickerScreen
            self.push_screen(
                ModelPickerScreen(health_result.available_models),
                self._on_model_selected,
            )
        log.info("app.mounted", extra={"initial_health": health_result.status.value if health_result else "unknown"})
        self.call_later(self._poll_ollama)
        self.call_after_refresh(self._restore_main_focus)

    async def on_unmount(self) -> None:
        self._scheduler.stop()
        self._sqlite_conn.close()
        log.info("app.unmounted")

    # --- health check ---

    async def _poll_ollama(self) -> None:
        from stash.health.ollama import check, HealthStatus, OllamaUnavailableError
        endpoint = self.config.get("ollama", {}).get("host", "http://localhost:11434")
        model = self.config.get("ollama", {}).get("model")
        try:
            result = await check(endpoint, model)
            available = result.status == HealthStatus.OK
        except OllamaUnavailableError:
            available = False

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

        chat = self.screen.query_one("ChatWidget")
        chat.set_input_enabled(False)
        chat.append_bubble("user", task)
        chat.append_bubble("system", "planning...", bubble_id="planning-bubble")

        db.begin_run(self._sqlite_conn, run_id, task)

        callbacks = [AuditLogger(self._sqlite_conn, run_id), TUIUpdater(self)]
        agent, registry = self._agent_factory.build(self._sqlite_conn, callbacks)

        try:
            loop = asyncio.get_event_loop()
            steps, messages = await loop.run_in_executor(None, agent.plan, task, registry, run_id)
        except Exception as e:
            log.error("app.plan_failed", extra={"run_id": run_id, "error": str(e)}, exc_info=True)
            db.finish_run(self._sqlite_conn, run_id, "failed")
            self._run_state = RunState.IDLE
            chat.remove_planning_bubble()
            chat.append_bubble("error", f"Planning failed: {e}")
            chat.set_input_enabled(True)
            return

        db.add_message(self._sqlite_conn, "user", task, session_id=self.config.get("_session_id"))

        has_actions = any(s.type == "action" for s in steps)
        if not has_actions:
            chat = self.screen.query_one("ChatWidget")
            chat.remove_planning_bubble()
            for step in steps:
                chat.append_step(step)
            chat.set_input_enabled(True)
            response_step = next((s for s in steps if s.type == "response"), None)
            if response_step:
                db.add_message(self._sqlite_conn, "assistant", response_step.content, session_id=self.config.get("_session_id"))
            db.finish_run(self._sqlite_conn, run_id, "completed")
            self._run_state = RunState.IDLE
            return

        self._pending_run = PendingRun(run_id=run_id, agent=agent, registry=registry, task=task, messages=messages)
        self._run_state = RunState.AWAITING_APPROVAL
        log.info("app.plan_ready", extra={"run_id": run_id, "steps": len(steps)})
        self.screen.query_one("ChatWidget").show_plan(steps)

    async def on_plan_approved(self, message: PlanApproved) -> None:
        if self._run_state != RunState.AWAITING_APPROVAL or self._pending_run is None:
            return

        self._run_state = RunState.RUNNING
        pending = self._pending_run
        chat = self.screen.query_one("ChatWidget")
        chat.hide_approve_bar()
        log.info("app.plan_approved", extra={"run_id": pending.run_id})

        try:
            loop = asyncio.get_event_loop()
            steps = await loop.run_in_executor(
                None, pending.agent.run, pending.task, pending.registry, pending.run_id, pending.messages
            )
            response = next((s for s in steps if s.type == "response"), None)
            if response:
                db.add_message(self._sqlite_conn, "assistant", response.content, session_id=self.config.get("_session_id"))
            db.finish_run(self._sqlite_conn, pending.run_id, "completed")
            log.info("app.run_complete", extra={"run_id": pending.run_id})
        except Exception as e:
            log.error("app.run_failed", extra={"run_id": pending.run_id, "error": str(e)}, exc_info=True)
            db.finish_run(self._sqlite_conn, pending.run_id, "failed")
        finally:
            self._pending_run = None
            self._run_state = RunState.IDLE
            self.screen.query_one("ChatWidget").set_input_enabled(True)

    async def on_plan_rejected(self, message: PlanRejected) -> None:
        if self._run_state != RunState.AWAITING_APPROVAL or self._pending_run is None:
            return

        run_id = self._pending_run.run_id
        db.finish_run(self._sqlite_conn, run_id, "failed")
        log.info("app.plan_rejected", extra={"run_id": run_id})
        self._pending_run = None
        self._run_state = RunState.IDLE
        chat = self.screen.query_one("ChatWidget")
        chat.hide_approve_bar()
        chat.append_rejection()
        chat.set_input_enabled(True)

    # --- cross-layer message handlers ---

    def on_react_step_ready(self, message: ReactStepReady) -> None:
        step = message.step
        self.screen.query_one("ChatWidget").append_step(step)
        if step.type == "observation" and step.tool and step.result:
            self.screen.query_one("SidebarWidget").append_audit_entry(step.tool, step.result)

    def on_rule_completed(self, message: RuleCompleted) -> None:
        log.info("app.rule_completed", extra={"rule_id": message.rule_id, "status": message.status})
        self.screen.query_one("SidebarWidget").update_rule_status(message.rule_id, message.status)

    def on_ollama_status_changed(self, message: OllamaStatusChanged) -> None:
        from stash.tui.screens.main import MainScreen
        for screen in self.screen_stack:
            if isinstance(screen, MainScreen):
                screen.query_one("TitleBar").set_ollama_status(message.available)
                break

    # --- action handlers ---

    def action_new_rule(self) -> None:
        from stash.tui.screens.rule_editor import RuleEditorScreen
        self.push_screen(RuleEditorScreen(), self._on_rule_saved)

    def _on_rule_saved(self, rule) -> None:
        if not rule:
            return
        self._rules_db.upsert(rule)
        self.screen.query_one("SidebarWidget").load_rules(self._rules_db.all())
        log.info("app.rule_saved", extra={"rule_id": rule.id, "name": rule.name})

    async def action_change_model(self) -> None:
        from stash.health.ollama import fetch_models, OllamaUnavailableError
        from stash.tui.screens.model_picker import ModelPickerScreen
        endpoint = self.config.get("ollama", {}).get("host", "http://localhost:11434")
        current  = self.config.get("ollama", {}).get("model", "")
        try:
            models = await fetch_models(endpoint)
        except OllamaUnavailableError:
            models = []
        self.push_screen(ModelPickerScreen(models, current=current), self._on_model_selected)

    def _on_model_selected(self, model: str | None) -> None:
        if not model:
            return
        self.config.setdefault("ollama", {})["model"] = model
        self._save_config()
        # Defer TitleBar update — this callback fires before pop_screen(),
        # so self.screen is still ModelPickerScreen at this point.
        # call_later runs after all pending messages (including pop_screen) are processed.
        self.call_later(self._apply_model_to_ui, model)

    def _apply_model_to_ui(self, model: str) -> None:
        from stash.tui.screens.main import MainScreen
        for screen in self.screen_stack:
            if isinstance(screen, MainScreen):
                screen.query_one("TitleBar").set_model(model)
                break
        if self._run_state == RunState.IDLE:
            self.call_after_refresh(self._restore_main_focus)

    def _restore_main_focus(self) -> None:
        """Re-enable and focus the chat input after any screen transition."""
        try:
            self.screen.query_one("ChatWidget").set_input_enabled(True)
        except Exception:
            pass

    def _save_config(self) -> None:
        try:
            import tomli_w
            saveable = {k: v for k, v in self.config.items() if not k.startswith("_")}
            with self._config_path.open("wb") as f:
                tomli_w.dump(saveable, f)
            log.info("app.config_saved", extra={"path": str(self._config_path)})
        except Exception as e:
            log.warning("app.config_save_failed", extra={"error": str(e)})

    def action_focus_audit_log(self) -> None:
        self.screen.query_one("SidebarWidget").focus_audit_log()

    def action_focus_rules(self) -> None:
        self.screen.query_one("SidebarWidget").focus_rules()

    def action_open_locations(self) -> None:
        from stash.tui.screens.location_registry import LocationRegistryScreen
        self.push_screen(LocationRegistryScreen(self._locations_db))

    # --- location picker (called from agent thread via resolve_location tool) ---

    def request_location(self, name: str) -> str | None:
        """Block the calling thread until the user picks and registers a folder."""
        # Phase 1: Defer picker during planning phase
        if self._run_state == RunState.PLANNING:
            return f"[plan mode — will prompt user to pick folder for '{name}']"

        event = threading.Event()
        result: list[str | None] = [None]

        def on_picked(entry) -> None:
            if entry is not None:
                self._locations_db.upsert(entry)
                result[0] = entry.path
            event.set()

        self.call_from_thread(self._open_location_picker, name, on_picked)
        completed = event.wait(timeout=120)
        if not completed:
            log.warning("app.request_location_timeout", extra={"name": name})
        return result[0]

    def _open_location_picker(self, name: str, callback) -> None:
        from stash.tui.screens.location_picker import LocationPickerScreen
        self.push_screen(LocationPickerScreen(suggested_name=name), callback)
