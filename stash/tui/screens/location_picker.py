"""
LocationPickerScreen — directory picker for registering a named location.
"""

from datetime import datetime, UTC
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label

from stash.persistence.tinydb import LocationEntry


class LocationPickerScreen(ModalScreen[LocationEntry | None]):
    DEFAULT_CSS = """
    LocationPickerScreen {
        align: center middle;
    }
    LocationPickerScreen #dialog {
        width: 70;
        height: 40;
        background: #161B22;
        border: solid #30363D;
        border-top: solid #58A6FF;
    }
    LocationPickerScreen #dialog-title {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        color: #58A6FF;
        text-style: bold;
        padding: 0 2;
        content-align: left middle;
    }
    LocationPickerScreen #dir-tree {
        height: 18;
        border-bottom: solid #30363D;
        background: #0E0E0F;
    }
    LocationPickerScreen #selected-path {
        height: 1;
        padding: 0 2;
        color: #8B949E;
    }
    LocationPickerScreen #form-body {
        height: auto;
        padding: 0 2;
    }
    LocationPickerScreen .field-label {
        height: 1;
        color: #8B949E;
        margin-top: 1;
        margin-bottom: 0;
    }
    LocationPickerScreen Input {
        background: #0E0E0F;
        border: solid #30363D;
        color: #C9D1D9;
        height: 3;
    }
    LocationPickerScreen Input:focus {
        border: solid #58A6FF;
    }
    LocationPickerScreen #error-label {
        height: 1;
        color: #F85149;
        margin-top: 1;
    }
    LocationPickerScreen #dialog-footer {
        height: 5;
        border-top: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    LocationPickerScreen #dialog-footer Button {
        height: 3;
        border: none;
        min-width: 0;
        padding: 0 2;
        margin-right: 1;
    }
    LocationPickerScreen #btn-save {
        background: #0D2B1A;
        color: #3FB950;
    }
    LocationPickerScreen #btn-save:hover { background: #133d24; }
    LocationPickerScreen #btn-cancel {
        background: #21262D;
        color: #8B949E;
    }
    LocationPickerScreen #btn-cancel:hover {
        background: #2B0D0D;
        color: #F85149;
    }
    LocationPickerScreen #key-hint {
        width: 1fr;
        height: 1;
        color: #30363D;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "save", show=False),
    ]

    def __init__(self, suggested_name: str = "", entry: LocationEntry | None = None) -> None:
        super().__init__()
        self._suggested_name = suggested_name
        self._entry = entry
        self._selected_path: str | None = entry.path if entry else None

    def compose(self) -> ComposeResult:
        title = "edit location" if self._entry else "register location"
        name = self._entry.name if self._entry else self._suggested_name
        aliases = ", ".join(self._entry.aliases) if self._entry else ""
        path_hint = self._selected_path or "select a folder below"

        with Vertical(id="dialog"):
            yield Label(title, id="dialog-title")
            yield DirectoryTree(str(Path.home()), id="dir-tree")
            yield Label(f"  {path_hint}", id="selected-path")
            with Vertical(id="form-body"):
                yield Label("Name", classes="field-label")
                yield Input(value=name, placeholder="Movies", id="inp-name")
                yield Label("Aliases  (comma-separated, optional)", classes="field-label")
                yield Input(value=aliases, placeholder="films, cinema", id="inp-aliases")
                yield Label("", id="error-label")
            with Horizontal(id="dialog-footer"):
                yield Button("✓ Save", id="btn-save")
                yield Button("✕ Cancel", id="btn-cancel")
                yield Label("ctrl+s · esc", id="key-hint")

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self._selected_path = str(event.path)
        self.query_one("#selected-path", Label).update(f"  {self._selected_path}")

    def action_save(self) -> None:
        name = self.query_one("#inp-name", Input).value.strip()
        aliases_raw = self.query_one("#inp-aliases", Input).value.strip()
        aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else []
        error = self.query_one("#error-label", Label)

        if not name:
            error.update("[#F85149]Name is required.[/]")
            self.query_one("#inp-name", Input).focus()
            return
        if not self._selected_path:
            error.update("[#F85149]Select a folder first.[/]")
            return

        now = datetime.now(UTC).isoformat()
        self.dismiss(LocationEntry(
            name=name,
            aliases=aliases,
            path=self._selected_path,
            added=self._entry.added if self._entry else now,
            last_verified=now,
        ))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
