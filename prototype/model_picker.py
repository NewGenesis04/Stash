"""
Stash prototype — model picker screen.

Modal overlay that lists available Ollama models and lets the user
select one with arrow keys + Enter.

Keys:
    ↑ / ↓   — navigate
    enter   — confirm selection
    escape  — cancel (no model change)
    q       — quit prototype

Run with:
    uv run python prototype/model_picker.py
"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Label, ListItem, ListView


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FAKE_MODELS = [
    "gemma3:4b",
    "gemma3:12b",
    "llama3.2:3b",
    "mistral:7b",
    "codellama:7b",
    "deepseek-r1:7b",
    "phi4:latest",
]


# ---------------------------------------------------------------------------
# ModelPickerScreen
# ---------------------------------------------------------------------------

class ModelPickerScreen(ModalScreen[str | None]):
    """
    Modal model selector. Dismisses with the chosen model name,
    or None if the user cancels.
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
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    ModelPickerScreen #dialog-title {
        width: 1fr;
        color: #58A6FF;
        text-style: bold;
    }
    ModelPickerScreen #dialog-key {
        width: auto;
        color: #8B949E;
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
    ModelPickerScreen #dialog-footer {
        height: 2;
        border-top: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
        color: #8B949E;
    }
    ModelPickerScreen #empty-state {
        height: 3;
        color: #8B949E;
        text-align: center;
        padding: 1 2;
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
                yield Label(
                    "No models found.\nRun [#58A6FF]ollama pull <model>[/] to get started.",
                    id="empty-state",
                )
            with Vertical(id="dialog-footer"):
                yield Label(
                    "[on #21262D][#C9D1D9] ↑↓ [/][/]  navigate   "
                    "[on #21262D][#C9D1D9] enter [/][/]  select   "
                    "[on #21262D][#C9D1D9] esc [/][/]  cancel"
                )

    def on_mount(self) -> None:
        if not self._models:
            return
        lv = self.query_one(ListView)
        # Pre-select current model if it's in the list
        if self._current and self._current in self._models:
            idx = self._models.index(self._current)
            lv.index = idx

    def action_select(self) -> None:
        if not self._models:
            return
        lv = self.query_one(ListView)
        if lv.index is not None:
            self.dismiss(self._models[lv.index])

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Double-confirm: selecting an item also triggers dismiss."""
        if lv := self.query_one(ListView):
            if lv.index is not None:
                self.dismiss(self._models[lv.index])


# ---------------------------------------------------------------------------
# Prototype app — wraps ModelPickerScreen in a minimal background
# ---------------------------------------------------------------------------

class _BgScreen(Screen):
    """Dark background so the modal has something to overlay."""

    DEFAULT_CSS = """
    _BgScreen {
        background: #0E0E0F;
        align: center middle;
    }
    """

    BINDINGS = [Binding("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Label(
            "[#8B949E]model picker prototype · press [#58A6FF]q[/] to quit[/]"
        )


class ModelPickerProto(App):

    CSS = """
    Screen { background: #0E0E0F; }
    """

    def on_mount(self) -> None:
        self.push_screen(
            ModelPickerScreen(FAKE_MODELS, current="gemma3:4b"),
            self._on_picked,
        )

    def _on_picked(self, model: str | None) -> None:
        if model:
            self.query_one(_BgScreen).query_one(Label).update(
                f"[#3FB950]Selected:[/] [#58A6FF]{model}[/]  [#8B949E](press q to quit)[/]"
            )
        else:
            self.query_one(_BgScreen).query_one(Label).update(
                "[#D29922]Cancelled[/]  [#8B949E](press q to quit)[/]"
            )

    def compose(self) -> ComposeResult:
        yield _BgScreen()


if __name__ == "__main__":
    ModelPickerProto().run()
