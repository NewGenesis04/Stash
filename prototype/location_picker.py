"""
Stash prototype — location picker & registry screens.

Demonstrates both screens in isolation:
  - LocationPickerScreen opens immediately on launch
  - After a pick the result is shown on the background
  - Press p to re-open the picker
  - Press r to open the full registry manager (pre-seeded with fake entries)
  - Press q to quit

Run with:
    uv run python prototype/location_picker.py
"""

import sys
import tempfile
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Label

from stash.persistence.tinydb import LocationEntry, LocationsDB
from stash.tui.screens.location_picker import LocationPickerScreen
from stash.tui.screens.location_registry import LocationRegistryScreen


# ---------------------------------------------------------------------------
# Fake registry entries (seeded into the demo DB)
# ---------------------------------------------------------------------------

FAKE_ENTRIES = [
    LocationEntry(
        name="Movies",
        aliases=["films", "cinema"],
        path=str(Path.home() / "Videos"),
        added="2026-04-01T10:00:00+00:00",
        last_verified="2026-04-29T09:00:00+00:00",
    ),
    LocationEntry(
        name="Downloads",
        aliases=["dl"],
        path=str(Path.home() / "Downloads"),
        added="2026-03-15T08:30:00+00:00",
        last_verified="2026-04-29T09:00:00+00:00",
    ),
    LocationEntry(
        name="Work",
        aliases=["projects", "dev"],
        path=str(Path.home() / "Documents"),
        added="2026-04-10T14:00:00+00:00",
        last_verified="2026-04-28T17:00:00+00:00",
    ),
]


# ---------------------------------------------------------------------------
# Background screen
# ---------------------------------------------------------------------------

class _BgScreen(Screen):

    DEFAULT_CSS = """
    _BgScreen {
        background: #0E0E0F;
        align: center middle;
    }
    _BgScreen #hint {
        color: #8B949E;
        text-align: center;
    }
    _BgScreen #result {
        margin-top: 2;
        height: auto;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("p", "pick",     "Picker"),
        Binding("r", "registry", "Registry"),
        Binding("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(
                "[#8B949E]location picker prototype[/]\n"
                "[#30363D][on #21262D] p [/] picker   [on #21262D] r [/] registry   [on #21262D] q [/] quit[/]",
                id="hint",
            )
            yield Label("", id="result")

    def action_pick(self) -> None:
        self.app.push_screen(LocationPickerScreen(), self.app._on_picked)

    def action_registry(self) -> None:
        self.app.push_screen(LocationRegistryScreen(self.app._locations_db))

    def show_result(self, entry: LocationEntry | None) -> None:
        result = self.query_one("#result", Label)
        if entry is None:
            result.update("[#D29922]Cancelled[/]")
        else:
            aliases = ", ".join(entry.aliases) if entry.aliases else "none"
            result.update(
                f"[#3FB950]Registered[/]\n"
                f"[#C9D1D9]Name:[/]    [#58A6FF]{entry.name}[/]\n"
                f"[#C9D1D9]Aliases:[/] [#8B949E]{aliases}[/]\n"
                f"[#C9D1D9]Path:[/]    [#8B949E]{entry.path}[/]"
            )


# ---------------------------------------------------------------------------
# Demo app
# ---------------------------------------------------------------------------

class LocationPickerProto(App):

    CSS = """
    Screen { background: #0E0E0F; }
    """

    def __init__(self) -> None:
        super().__init__()
        # Use a temp file so the demo doesn't touch real stash data
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._locations_db = LocationsDB(Path(self._tmp.name))
        for entry in FAKE_ENTRIES:
            self._locations_db.upsert(entry)

    def compose(self) -> ComposeResult:
        yield _BgScreen()

    def on_mount(self) -> None:
        self.push_screen(LocationPickerScreen(), self._on_picked)

    def _on_picked(self, entry: LocationEntry | None) -> None:
        if entry is not None:
            self._locations_db.upsert(entry)
        self.query_one(_BgScreen).show_result(entry)


if __name__ == "__main__":
    LocationPickerProto().run()
