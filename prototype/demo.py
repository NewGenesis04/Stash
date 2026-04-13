"""
Stash prototype — full demo.

Assembles every prototype component into one runnable app:
  loading screen → main layout (TitleBar + Chat + Sidebar + Footer)

Full interaction loop:
  1. Type a task → 1.5 s planning delay → thought bubble + plan card
  2. Approve (enter / button) → steps stream with audit log entries
  3. Reject (esc / button)    → cleared, ready for next task
  4. ctrl+o → model picker
  5. ctrl+n → rule editor

Run with:
    uv run python prototype/demo.py
"""

import asyncio
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer

from prototype.chat import ChatWidget, PlanApproved, PlanRejected, RunState, TaskSubmitted
from prototype.loading import AsciiArt, StatusSection
from prototype.model_picker import FAKE_MODELS, ModelPickerScreen
from prototype.models import FAKE_OBSERVATIONS, FAKE_PLAN
from prototype.rule_editor import RuleEditorScreen
from prototype.sidebar import FAKE_RULES, SidebarWidget
from prototype.title_bar import TitleBar


# ---------------------------------------------------------------------------
# Loading screen — standalone, no subclassing, pops itself after 5 s
# ---------------------------------------------------------------------------

class DemoLoadingScreen(Screen):
    """Reuses AsciiArt + StatusSection visuals. Pops itself after 5 s."""

    DEFAULT_CSS = """
    DemoLoadingScreen {
        background: #0E0E0F;
        align: center middle;
    }
    DemoLoadingScreen #body {
        width: auto;
        height: auto;
        layout: vertical;
        align: center middle;
    }
    DemoLoadingScreen #descriptor {
        height: auto;
        width: auto;
        layout: vertical;
        margin-top: 2;
        align: center middle;
    }
    DemoLoadingScreen #desc-line {
        color: #8B949E;
        text-align: center;
        height: 1;
        width: auto;
    }
    DemoLoadingScreen #by-line {
        color: #8B949E;
        opacity: 0.4;
        text-align: center;
        height: 1;
        width: auto;
        text-style: bold;
    }
    DemoLoadingScreen #status-wrap {
        margin-top: 3;
        width: 42;
        height: auto;
    }
    DemoLoadingScreen #corners {
        dock: bottom;
        height: 1;
        width: 100%;
        padding: 0 2;
    }
    DemoLoadingScreen #corner-bl {
        width: 1fr;
        color: #8B949E;
        opacity: 0.25;
        height: 1;
    }
    DemoLoadingScreen #corner-br {
        width: 1fr;
        color: #8B949E;
        opacity: 0.25;
        text-align: right;
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal as H
        from textual.widgets import Label
        with Vertical(id="body"):
            yield AsciiArt()
            with Vertical(id="descriptor"):
                yield Label("Local-first file management agent", id="desc-line")
                yield Label("BY NEWGENESIS", id="by-line")
            with Vertical(id="status-wrap"):
                yield StatusSection()
        with H(id="corners"):
            yield Label("NODE_SYSTEM_V4.0.2  ● ENCRYPTION: AES-256", id="corner-bl")
            yield Label("KERNEL_BOOT: OK  IO_PORT: 8080", id="corner-br")

    def on_mount(self) -> None:
        self.set_timer(5.0, self._finish)

    def _finish(self) -> None:
        self.app.pop_screen()
        # Schedule focus after the screen transition has rendered
        self.app.call_after_refresh(self._restore_focus)

    def _restore_focus(self) -> None:
        try:
            self.app.screen.query_one(ChatWidget).set_input_enabled(True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------

class MainDemoScreen(Screen):

    DEFAULT_CSS = """
    MainDemoScreen { layout: vertical; }
    MainDemoScreen #main-columns {
        width: 100%;
        height: 1fr;
        layout: horizontal;
    }
    MainDemoScreen #chat-col    { width: 1fr; height: 100%; }
    MainDemoScreen #sidebar-col { width: 44;  height: 100%; }
    """

    def compose(self) -> ComposeResult:
        yield TitleBar()
        with Horizontal(id="main-columns"):
            with Vertical(id="chat-col"):
                yield ChatWidget()
            with Vertical(id="sidebar-col"):
                yield SidebarWidget()
        yield Footer()

    def on_mount(self) -> None:
        tb = self.query_one(TitleBar)
        tb.set_ollama_status(True)
        tb.set_model("gemma3:4b")
        tb.set_rule_count(len(FAKE_RULES))

    def on_screen_resume(self) -> None:
        """Belt-and-suspenders: fires in Textual versions that post ScreenResume."""
        self.call_after_refresh(
            lambda: self.query_one(ChatWidget).set_input_enabled(True)
        )


# ---------------------------------------------------------------------------
# Demo app
# ---------------------------------------------------------------------------

class DemoApp(App):

    TITLE = "stash"

    CSS = """
    Screen { background: #0E0E0F; }
    """

    BINDINGS = [
        Binding("ctrl+o", "change_model", "Model"),
        Binding("ctrl+n", "new_rule",     "New rule"),
        Binding("ctrl+q", "quit",         "Quit"),
        Binding("enter",  "approve",      "Approve", show=False),
        Binding("escape", "reject",       "Reject",  show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state = RunState.IDLE

    async def on_mount(self) -> None:
        # Push main first (base), then loading on top.
        # Loading pops itself after 5 s, revealing main.
        await self.push_screen(MainDemoScreen())
        await self.push_screen(DemoLoadingScreen())

    # ------------------------------------------------------------------
    # Keyboard shortcuts for approve / reject
    # ------------------------------------------------------------------

    def action_approve(self) -> None:
        if self._state == RunState.AWAITING_APPROVAL:
            self.on_plan_approved(PlanApproved())

    def action_reject(self) -> None:
        if self._state == RunState.AWAITING_APPROVAL:
            self.on_plan_rejected(PlanRejected())

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def on_task_submitted(self, msg: TaskSubmitted) -> None:
        if self._state != RunState.IDLE:
            return
        self._state = RunState.PLANNING
        chat = self.screen.query_one(ChatWidget)
        chat.set_input_enabled(False)
        chat.append_bubble("user", msg.task)
        chat.append_bubble("system", "planning...")
        self.run_worker(self._do_plan(), exclusive=True)

    async def _do_plan(self) -> None:
        await asyncio.sleep(1.5)
        chat = self.screen.query_one(ChatWidget)
        chat.append_bubble(
            "thought",
            "I need to list the directory first, identify files to act on, "
            "then move and clean up. Let me plan the steps.",
        )
        chat.show_plan(FAKE_PLAN)
        self._state = RunState.AWAITING_APPROVAL

    def on_plan_approved(self, _: PlanApproved) -> None:
        if self._state != RunState.AWAITING_APPROVAL:
            return
        self._state = RunState.RUNNING
        chat = self.screen.query_one(ChatWidget)
        chat.hide_approve_bar()
        self.run_worker(self._do_run(), exclusive=True)

    def on_plan_rejected(self, _: PlanRejected) -> None:
        if self._state != RunState.AWAITING_APPROVAL:
            return
        chat = self.screen.query_one(ChatWidget)
        chat.hide_approve_bar()
        chat.append_rejection()
        chat.set_input_enabled(True)
        self._state = RunState.IDLE

    async def _do_run(self) -> None:
        chat     = self.screen.query_one(ChatWidget)
        sidebar  = self.screen.query_one(SidebarWidget)
        obs_idx  = 0
        step_idx = 0

        for step in FAKE_PLAN:
            await asyncio.sleep(0.7)

            if step.type == "thought":
                chat.append_bubble("thought", step.content)

            elif step.type == "action":
                args_str = ", ".join(f"{k}={v}" for k, v in (step.args or {}).items())
                chat.append_bubble("action", f"{step.tool}({args_str})")
                await asyncio.sleep(0.5)
                if obs_idx < len(FAKE_OBSERVATIONS):
                    obs = FAKE_OBSERVATIONS[obs_idx]
                    chat.append_bubble("observation", obs)
                    sidebar.append_audit_entry(step.tool or "?", obs)
                    obs_idx += 1
                chat.mark_step_done(step_idx)
                step_idx += 1

            elif step.type == "final":
                chat.append_bubble("final", step.content)

        chat.set_input_enabled(True)
        self._state = RunState.IDLE

    # ------------------------------------------------------------------
    # Modals
    # ------------------------------------------------------------------

    def action_change_model(self) -> None:
        self.push_screen(
            ModelPickerScreen(FAKE_MODELS, current="gemma3:4b"),
            self._on_model_selected,
        )

    def _on_model_selected(self, model: str | None) -> None:
        if model:
            self.screen.query_one(TitleBar).set_model(model)

    def action_new_rule(self) -> None:
        self.push_screen(RuleEditorScreen(), self._on_rule_saved)

    def _on_rule_saved(self, rule: dict | None) -> None:
        if rule:
            self.screen.query_one(TitleBar).set_rule_count(len(FAKE_RULES) + 1)


if __name__ == "__main__":
    DemoApp().run()
