"""
Model picker screen — shown on first run or when the configured model is missing.

Fetches available models from Ollama, lets the user select one, then saves
the selection to config.toml before dismissing. Dismissed with the selected
model name, or None if the user cancels.

Two states:
  - models found   → scrollable list with arrow-key navigation
  - no models      → text input for manual entry + pull instructions
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, ListItem, ListView


class ModelPickerScreen(ModalScreen[str | None]):
    """
    Receives the list of available models.
    Dismisses with the selected model name, or None if cancelled.
    """

    DEFAULT_CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    ModelPickerScreen #dialog {
        width: 56;
        height: auto;
        max-height: 30;
        background: #161B22;
        border: solid #30363D;
        border-top: solid #58A6FF;
    }
    ModelPickerScreen #dialog-header {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        align: left middle;
        padding: 0 2;
    }
    ModelPickerScreen #dialog-title {
        color: #58A6FF;
        text-style: bold;
    }
    ModelPickerScreen #subtitle {
        height: 1;
        color: #8B949E;
        padding: 1 2 0 2;
    }
    ModelPickerScreen #model-list {
        height: auto;
        max-height: 20;
        margin: 1 2;
        background: #0E0E0F;
        border: solid #30363D;
    }
    ModelPickerScreen ListView {
        background: #0E0E0F;
    }
    ModelPickerScreen ListItem {
        background: #0E0E0F;
        color: #8B949E;
        padding: 0 2;
        height: 1;
    }
    ModelPickerScreen ListItem:hover {
        background: #1C2128;
        color: #C9D1D9;
    }
    ModelPickerScreen ListItem.--highlight {
        background: #0D1F38;
        color: #58A6FF;
    }
    ModelPickerScreen #manual-area {
        margin: 1 2;
        height: auto;
    }
    ModelPickerScreen #manual-label {
        color: #8B949E;
        height: 1;
        margin-bottom: 1;
    }
    ModelPickerScreen #manual-input {
        background: #0E0E0F;
        border: solid #30363D;
        color: #C9D1D9;
        height: 3;
    }
    ModelPickerScreen #manual-input:focus {
        border: solid #58A6FF;
    }
    ModelPickerScreen #pull-hint {
        color: #8B949E;
        height: 1;
        padding: 0 0 0 0;
        margin-top: 1;
    }
    ModelPickerScreen #dialog-footer {
        height: 2;
        border-top: solid #30363D;
        align: left middle;
        padding: 0 2;
        color: #8B949E;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter",  "select", "Select", show=False),
    ]

    def __init__(self, available_models: list[str], current: str = "") -> None:
        super().__init__()
        self._models  = available_models
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            with Vertical(id="dialog-header"):
                yield Label("select a model", id="dialog-title")

            if self._models:
                yield Label(
                    f"[#8B949E]{len(self._models)} model{'s' if len(self._models) != 1 else ''} found on ollama[/]",
                    id="subtitle",
                )
                with Vertical(id="model-list"):
                    yield ListView(
                        *[
                            ListItem(Label(m), id=f"model-{i}")
                            for i, m in enumerate(self._models)
                        ]
                    )
            else:
                with Vertical(id="manual-area"):
                    yield Label(
                        "No models detected. Enter a model name manually:",
                        id="manual-label",
                    )
                    yield Input(
                        placeholder="e.g. gemma3:4b",
                        id="manual-input",
                    )
                    yield Label(
                        "[#58A6FF]ollama pull <name>[/]  to download a model first",
                        id="pull-hint",
                    )

            with Vertical(id="dialog-footer"):
                if self._models:
                    yield Label(
                        "[on #21262D][#C9D1D9] ↑↓ [/][/]  navigate   "
                        "[on #21262D][#C9D1D9] enter [/][/]  select   "
                        "[on #21262D][#C9D1D9] esc [/][/]  cancel"
                    )
                else:
                    yield Label(
                        "[on #21262D][#C9D1D9] enter [/][/]  confirm   "
                        "[on #21262D][#C9D1D9] esc [/][/]  cancel"
                    )

    def on_mount(self) -> None:
        if self._models:
            lv = self.query_one(ListView)
            if self._current in self._models:
                lv.index = self._models.index(self._current)
        else:
            self.query_one("#manual-input", Input).focus()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_select(self) -> None:
        if self._models:
            lv = self.query_one(ListView)
            if lv.index is not None:
                self.dismiss(self._models[lv.index])
        else:
            value = self.query_one("#manual-input", Input).value.strip()
            if value:
                self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, _: ListView.Selected) -> None:
        """Selecting a row (Enter on highlighted item) also confirms."""
        lv = self.query_one(ListView)
        if lv.index is not None:
            self.dismiss(self._models[lv.index])
