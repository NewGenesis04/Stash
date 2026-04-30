"""
FolderPickerScreen — minimal directory picker that returns a path string.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label


class FolderPickerScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    FolderPickerScreen {
        align: center middle;
    }
    FolderPickerScreen #dialog {
        width: 70;
        height: 32;
        background: #161B22;
        border: solid #30363D;
        border-top: solid #58A6FF;
    }
    FolderPickerScreen #dialog-title {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        color: #58A6FF;
        text-style: bold;
        padding: 0 2;
        content-align: left middle;
    }
    FolderPickerScreen #dir-tree {
        height: 1fr;
        border-bottom: solid #30363D;
        background: #0E0E0F;
    }
    FolderPickerScreen #selected-path {
        height: 1;
        padding: 0 2;
        color: #8B949E;
    }
    FolderPickerScreen #dialog-footer {
        height: 5;
        border-top: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    FolderPickerScreen #dialog-footer Button {
        height: 3;
        border: none;
        min-width: 0;
        padding: 0 2;
        margin-right: 1;
    }
    FolderPickerScreen #btn-select {
        background: #0D2B1A;
        color: #3FB950;
    }
    FolderPickerScreen #btn-select:hover { background: #133d24; }
    FolderPickerScreen #btn-cancel {
        background: #21262D;
        color: #8B949E;
    }
    FolderPickerScreen #btn-cancel:hover {
        background: #2B0D0D;
        color: #F85149;
    }
    FolderPickerScreen #key-hint {
        width: 1fr;
        height: 1;
        color: #30363D;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("ctrl+s", "select_folder", show=False),
    ]

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self._selected_path: str | None = initial_path or None

    def compose(self) -> ComposeResult:
        hint = self._selected_path or "select a folder below"
        with Vertical(id="dialog"):
            yield Label("select folder", id="dialog-title")
            yield DirectoryTree(str(Path.home()), id="dir-tree")
            yield Label(f"  {hint}", id="selected-path")
            with Horizontal(id="dialog-footer"):
                yield Button("✓ Select", id="btn-select")
                yield Button("✕ Cancel", id="btn-cancel")
                yield Label("ctrl+s · esc", id="key-hint")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected_path = str(event.path)
        self.query_one("#selected-path", Label).update(f"  {self._selected_path}")

    def action_select_folder(self) -> None:
        if self._selected_path:
            self.dismiss(self._selected_path)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn-select":
            self.action_select_folder()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
