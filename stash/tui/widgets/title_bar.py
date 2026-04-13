"""
TitleBar widget — top bar of the Stash TUI.

Shows the app name, Ollama status badge, active model badge, and active
rule count. Badges update live as health state changes.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


def _ollama_markup(state: str, dot: str = "●") -> str:
    if state == "online":
        return f"[on #0D2B1A] [#3FB950]{dot} ollama running[/] [/]"
    elif state == "offline":
        return "[on #2B0D0D] [#F85149]✗ ollama offline[/] [/]"
    else:
        return "[on #2B1D0A] [#D29922]◌ checking...[/] [/]"


def _model_markup(model: str) -> str:
    return f"[on #0D1F38] [#58A6FF]{model}[/] [/]"


def _rules_markup(count: int) -> str:
    label = f"◷ {count} rule{'s' if count != 1 else ''}"
    return f"[on #2B1D0A] [#D29922]{label}[/] [/]"


class TitleBar(Widget):
    """
    Fixed top bar. Public interface:
        set_ollama_status(available: bool)
        set_model(model: str)
        set_rule_count(count: int)
    """

    DEFAULT_CSS = """
    TitleBar {
        height: 3;
        background: #161B22;
        border-bottom: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
        dock: top;
    }
    TitleBar #app-name {
        color: #58A6FF;
        text-style: bold;
        width: auto;
        padding: 0 3 0 0;
    }
    TitleBar #badge-row {
        width: 1fr;
        height: 3;
        layout: horizontal;
        align: right middle;
    }
    TitleBar #ollama-badge {
        width: auto;
        height: 1;
        margin: 0 1;
    }
    TitleBar #model-badge {
        width: auto;
        height: 1;
        margin: 0 1;
        display: none;
    }
    TitleBar #rules-badge {
        width: auto;
        height: 1;
        margin: 0 1;
        display: none;
    }
    """

    _pulse_on: reactive[bool] = reactive(True)

    def __init__(self, model: str = "") -> None:
        super().__init__()
        self._model           = model
        self._ollama_state    = "unknown"   # "online" | "offline" | "unknown"

    def compose(self) -> ComposeResult:
        yield Label("[bold #58A6FF]stash[/]", id="app-name")
        with Horizontal(id="badge-row"):
            yield Label(_ollama_markup("unknown"), id="ollama-badge")
            yield Label("", id="model-badge")
            yield Label("", id="rules-badge")

    def on_mount(self) -> None:
        if self._model:
            self.set_model(self._model)
        self.set_interval(0.8, self._tick_pulse)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_ollama_status(self, available: bool) -> None:
        self._ollama_state = "online" if available else "offline"
        self._refresh_ollama_badge()

    def set_model(self, model: str) -> None:
        self._model = model
        badge = self.query_one("#model-badge", Label)
        if model:
            badge.update(_model_markup(model))
            badge.display = True
        else:
            badge.display = False

    def set_rule_count(self, count: int) -> None:
        badge = self.query_one("#rules-badge", Label)
        if count > 0:
            badge.update(_rules_markup(count))
            badge.display = True
        else:
            badge.display = False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _tick_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self._refresh_ollama_badge()

    def _refresh_ollama_badge(self) -> None:
        dot = "●" if self._pulse_on else "◉"
        self.query_one("#ollama-badge", Label).update(
            _ollama_markup(self._ollama_state, dot)
        )
