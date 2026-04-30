"""
Stash prototype — rule editor with folder picker & location picker.

Demonstrates the full rule creation flow:
  - ctrl+n  open new rule editor (Browse button → FolderPickerScreen)
  - ctrl+e  open editor pre-filled with a fake existing rule
  - p       open LocationPickerScreen as a popup
  - q       quit

Run with:
    uv run python prototype/rule_editor.py
"""

import sys
import tempfile
import uuid
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Label

from stash.persistence.tinydb import FolderRule, LocationEntry, LocationsDB
from stash.tui.screens.location_picker import LocationPickerScreen
from stash.tui.screens.rule_editor import RuleEditorScreen


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FAKE_EXISTING_RULE = FolderRule(
    id="rule_001",
    name="Downloads Cleanup",
    target_path=str(Path.home() / "Downloads"),
    instructions="Remove files older than 30 days. Move videos to ~/Media/Videos.",
    interval_hours=6,
    allowed_tools=["ls", "glob", "mv"],
)

FAKE_LOCATIONS = [
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
    """

    BINDINGS = [
        Binding("p", "location_pick", "Location picker"),
        Binding("q", "app.quit",      "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Label(self._hint_text(), id="hint")

    def _hint_text(self) -> str:
        return (
            "[#8B949E]rule editor prototype[/]\n"
            "[#30363D]"
            "[on #21262D] ctrl+n [/] new rule   "
            "[on #21262D] ctrl+e [/] edit existing   "
            "[on #21262D] p [/] location picker   "
            "[on #21262D] q [/] quit"
            "[/]"
        )

    def action_location_pick(self) -> None:
        self.app.push_screen(LocationPickerScreen(), self.app._on_location_picked)

    def show_rule(self, rule: FolderRule | None) -> None:
        label = self.query_one("#hint", Label)
        if rule is None:
            label.update(f"[#D29922]Cancelled.[/]\n\n{self._hint_text()}")
        else:
            tools = ", ".join(rule.allowed_tools)
            label.update(
                f"[#3FB950]Rule saved[/]\n"
                f"[#C9D1D9]Name:[/]         [#58A6FF]{rule.name}[/]\n"
                f"[#C9D1D9]Target path:[/]  [#8B949E]{rule.target_path}[/]\n"
                f"[#C9D1D9]Instructions:[/] [#8B949E]{rule.instructions}[/]\n"
                f"[#C9D1D9]Interval:[/]     [#8B949E]{rule.interval_hours}h[/]\n"
                f"[#C9D1D9]Tools:[/]        [#8B949E]{tools}[/]\n\n"
                f"{self._hint_text()}"
            )

    def show_location(self, entry: LocationEntry | None) -> None:
        label = self.query_one("#hint", Label)
        if entry is None:
            label.update(f"[#D29922]Cancelled.[/]\n\n{self._hint_text()}")
        else:
            aliases = ", ".join(entry.aliases) if entry.aliases else "none"
            label.update(
                f"[#3FB950]Location registered[/]\n"
                f"[#C9D1D9]Name:[/]    [#58A6FF]{entry.name}[/]\n"
                f"[#C9D1D9]Aliases:[/] [#8B949E]{aliases}[/]\n"
                f"[#C9D1D9]Path:[/]    [#8B949E]{entry.path}[/]\n\n"
                f"{self._hint_text()}"
            )


# ---------------------------------------------------------------------------
# Demo app
# ---------------------------------------------------------------------------

class RuleEditorProto(App):

    CSS = """
    Screen { background: #0E0E0F; }
    """

    BINDINGS = [
        Binding("ctrl+n", "new_rule",  "New rule"),
        Binding("ctrl+e", "edit_rule", "Edit rule"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._locations_db = LocationsDB(Path(self._tmp.name))
        for entry in FAKE_LOCATIONS:
            self._locations_db.upsert(entry)

    def compose(self) -> ComposeResult:
        yield _BgScreen()

    def action_new_rule(self) -> None:
        self.push_screen(RuleEditorScreen(), self._on_rule_saved)

    def action_edit_rule(self) -> None:
        self.push_screen(RuleEditorScreen(FAKE_EXISTING_RULE), self._on_rule_saved)

    def _on_rule_saved(self, rule: FolderRule | None) -> None:
        self.query_one(_BgScreen).show_rule(rule)

    def _on_location_picked(self, entry: LocationEntry | None) -> None:
        if entry is not None:
            self._locations_db.upsert(entry)
        self.query_one(_BgScreen).show_location(entry)


if __name__ == "__main__":
    RuleEditorProto().run()
