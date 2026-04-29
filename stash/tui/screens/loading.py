"""
Loading screen — boot splash shown while the app initialises.

Displays the STASH ASCII art with a gradient colour sweep, fading status
messages, and a fill progress bar. Dismisses itself after 5 seconds and
passes the pre-computed HealthResult back to the caller via dismiss().
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Label, Static

from stash.health.ollama import HealthResult


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_BLUE   = (0x58, 0xA6, 0xFF)
_PURPLE = (0x89, 0x57, 0xE5)
_GREEN  = (0x3F, 0xB9, 0x50)
_STOPS  = [_BLUE, _PURPLE, _GREEN, _BLUE]


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _sweep_color(phase: float) -> str:
    """Map phase [0.0, 1.0] → hex colour across the 3-stop gradient cycle."""
    pos = phase * 3
    i   = int(pos) % 3
    t   = pos - int(pos)
    c1, c2 = _STOPS[i], _STOPS[i + 1]
    return f"#{_lerp(c1[0], c2[0], t):02x}{_lerp(c1[1], c2[1], t):02x}{_lerp(c1[2], c2[2], t):02x}"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

_ROWS = [
    " ██████╗████████╗ █████╗ ██████╗██╗  ██╗",
    "██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║  ██║",
    "╚█████╗    ██║   ███████║╚█████╗ ███████║",
    " ╚═══██╗   ██║   ██╔══██║ ╚═══██╗██╔══██║",
    "██████╔╝   ██║   ██║  ██║██████╔╝██║  ██║",
    "╚═════╝    ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝",
]

_OFFSETS = [i / len(_ROWS) for i in range(len(_ROWS))]

_STATUS_MESSAGES = [
    "Connecting to Ollama...",
    "Loading rules...",
    "Warming up...",
    "Ready",
]

_SHOW_AT = [0.2, 1.3, 2.5, 3.8]
_HOLD    = 0.7


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------

class _AsciiArt(Widget):
    """STASH block text — gradient colour sweeps across rows at 20 fps."""

    DEFAULT_CSS = """
    _AsciiArt {
        height: auto;
        width: auto;
    }
    _AsciiArt Label {
        height: 1;
        width: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._tick = 0

    def compose(self) -> ComposeResult:
        for i, row in enumerate(_ROWS):
            yield Label(row, id=f"arow-{i}")

    def on_mount(self) -> None:
        self.set_interval(1 / 20, self._advance)

    def _advance(self) -> None:
        self._tick += 1
        cycle_pos = (self._tick % 80) / 80
        for i, label in enumerate(self.query(Label)):
            phase = (cycle_pos + _OFFSETS[i]) % 1.0
            label.update(f"[{_sweep_color(phase)}]{_ROWS[i]}[/]")


class _BootProgressBar(Widget):
    """Thin 1-cell fill bar. Animate `progress` (0.0–1.0) to drive it."""

    progress: reactive[float] = reactive(0.0)

    DEFAULT_CSS = """
    _BootProgressBar {
        height: 1;
        width: 100%;
        background: #21262D;
    }
    _BootProgressBar #fill {
        height: 1;
        width: 0%;
        background: #3FB950;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="fill")

    def watch_progress(self, value: float) -> None:
        pct = max(0.0, min(100.0, value * 100))
        self.query_one("#fill").styles.width = f"{pct:.1f}%"


class _StatusSection(Widget):
    """Fading status messages + progress bar, timed to the 5-second splash."""

    DEFAULT_CSS = """
    _StatusSection {
        height: auto;
        width: 100%;
        layout: vertical;
        align: center middle;
    }
    _StatusSection #status-label {
        height: 1;
        width: 80%;
        text-align: center;
        color: #3FB950;
    }
    _StatusSection _BootProgressBar {
        margin-top: 1;
        width: 80%;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", id="status-label")
        yield _BootProgressBar()

    def on_mount(self) -> None:
        self.query_one("#status-label").styles.opacity = 0.0
        for i, t in enumerate(_SHOW_AT):
            self.set_timer(t, lambda idx=i: self._show(idx))

    def _show(self, index: int) -> None:
        label   = self.query_one("#status-label", Label)
        bar     = self.query_one(_BootProgressBar)
        is_last = index == len(_STATUS_MESSAGES) - 1

        label.update(_STATUS_MESSAGES[index])
        label.styles.animate("opacity", value=1.0, duration=0.25)
        bar.animate("progress", (index + 1) / len(_STATUS_MESSAGES), duration=0.8)

        if not is_last:
            self.set_timer(_HOLD, lambda: label.styles.animate("opacity", value=0.0, duration=0.2))


# ---------------------------------------------------------------------------
# Screen
# ---------------------------------------------------------------------------

class LoadingScreen(Screen[HealthResult | None]):
    """
    Boot splash. Dismisses with the HealthResult after 5 seconds so the
    app can decide whether to push the model picker or go straight to main.
    """

    DEFAULT_CSS = """
    LoadingScreen {
        background: #0E0E0F;
        align: center middle;
    }
    LoadingScreen #body {
        width: auto;
        height: auto;
        layout: vertical;
        align: center middle;
    }
    LoadingScreen #descriptor {
        height: auto;
        width: auto;
        layout: vertical;
        margin-top: 2;
        align: center middle;
    }
    LoadingScreen #desc-line {
        color: #8B949E;
        text-align: center;
        height: 1;
        width: auto;
    }
    LoadingScreen #by-line {
        color: #8B949E;
        opacity: 0.4;
        text-align: center;
        height: 1;
        width: auto;
        text-style: bold;
    }
    LoadingScreen #status-wrap {
        margin-top: 3;
        width: 42;
        height: auto;
    }
    LoadingScreen #corners {
        dock: bottom;
        height: 1;
        width: 100%;
        padding: 0 2;
    }
    LoadingScreen #corner-bl {
        width: 1fr;
        color: #8B949E;
        opacity: 0.25;
        height: 1;
    }
    LoadingScreen #corner-br {
        width: 1fr;
        color: #8B949E;
        opacity: 0.25;
        text-align: right;
        height: 1;
    }
    """

    def __init__(self, health_result: HealthResult | None = None) -> None:
        super().__init__()
        self._health_result = health_result

    def compose(self) -> ComposeResult:
        with Vertical(id="body"):
            yield _AsciiArt()
            with Vertical(id="descriptor"):
                yield Label("Local-first file management agent", id="desc-line")
                yield Label("BY NEWGENESIS", id="by-line")
            with Vertical(id="status-wrap"):
                yield _StatusSection()
        with Horizontal(id="corners"):
            yield Label("NODE_SYSTEM_V4.0.2  ● ENCRYPTION: AES-256", id="corner-bl")
            yield Label("KERNEL_BOOT: OK  IO_PORT: 8080", id="corner-br")

    def on_mount(self) -> None:
        def _dismiss() -> None:
            self.dismiss(self._health_result)
        self.set_timer(5.0, _dismiss)
