"""
Rule editor screen — create and edit folder rules.

Pushed onto the screen stack from ctrl+n (new) or a future rule list action (edit).
Dismissed with the saved FolderRule, or None if the user cancels.
"""

import uuid

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

from stash.persistence.tinydb import FolderRule


_ALL_TOOLS = ["ls", "glob", "mv", "mkdir", "rm", "rename"]

_INTERVAL_OPTIONS: list[tuple[str, int]] = [
    ("Every hour",    1),
    ("Every 6 hours", 6),
    ("Every 12 hours", 12),
    ("Every day",     24),
    ("Every 3 days",  72),
    ("Every week",    168),
]


class RuleEditorScreen(ModalScreen[FolderRule | None]):
    """
    Modal form for creating or editing a FolderRule.
    Pass rule=None to create; pass an existing FolderRule to edit.
    """

    DEFAULT_CSS = """
    RuleEditorScreen {
        align: center middle;
    }
    RuleEditorScreen #dialog {
        width: 60;
        height: auto;
        max-height: 36;
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
        max-height: 26;
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
        border: solid #30363D;
        height: 3;
        margin-bottom: 0;
    }
    RuleEditorScreen Select:focus {
        border: solid #58A6FF;
    }
    RuleEditorScreen #tools-row {
        height: auto;
        layout: horizontal;
        margin-top: 0;
    }
    RuleEditorScreen #tools-row Checkbox {
        height: 1;
        border: none;
        background: transparent;
        padding: 0 1 0 0;
        margin: 0;
    }
    RuleEditorScreen #chk-enabled {
        height: 1;
        border: none;
        background: transparent;
        padding: 0;
        margin-top: 1;
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
    RuleEditorScreen #btn-save:hover { background: #133d24; }
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
        color: #30363D;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save",   "Save",   show=False),
    ]

    def __init__(self, rule: FolderRule | None = None) -> None:
        super().__init__()
        self.rule = rule  # None = creating new

    def compose(self) -> ComposeResult:
        is_new    = self.rule is None
        title     = "new rule" if is_new else "edit rule"
        name      = "" if is_new else self.rule.name
        path      = "" if is_new else self.rule.target_path
        instruct  = "" if is_new else self.rule.instructions
        interval  = 6 if is_new else self.rule.interval_hours
        tools_on  = set(_ALL_TOOLS) if is_new else set(self.rule.allowed_tools)
        enabled   = True if is_new else self.rule.enabled

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
                yield Select(
                    _INTERVAL_OPTIONS,
                    value=interval,
                    id="sel-interval",
                )

                yield Label("Allowed tools", classes="field-label")
                with Horizontal(id="tools-row"):
                    for tool in _ALL_TOOLS:
                        yield Checkbox(tool, value=(tool in tools_on), id=f"tool-{tool}")

                yield Checkbox("Enabled", value=enabled, id="chk-enabled")
                yield Label("", id="error-label")

            with Horizontal(id="dialog-footer"):
                yield Button("✓ Save",   id="btn-save")
                yield Button("✕ Cancel", id="btn-cancel")
                yield Label("ctrl+s · esc", id="key-hint")

    def on_mount(self) -> None:
        self.query_one("#inp-name", Input).focus()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_save(self) -> None:
        rule = self._build_rule()
        if rule:
            self.dismiss(rule)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_rule(self) -> FolderRule | None:
        name     = self.query_one("#inp-name", Input).value.strip()
        path     = self.query_one("#inp-path", Input).value.strip()
        instruct = self.query_one("#inp-instructions", Input).value.strip()
        interval = self.query_one("#sel-interval", Select).value
        tools    = [t for t in _ALL_TOOLS if self.query_one(f"#tool-{t}", Checkbox).value]
        enabled  = self.query_one("#chk-enabled", Checkbox).value

        error = self.query_one("#error-label", Label)

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

        kwargs = dict(
            id=self.rule.id if self.rule else str(uuid.uuid4()),
            name=name,
            target_path=path,
            instructions=instruct,
            allowed_tools=tools,
            interval_hours=int(interval),
            enabled=enabled,
            last_run=self.rule.last_run if self.rule else None,
            last_run_status=self.rule.last_run_status if self.rule else None,
        )
        if self.rule:
            kwargs["created_at"] = self.rule.created_at  # preserve original timestamp
        return FolderRule(**kwargs)
