"""
Stash prototype — plan approval UX.

Tests the core interaction:
  type a task → plan surfaces → approve/deny steps → fake execution streams in

Run with:
    textual run --dev prototype/app.py
    # or
    python prototype/app.py
"""

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, RichLog

from prototype.models import FAKE_OBSERVATIONS, FAKE_PLAN, ReActStep


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class TaskSubmitted(Message):
    def __init__(self, task: str) -> None:
        self.task = task
        super().__init__()


class PlanApproved(Message):
    def __init__(self, approved_tools: set[str]) -> None:
        self.approved_tools = approved_tools
        super().__init__()


class PlanRejected(Message):
    pass


# ---------------------------------------------------------------------------
# Plan step widget — one row in the approval panel
# ---------------------------------------------------------------------------

class PlanStepRow(Widget):
    """Renders a single ReActStep in the approval panel."""

    DEFAULT_CSS = """
    PlanStepRow {
        height: auto;
        padding: 0 1;
        margin-bottom: 0;
    }
    PlanStepRow.thought {
        color: $text-muted;
    }
    PlanStepRow.action {
        background: $surface;
        border-left: thick $accent;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    PlanStepRow.final {
        color: $success;
        border-left: thick $success;
        padding: 0 1;
        margin-top: 1;
    }
    PlanStepRow Checkbox {
        height: 1;
        border: none;
        padding: 0;
        background: transparent;
    }
    PlanStepRow .step-label {
        height: auto;
        padding: 0 0 0 1;
    }
    PlanStepRow .args-label {
        color: $text-muted;
        padding: 0 0 0 3;
        height: auto;
    }
    """

    def __init__(self, step: ReActStep, index: int) -> None:
        super().__init__(classes=step.type)
        self.step = step
        self.index = index

    def compose(self) -> ComposeResult:
        step = self.step

        if step.type == "thought":
            yield Label(f"[dim]思[/dim] {step.content}", classes="step-label")

        elif step.type == "action":
            args_str = "  ".join(f"[bold]{k}[/bold]={v}" for k, v in (step.args or {}).items())
            with Horizontal():
                yield Checkbox(value=True, id=f"step_{self.index}")
                yield Label(
                    f"[bold]{step.tool}[/bold]  {step.content}",
                    classes="step-label",
                )
            yield Label(args_str, classes="args-label")

        elif step.type == "final":
            yield Label(f"[green]→ {step.content}[/green]", classes="step-label")


# ---------------------------------------------------------------------------
# Plan approval panel
# ---------------------------------------------------------------------------

class PlanApprovalPanel(Widget):
    """Shows the full plan, lets the user approve/deny individual steps."""

    DEFAULT_CSS = """
    PlanApprovalPanel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    PlanApprovalPanel #panel-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    PlanApprovalPanel #task-label {
        margin-bottom: 1;
        padding: 0 1;
        background: $surface;
        height: auto;
    }
    PlanApprovalPanel #steps-scroll {
        height: 1fr;
        margin-bottom: 1;
    }
    PlanApprovalPanel #tools-summary {
        color: $text-muted;
        margin-bottom: 1;
        height: auto;
    }
    PlanApprovalPanel #button-row {
        height: 3;
        align: center middle;
    }
    PlanApprovalPanel #btn-approve {
        margin-right: 2;
    }
    PlanApprovalPanel .empty-state {
        color: $text-muted;
        text-align: center;
        margin-top: 4;
        width: 100%;
    }
    """

    task: reactive[str] = reactive("")
    has_plan: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Label("Plan Approval", id="panel-title")
        yield Label("", id="task-label")
        with ScrollableContainer(id="steps-scroll"):
            yield Label("Waiting for task...", classes="empty-state", id="empty-state")
        yield Label("", id="tools-summary")
        with Horizontal(id="button-row"):
            yield Button("Approve & Run", variant="success", id="btn-approve", disabled=True)
            yield Button("Reject", variant="error", id="btn-reject", disabled=True)

    def load_plan(self, task: str) -> None:
        self.task = task
        self.query_one("#task-label", Label).update(f"Task: [bold]{task}[/bold]")

        scroll = self.query_one("#steps-scroll", ScrollableContainer)
        scroll.remove_children()

        action_steps = []
        for i, step in enumerate(FAKE_PLAN):
            row = PlanStepRow(step, i)
            scroll.mount(row)
            if step.type == "action":
                action_steps.append(step)

        tools = sorted({s.tool for s in action_steps if s.tool})
        self.query_one("#tools-summary", Label).update(
            f"Tools required: [bold]{', '.join(tools)}[/bold]"
        )

        self.query_one("#btn-approve", Button).disabled = False
        self.query_one("#btn-reject", Button).disabled = False
        self.has_plan = True

    def get_approved_tools(self) -> set[str]:
        """Return tools where the user left the checkbox checked."""
        approved: set[str] = set()
        for i, step in enumerate(FAKE_PLAN):
            if step.type == "action" and step.tool:
                cb = self.query_one(f"#step_{i}", Checkbox)
                if cb.value:
                    approved.add(step.tool)
        return approved

    def set_executing(self) -> None:
        self.query_one("#btn-approve", Button).disabled = True
        self.query_one("#btn-reject", Button).disabled = True
        self.query_one("#panel-title", Label).update("[yellow]Executing...[/yellow]")

    def set_done(self) -> None:
        self.query_one("#panel-title", Label).update("[green]Done[/green]")

    def reset(self) -> None:
        self.has_plan = False
        self.query_one("#task-label", Label).update("")
        self.query_one("#tools-summary", Label).update("")
        scroll = self.query_one("#steps-scroll", ScrollableContainer)
        scroll.remove_children()
        scroll.mount(Label("Waiting for task...", classes="empty-state", id="empty-state"))
        self.query_one("#btn-approve", Button).disabled = True
        self.query_one("#btn-reject", Button).disabled = True
        self.query_one("#panel-title", Label).update("Plan Approval")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-approve":
            approved_tools = self.get_approved_tools()
            self.post_message(PlanApproved(approved_tools))
        elif event.button.id == "btn-reject":
            self.post_message(PlanRejected())


# ---------------------------------------------------------------------------
# Chat pane — task input + streaming ReAct log
# ---------------------------------------------------------------------------

class ChatPane(Widget):
    DEFAULT_CSS = """
    ChatPane {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    ChatPane #pane-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }
    ChatPane #react-log {
        height: 1fr;
        margin-bottom: 1;
    }
    ChatPane #input-row {
        height: 3;
        align: center middle;
    }
    ChatPane #task-input {
        width: 1fr;
        margin-right: 1;
    }
    """

    can_submit: reactive[bool] = reactive(True)

    def compose(self) -> ComposeResult:
        yield Label("Chat", id="pane-title")
        yield RichLog(id="react-log", highlight=True, markup=True, auto_scroll=True)
        with Horizontal(id="input-row"):
            yield Input(placeholder="Describe a task...", id="task-input")
            yield Button("Submit", variant="primary", id="btn-submit")

    def write(self, text: str) -> None:
        self.query_one("#react-log", RichLog).write(text)

    def set_submittable(self, value: bool) -> None:
        self.can_submit = value
        self.query_one("#btn-submit", Button).disabled = not value
        self.query_one("#task-input", Input).disabled = not value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def _submit(self) -> None:
        if not self.can_submit:
            return
        task_input = self.query_one("#task-input", Input)
        task = task_input.value.strip()
        if not task:
            return
        task_input.value = ""
        self.post_message(TaskSubmitted(task))


# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

class StashApp(App):
    TITLE = "Stash"
    SUB_TITLE = "local-first file agent"

    CSS = """
    Screen {
        layout: horizontal;
    }
    #left {
        width: 1fr;
        height: 100%;
        padding: 1;
    }
    #right {
        width: 1fr;
        height: 100%;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+r", "reset", "Reset"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="left"):
                yield ChatPane()
            with Vertical(id="right"):
                yield PlanApprovalPanel()
        yield Footer()

    # --- message handlers ---

    def on_task_submitted(self, message: TaskSubmitted) -> None:
        chat = self.query_one(ChatPane)

        chat.set_submittable(False)
        chat.write(f"\n[bold cyan]You:[/bold cyan] {message.task}")
        chat.write("[dim]Generating plan...[/dim]")

        # Simulate plan generation delay then load plan
        self.run_worker(self._generate_plan(message.task), exclusive=True)

    async def _generate_plan(self, task: str) -> None:
        await asyncio.sleep(1.2)  # fake LLM latency
        chat = self.query_one(ChatPane)
        panel = self.query_one(PlanApprovalPanel)
        chat.write("[dim]Plan ready. Review and approve →[/dim]")
        panel.load_plan(task)

    def on_plan_approved(self, message: PlanApproved) -> None:
        chat = self.query_one(ChatPane)
        panel = self.query_one(PlanApprovalPanel)

        panel.set_executing()
        tools_str = ", ".join(sorted(message.approved_tools)) or "none"
        chat.write(f"\n[green]Approved.[/green] Locked tools: [bold]{tools_str}[/bold]")
        chat.write("[dim]Executing...[/dim]")

        self.run_worker(self._execute_plan(message.approved_tools), exclusive=True)

    async def _execute_plan(self, approved_tools: set[str]) -> None:
        chat = self.query_one(ChatPane)
        panel = self.query_one(PlanApprovalPanel)
        obs_index = 0

        for step in FAKE_PLAN:
            await asyncio.sleep(0.6)

            if step.type == "thought":
                chat.write(f"\n[dim]Thought:[/dim] {step.content}")

            elif step.type == "action":
                if step.tool not in approved_tools:
                    chat.write(f"\n[red]BLOCKED:[/red] [bold]{step.tool}[/bold] — not approved, skipping.")
                    if obs_index < len(FAKE_OBSERVATIONS):
                        obs_index += 1
                    continue

                args_str = ", ".join(f"{k}={v}" for k, v in (step.args or {}).items())
                chat.write(f"\n[yellow]Action:[/yellow] [bold]{step.tool}[/bold]({args_str})")
                await asyncio.sleep(0.4)

                if obs_index < len(FAKE_OBSERVATIONS):
                    obs = FAKE_OBSERVATIONS[obs_index]
                    chat.write(f"[dim]  → {obs}[/dim]")
                    obs_index += 1

            elif step.type == "final":
                await asyncio.sleep(0.4)
                chat.write(f"\n[green bold]Final answer:[/green bold] {step.content}")

        panel.set_done()
        chat.set_submittable(True)
        chat.write("\n[dim]Task complete. Type another task to continue.[/dim]")

    def on_plan_rejected(self, message: PlanRejected) -> None:
        chat = self.query_one(ChatPane)
        panel = self.query_one(PlanApprovalPanel)
        panel.reset()
        chat.write("\n[red]Plan rejected.[/red] Type a new task.")
        chat.set_submittable(True)

    def action_reset(self) -> None:
        chat = self.query_one(ChatPane)
        panel = self.query_one(PlanApprovalPanel)
        panel.reset()
        chat.set_submittable(True)
        chat.write("\n[dim]Reset.[/dim]")


if __name__ == "__main__":
    StashApp().run()
