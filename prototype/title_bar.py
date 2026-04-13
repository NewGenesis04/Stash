"""
Stash prototype — title bar widget.

Demonstrates the app name, Ollama status badge (all three states),
model badge, rules badge, and the pulsing dot animation.

Keys:
    o   — toggle Ollama online / offline
    u   — reset to checking... (unknown)
    m   — cycle model badge (gemma4:4b → gemma4:12b → llama3.2:3b → hidden)
    r   — cycle active rule count (0 → 1 → 3 → 0)
    q   — quit

Run with:
    uv run python prototype/title_bar.py
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


# ---------------------------------------------------------------------------
# Badge markup helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# TitleBar widget
# ---------------------------------------------------------------------------

class TitleBar(Widget):

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

    def __init__(self) -> None:
        super().__init__()
        self._ollama_state = "unknown"

    def compose(self) -> ComposeResult:
        yield Label("[bold #58A6FF]stash[/]", id="app-name")
        with Horizontal(id="badge-row"):
            yield Label(_ollama_markup("unknown"), id="ollama-badge")
            yield Label("", id="model-badge")
            yield Label("", id="rules-badge")

    def on_mount(self) -> None:
        self.set_interval(0.8, self._tick_pulse)

    def set_ollama_status(self, available: bool) -> None:
        self._ollama_state = "online" if available else "offline"
        self._refresh_ollama_badge()

    def set_ollama_unknown(self) -> None:
        self._ollama_state = "unknown"
        self._refresh_ollama_badge()

    def set_model(self, model: str) -> None:
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

    def _tick_pulse(self) -> None:
        self._pulse_on = not self._pulse_on
        self._refresh_ollama_badge()

    def _refresh_ollama_badge(self) -> None:
        dot = "●" if self._pulse_on else "◉"
        self.query_one("#ollama-badge", Label).update(
            _ollama_markup(self._ollama_state, dot)
        )


# ---------------------------------------------------------------------------
# Prototype app
# ---------------------------------------------------------------------------

_MODELS      = ["gemma4:4b", "gemma4:12b", "llama3.2:3b", ""]
_RULE_COUNTS = [0, 1, 3]


class TitleBarProto(App):

    CSS = """
    Screen {
        background: #0E0E0F;
        layout: vertical;
    }
    #body {
        width: 100%;
        height: 1fr;
        align: center middle;
    }
    #hint {
        color: #8B949E;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("o", "toggle_ollama", "Toggle online/offline"),
        Binding("u", "set_unknown",   "Set checking..."),
        Binding("m", "cycle_model",   "Cycle model badge"),
        Binding("r", "cycle_rules",   "Cycle rule count"),
        Binding("q", "quit",          "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._ollama_online  = False
        self._model_idx      = 0
        self._rule_idx       = 0

    def compose(self) -> ComposeResult:
        yield TitleBar()
        with Vertical(id="body"):
            yield Label(
                "[#8B949E]o[/] ollama   "
                "[#8B949E]u[/] checking   "
                "[#8B949E]m[/] model   "
                "[#8B949E]r[/] rules   "
                "[#8B949E]q[/] quit",
                id="hint",
            )

    def action_toggle_ollama(self) -> None:
        self._ollama_online = not self._ollama_online
        self.query_one(TitleBar).set_ollama_status(self._ollama_online)

    def action_set_unknown(self) -> None:
        self.query_one(TitleBar).set_ollama_unknown()

    def action_cycle_model(self) -> None:
        self._model_idx = (self._model_idx + 1) % len(_MODELS)
        self.query_one(TitleBar).set_model(_MODELS[self._model_idx])

    def action_cycle_rules(self) -> None:
        self._rule_idx = (self._rule_idx + 1) % len(_RULE_COUNTS)
        self.query_one(TitleBar).set_rule_count(_RULE_COUNTS[self._rule_idx])


if __name__ == "__main__":
    TitleBarProto().run()
