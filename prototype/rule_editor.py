"""
Stash prototype — rule editor screen.

Modal form for creating / editing a folder rule.

Keys:
    ctrl+n  — open new rule editor
    ctrl+e  — open editor pre-filled with a fake existing rule
    ctrl+s  — save (inside editor)
    escape  — cancel (inside editor)
    q       — quit prototype

Run with:
    uv run python prototype/rule_editor.py
"""

import sys
import uuid
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Checkbox, Input, Label, Select


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FAKE_EXISTING_RULE = {
    "id": "rule_001",
    "name": "Downloads Cleanup",
    "target_path": "~/Downloads",
    "instructions": "Remove files older than 30 days. Move videos to ~/Media/Videos.",
    "interval_hours": 6,
    "allowed_tools": ["ls", "glob", "mv"],
}

_ALL_TOOLS = ["ls", "glob", "mv", "mkdir", "rm", "rename"]

# Two rows of three so all tools fit within the 60-wide dialog
_TOOL_ROWS = [_ALL_TOOLS[:3], _ALL_TOOLS[3:]]

_INTERVAL_OPTIONS: list[tuple[str, int]] = [
    ("Every hour",     1),
    ("Every 6 hours",  6),
    ("Every 12 hours", 12),
    ("Every day",      24),
    ("Every 3 days",   72),
    ("Every week",     168),
]


def _chip(key: str) -> str:
    return f"[on #21262D][#C9D1D9] {key} [/][/]"


# ---------------------------------------------------------------------------
# RuleEditorScreen
# ---------------------------------------------------------------------------

class RuleEditorScreen(ModalScreen):
    """
    Modal form. Dismisses with a dict on save, None on cancel.
    Pass rule=None for a new rule, or a dict to pre-fill for edit.
    """

    DEFAULT_CSS = """
    RuleEditorScreen {
        align: center middle;
    }
    RuleEditorScreen #dialog {
        width: 60;
        height: auto;
        max-height: 38;
        background: #161B22;
        border: solid #30363D;
        border-top: solid #58A6FF;
    }
    RuleEditorScreen #dialog-header {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        align: left middle;
        padding: 0 2;
    }
    RuleEditorScreen #dialog-title {
        color: #58A6FF;
        text-style: bold;
    }
    RuleEditorScreen #form-body {
        height: auto;
        max-height: 28;
        padding: 1 2;
    }
    RuleEditorScreen .field-label {
        height: 1;
        color: #8B949E;
        margin-top: 1;
        margin-bottom: 0;
    }
    RuleEditorScreen Input {
        background: #0E0E0F;
        border: solid #30363D;
        color: #C9D1D9;
        height: 3;
        margin-bottom: 0;
    }
    RuleEditorScreen Input:focus {
        border: solid #58A6FF;
    }
    RuleEditorScreen Select {
        background: #0E0E0F;
        height: 3;
        margin-bottom: 0;
    }
    RuleEditorScreen Select:focus {
        border: solid #58A6FF;
    }
    RuleEditorScreen .tool-row {
        height: 1;
        layout: horizontal;
        margin-top: 1;
    }
    RuleEditorScreen .tool-row Checkbox {
        height: 1;
        width: 1fr;
        border: none;
        background: transparent;
        padding: 0;
        margin: 0;
    }
    RuleEditorScreen #error-label {
        height: 1;
        color: #F85149;
        margin-top: 1;
    }
    RuleEditorScreen #dialog-footer {
        height: 5;
        border-top: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    RuleEditorScreen #dialog-footer Button {
        height: 3;
        border: none;
        min-width: 0;
        padding: 0 2;
        margin-right: 1;
    }
    RuleEditorScreen #btn-save {
        background: #0D2B1A;
        color: #3FB950;
    }
    RuleEditorScreen #btn-save:hover   { background: #133d24; }
    RuleEditorScreen #btn-cancel {
        background: #21262D;
        color: #8B949E;
    }
    RuleEditorScreen #btn-cancel:hover {
        background: #2B0D0D;
        color: #F85149;
    }
    RuleEditorScreen #key-hint {
        width: 1fr;
        height: 1;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save",   "Save",   show=False),
    ]

    def __init__(self, rule: dict | None = None) -> None:
        super().__init__()
        self.rule = rule

    def compose(self) -> ComposeResult:
        is_new   = self.rule is None
        title    = "new rule" if is_new else "edit rule"
        name     = "" if is_new else self.rule["name"]
        path     = "" if is_new else self.rule["target_path"]
        instruct = "" if is_new else self.rule["instructions"]
        interval = 6 if is_new else self.rule["interval_hours"]
        tools_on = set() if is_new else set(self.rule["allowed_tools"])

        with Vertical(id="dialog"):
            with Vertical(id="dialog-header"):
                yield Label(title, id="dialog-title")

            with ScrollableContainer(id="form-body"):
                yield Label("Name", classes="field-label")
                yield Input(value=name, placeholder="Downloads Cleanup", id="inp-name")

                yield Label("Target path", classes="field-label")
                yield Input(value=path, placeholder="~/Downloads", id="inp-path")

                yield Label("Instructions", classes="field-label")
                yield Input(
                    value=instruct,
                    placeholder="Remove files older than 30 days, move videos to ~/Media",
                    id="inp-instructions",
                )

                yield Label("Run every", classes="field-label")
                yield Select(_INTERVAL_OPTIONS, value=interval, id="sel-interval")

                yield Label("Allowed tools", classes="field-label")
                for row in _TOOL_ROWS:
                    with Horizontal(classes="tool-row"):
                        for tool in row:
                            yield Checkbox(tool, value=(tool in tools_on), id=f"tool-{tool}")

                yield Label("", id="error-label")

            with Horizontal(id="dialog-footer"):
                yield Button("✓ Save",   id="btn-save")
                yield Button("✕ Cancel", id="btn-cancel")
                yield Label(
                    f"{_chip('ctrl+s')} save   {_chip('esc')} cancel",
                    id="key-hint",
                )

    def on_mount(self) -> None:
        self.query_one("#inp-name", Input).focus()

    def action_save(self) -> None:
        result = self._build_rule()
        if result:
            self.dismiss(result)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def _build_rule(self) -> dict | None:
        name     = self.query_one("#inp-name", Input).value.strip()
        path     = self.query_one("#inp-path", Input).value.strip()
        instruct = self.query_one("#inp-instructions", Input).value.strip()
        interval = self.query_one("#sel-interval", Select).value
        tools    = [t for t in _ALL_TOOLS if self.query_one(f"#tool-{t}", Checkbox).value]
        error    = self.query_one("#error-label", Label)

        if not name:
            error.update("[#F85149]Name is required.[/]")
            self.query_one("#inp-name", Input).focus()
            return None
        if not path:
            error.update("[#F85149]Target path is required.[/]")
            self.query_one("#inp-path", Input).focus()
            return None
        if not instruct:
            error.update("[#F85149]Instructions are required.[/]")
            self.query_one("#inp-instructions", Input).focus()
            return None
        if not tools:
            error.update("[#F85149]Select at least one tool.[/]")
            return None
        error.update("")
        return {
            "id":             self.rule["id"] if self.rule else str(uuid.uuid4()),
            "name":           name,
            "target_path":    path,
            "instructions":   instruct,
            "interval_hours": int(interval),
            "allowed_tools":  tools,
        }


# ---------------------------------------------------------------------------
# Prototype app
# ---------------------------------------------------------------------------

class _BgScreen(Screen):
    DEFAULT_CSS = """
    _BgScreen {
        background: #0E0E0F;
        align: center middle;
    }
    """

    BINDINGS = [Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Label(
            "[#8B949E]"
            "[#58A6FF]ctrl+n[/] new rule   "
            "[#58A6FF]ctrl+e[/] edit existing   "
            "[#58A6FF]q[/] quit"
            "[/]",
            id="hint",
        )


class RuleEditorProto(App):

    CSS = """
    Screen { background: #0E0E0F; }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_rule",  "New rule"),
        Binding("ctrl+e", "edit_rule", "Edit rule"),
    ]

    def compose(self) -> ComposeResult:
        yield _BgScreen()

    def action_new_rule(self) -> None:
        self.push_screen(RuleEditorScreen(), self._on_done)

    def action_edit_rule(self) -> None:
        self.push_screen(RuleEditorScreen(FAKE_EXISTING_RULE), self._on_done)

    def _on_done(self, result: dict | None) -> None:
        bg = self.query_one(_BgScreen)
        if result:
            tools = ", ".join(result["allowed_tools"])
            bg.query_one("#hint", Label).update(
                f"[#3FB950]Saved:[/] [#C9D1D9]{result['name']}[/]  "
                f"[#8B949E]{result['target_path']} · every {result['interval_hours']}h · {tools}[/]\n\n"
                f"[#8B949E][#58A6FF]ctrl+n[/] new   [#58A6FF]ctrl+e[/] edit   [#58A6FF]q[/] quit[/]"
            )
        else:
            bg.query_one("#hint", Label).update(
                "[#D29922]Cancelled.[/]  "
                "[#8B949E][#58A6FF]ctrl+n[/] new   [#58A6FF]ctrl+e[/] edit   [#58A6FF]q[/] quit[/]"
            )


if __name__ == "__main__":
    RuleEditorProto().run()
