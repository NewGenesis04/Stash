"""
ChatWidget — task input and live ReAct stream.

Contains everything visible in the chat column:
  PaneHeader     — column title + keybind chip
  MessageBubble  — one streamed message (thought / action / observation / response / error / system)
  PlanStepRow    — one row in the plan table (blue chip · description · ○/✓)
  PlanMessage    — full plan card (tool chips + step table), rendered inline in stream
  ApproveBar     — approve / reject strip shown above input while awaiting approval
  InputArea      — › prefix + text input
  ChatWidget     — orchestrates all of the above; public API called by StashApp

Messages posted upward (handled by StashApp):
  TaskSubmitted  — user typed a task and hit Enter
  PlanApproved   — user approved the plan
  PlanRejected   — user rejected the plan
"""

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widget import Widget
from textual.widgets import Button, Input, Label

from stash.core.agent import ReActStep
from stash.tui.messages import PlanApproved, PlanRejected, TaskSubmitted


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_chip(tool: str) -> str:
    """Green chip — executed action (already run)."""
    return f"[on #0D2B1A][#3FB950] {tool} [/][/]"


def _plan_chip(tool: str) -> str:
    """Blue chip — proposed action (not yet run)."""
    return f"[on #0D1F38][#58A6FF] {tool} [/][/]"


def _keybind_chip(key: str) -> str:
    return f"[on #21262D][#58A6FF] {key} [/][/]"


# ---------------------------------------------------------------------------
# PaneHeader
# ---------------------------------------------------------------------------

class PaneHeader(Widget):
    DEFAULT_CSS = """
    PaneHeader {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
    }
    PaneHeader #pane-title { width: 1fr; color: #8B949E; }
    PaneHeader #pane-key   { width: auto; }
    """

    def __init__(self, title: str, keybind: str) -> None:
        super().__init__()
        self._title   = title
        self._keybind = keybind

    def compose(self) -> ComposeResult:
        yield Label(self._title.upper(), id="pane-title")
        yield Label(_keybind_chip(self._keybind), id="pane-key")


# ---------------------------------------------------------------------------
# MessageBubble
# ---------------------------------------------------------------------------

class MessageBubble(Widget):
    """One message in the stream: label + content card with coloured left border."""

    DEFAULT_CSS = """
    MessageBubble {
        height: auto;
        width: 100%;
        padding: 0 2 1 2;
        margin-bottom: 1;
    }
    MessageBubble #msg-header {
        height: 1;
        color: #8B949E;
    }
    MessageBubble #msg-card {
        height: auto;
        background: #161B22;
        border: tall #21262D;
        padding: 0 1;
    }
    MessageBubble #msg-content {
        height: auto;
        color: #C9D1D9;
    }

    /* Left accent per type */
    MessageBubble.user        #msg-card { border-left: tall #58A6FF; }
    MessageBubble.thought     #msg-card { border-left: tall #8957E5; }
    MessageBubble.action      #msg-card { border-left: tall #3FB950; }
    MessageBubble.observation #msg-card { border-left: tall #D29922; }
    MessageBubble.response       #msg-card { border-left: tall #FF7B72; }
    MessageBubble.error       #msg-card { border-left: tall #F85149; }
    MessageBubble.system      #msg-card { border-left: tall #30363D; }

    /* Header colour per type */
    MessageBubble.user        #msg-header { color: #58A6FF; }
    MessageBubble.thought     #msg-header { color: #8957E5; }
    MessageBubble.action      #msg-header { color: #3FB950; }
    MessageBubble.observation #msg-header { color: #D29922; }
    MessageBubble.response       #msg-header { color: #FF7B72; }
    MessageBubble.error       #msg-header { color: #F85149; }

    /* Content style per type */
    MessageBubble.thought  #msg-content { color: #9E8FDF; text-style: italic; }
    MessageBubble.system   #msg-content { color: #8B949E; }
    """

    _HEADERS = {
        "user":        "you",
        "thought":     "stash — thinking",
        "action":      "stash — executing",
        "observation": "stash — observed",
        "response":       "stash — response",
        "error":       "stash — error",
        "system":      "",
    }

    def __init__(self, msg_type: str, content: str, **kwargs) -> None:
        super().__init__(classes=msg_type, **kwargs)
        self._msg_type = msg_type
        self._content  = content

    def compose(self) -> ComposeResult:
        header  = self._HEADERS.get(self._msg_type, "")
        content = f"▶ {self._content}" if self._msg_type == "action" else self._content
        yield Label(header, id="msg-header")
        with Vertical(id="msg-card"):
            yield Label(content, id="msg-content")


# ---------------------------------------------------------------------------
# PlanMessage
# ---------------------------------------------------------------------------

class PlanStepRow(Widget):
    """One action step row: number · blue tool chip · description · ○/✓."""

    DEFAULT_CSS = """
    PlanStepRow {
        height: 1;
        width: 100%;
        layout: horizontal;
        align: left middle;
    }
    PlanStepRow #snum  { width: 4;   color: #58A6FF; text-style: bold; }
    PlanStepRow #stool { width: 14;  }
    PlanStepRow #sdesc { width: 1fr; color: #8B949E; padding: 0 1; }
    PlanStepRow #sstat { width: 2;   color: #30363D; }
    """

    def __init__(self, index: int, step: ReActStep) -> None:
        super().__init__(id=f"plan-step-{index}")
        self._index = index
        self._step  = step

    def compose(self) -> ComposeResult:
        yield Label(f"{self._index + 1}.", id="snum")
        yield Label(_plan_chip(self._step.tool or "?"), id="stool")
        yield Label(self._step.content, id="sdesc")
        yield Label("○", id="sstat")

    def mark_done(self) -> None:
        self.query_one("#sstat", Label).update("[#3FB950]✓[/]")


class PlanMessage(Widget):
    """Inline plan card: blue tool chips + action step table."""

    DEFAULT_CSS = """
    PlanMessage {
        height: auto;
        width: 100%;
        padding: 0 2 1 2;
        margin-bottom: 1;
    }
    PlanMessage #plan-card {
        height: auto;
        background: #161B22;
        border: tall #21262D;
        border-left: tall #D29922;
        padding: 0 1 1 1;
    }
    PlanMessage #plan-header {
        height: 1;
        color: #D29922;
        margin-bottom: 1;
    }
    PlanMessage #plan-tools {
        height: 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, steps: list[ReActStep]) -> None:
        super().__init__()
        self._action_steps = [s for s in steps if s.type == "action"]
        self._tools = list(dict.fromkeys(
            s.tool for s in self._action_steps if s.tool
        ))

    def compose(self) -> ComposeResult:
        with Vertical(id="plan-card"):
            yield Label("stash — plan ready · awaiting approval", id="plan-header")
            yield Label(
                "tools requested:  " + "  ".join(_plan_chip(t) for t in self._tools),
                id="plan-tools",
            )
            for i, step in enumerate(self._action_steps):
                yield PlanStepRow(i, step)

    def mark_step_done(self, index: int) -> None:
        try:
            self.query_one(f"#plan-step-{index}", PlanStepRow).mark_done()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ApproveBar
# ---------------------------------------------------------------------------

class ApproveBar(Widget):
    """Approve / reject strip. Hidden until a plan is ready."""

    DEFAULT_CSS = """
    ApproveBar {
        height: 5;
        layout: horizontal;
        align: left middle;
        background: #161B22;
        border-top: solid #30363D;
        padding: 0 2;
        display: none;
    }
    ApproveBar #approve-label {
        width: auto;
        height: 1;
        color: #8B949E;
        padding: 0 2 0 0;
    }
    ApproveBar #key-hint {
        width: 1fr;
        height: 1;
        color: #30363D;
        text-align: right;
    }
    ApproveBar Button {
        height: 3;
        border: none;
        min-width: 0;
        padding: 0 2;
        margin-right: 1;
    }
    ApproveBar #btn-approve {
        background: #0D2B1A;
        color: #3FB950;
    }
    ApproveBar #btn-approve:hover { background: #133d24; }
    ApproveBar #btn-reject {
        background: #2B0D0D;
        color: #F85149;
    }
    ApproveBar #btn-reject:hover { background: #3d1313; }
    """

    def compose(self) -> ComposeResult:
        yield Label("approve plan?", id="approve-label")
        yield Button("✓ Approve", id="btn-approve")
        yield Button("✕ Reject",  id="btn-reject")
        yield Label("enter · esc", id="key-hint")

    def show_bar(self) -> None:
        self.display = True

    def hide_bar(self) -> None:
        self.display = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-approve":
            self.post_message(PlanApproved())
        elif event.button.id == "btn-reject":
            self.post_message(PlanRejected())


# ---------------------------------------------------------------------------
# InputArea
# ---------------------------------------------------------------------------

class InputArea(Widget):
    """› prefix + text input."""

    DEFAULT_CSS = """
    InputArea {
        height: 3;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
        border-top: solid #30363D;
        background: #0E0E0F;
    }
    InputArea #prefix {
        width: 3;
        height: 1;
        color: #58A6FF;
        text-style: bold;
    }
    InputArea Input {
        width: 1fr;
        height: 1;
        background: transparent;
        border: none;
        color: #C9D1D9;
        padding: 0;
    }
    InputArea Input:focus { border: none; }
    """

    def compose(self) -> ComposeResult:
        yield Label("›", id="prefix")
        yield Input(placeholder="describe a task...", id="task-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        task = event.value.strip()
        if task:
            self.query_one(Input).clear()
            self.post_message(TaskSubmitted(task))

    def set_enabled(self, enabled: bool) -> None:
        inp = self.query_one(Input)
        inp.disabled = not enabled
        if enabled:
            inp.focus()


# ---------------------------------------------------------------------------
# ChatWidget
# ---------------------------------------------------------------------------

class ChatWidget(Widget):
    """
    Full chat column: header · scrollable stream · approve bar · input.

    Public API (called by StashApp):
      append_bubble(msg_type, content)  — add a raw bubble to the stream
      append_step(step)                 — render a ReActStep into the right bubble type
      show_plan(steps)                  — mount the inline plan card + show approve bar
      hide_approve_bar()                — hide the approve bar after decision
      mark_step_done(index)             — tick ✓ on plan step #index
      append_rejection()                — system bubble: plan rejected
      set_input_enabled(enabled)        — enable / disable the task input
    """

    DEFAULT_CSS = """
    ChatWidget {
        width: 100%;
        height: 100%;
        layout: vertical;
        background: #0E0E0F;
    }
    ChatWidget #stream {
        width: 100%;
        height: 1fr;
        padding: 1 0;
        background: #0E0E0F;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._action_step_idx = 0  # tracks which plan step to tick ✓ next

    def compose(self) -> ComposeResult:
        yield PaneHeader("task / chat", "enter")
        yield ScrollableContainer(id="stream")
        yield ApproveBar()
        yield InputArea()

    def on_mount(self) -> None:
        # Sets disabled=False as a safe default, but the focus() call inside
        # set_enabled is silently discarded by Textual — LoadingScreen is already
        # the active screen when this fires, and you can't focus a widget on an
        # inactive screen. The focus the user actually experiences comes from
        # StashApp._restore_main_focus(), called via call_after_refresh after
        # LoadingScreen dismisses. This call is kept as a belt-and-suspenders
        # default in case the startup order ever changes.
        self.query_one(InputArea).set_enabled(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_bubble(self, msg_type: str, content: str, bubble_id: str | None = None) -> None:
        stream = self.query_one("#stream", ScrollableContainer)
        kwargs = {"id": bubble_id} if bubble_id else {}
        stream.mount(MessageBubble(msg_type, content, **kwargs))
        stream.scroll_end(animate=False)

    def remove_planning_bubble(self) -> None:
        try:
            self.query_one("#planning-bubble").remove()
        except Exception:
            pass

    def append_step(self, step: ReActStep) -> None:
        """Render one ReActStep from the live agent into the stream."""
        if step.type == "thought":
            self.append_bubble("thought", step.content)

        elif step.type == "action":
            args_str = ", ".join(
                f"{k}={v}" for k, v in (step.args or {}).items()
            )
            self.append_bubble("action", f"{step.tool}({args_str})")
            # Tick the corresponding plan step circle immediately
            self.mark_step_done(self._action_step_idx)
            self._action_step_idx += 1

        elif step.type == "observation":
            self.append_bubble("observation", step.result or step.content)

        elif step.type == "response":
            self.append_bubble("response", step.content)

        elif step.type == "error":
            self.append_bubble("error", step.content)

    def show_plan(self, steps: list[ReActStep]) -> None:
        self._action_step_idx = 0
        self.remove_planning_bubble()
        stream = self.query_one("#stream", ScrollableContainer)
        stream.mount(PlanMessage(steps))
        stream.scroll_end(animate=False)
        self.query_one(ApproveBar).show_bar()

    def hide_approve_bar(self) -> None:
        self.query_one(ApproveBar).hide_bar()

    def mark_step_done(self, index: int) -> None:
        try:
            self.query_one(PlanMessage).mark_step_done(index)
        except Exception:
            pass

    def append_rejection(self) -> None:
        self.append_bubble("system", "Plan rejected. Type a new task.")

    def set_input_enabled(self, enabled: bool) -> None:
        self.query_one(InputArea).set_enabled(enabled)
