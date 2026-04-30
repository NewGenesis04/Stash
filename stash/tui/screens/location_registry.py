"""
LocationRegistryScreen — view and manage the location registry.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from stash.persistence.tinydb import LocationEntry, LocationsDB


class LocationRegistryScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    LocationRegistryScreen {
        align: center middle;
    }
    LocationRegistryScreen #dialog {
        width: 84;
        height: 30;
        background: #161B22;
        border: solid #30363D;
        border-top: solid #58A6FF;
    }
    LocationRegistryScreen #dialog-title {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        color: #58A6FF;
        text-style: bold;
        padding: 0 2;
        content-align: left middle;
    }
    LocationRegistryScreen #table-container {
        height: 1fr;
        padding: 1 2;
    }
    LocationRegistryScreen DataTable {
        height: 1fr;
        background: #0E0E0F;
    }
    LocationRegistryScreen #status-label {
        height: 1;
        padding: 0 2;
        color: #8B949E;
    }
    LocationRegistryScreen #dialog-footer {
        height: 5;
        border-top: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    LocationRegistryScreen #dialog-footer Button {
        height: 3;
        border: none;
        min-width: 0;
        padding: 0 2;
        margin-right: 1;
    }
    LocationRegistryScreen #btn-add    { background: #0D2B1A; color: #3FB950; }
    LocationRegistryScreen #btn-add:hover { background: #133d24; }
    LocationRegistryScreen #btn-edit   { background: #21262D; color: #C9D1D9; }
    LocationRegistryScreen #btn-edit:hover { background: #2D333B; }
    LocationRegistryScreen #btn-verify { background: #21262D; color: #C9D1D9; }
    LocationRegistryScreen #btn-verify:hover { background: #2D333B; }
    LocationRegistryScreen #btn-remove { background: #21262D; color: #8B949E; }
    LocationRegistryScreen #btn-remove:hover { background: #2B0D0D; color: #F85149; }
    LocationRegistryScreen #btn-close  { background: #21262D; color: #8B949E; }
    LocationRegistryScreen #btn-close:hover { background: #2D333B; }
    LocationRegistryScreen #key-hint {
        width: 1fr;
        height: 1;
        color: #30363D;
        text-align: right;
    }
    """

    BINDINGS = [
        Binding("escape", "close", show=False),
        Binding("ctrl+n", "add_location", "New", show=True),
    ]

    def __init__(self, locations_db: LocationsDB) -> None:
        super().__init__()
        self._locations_db = locations_db

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("location registry", id="dialog-title")
            with Vertical(id="table-container"):
                yield DataTable(id="locations-table", cursor_type="row")
            yield Label("", id="status-label")
            with Horizontal(id="dialog-footer"):
                yield Button("+ Add",    id="btn-add")
                yield Button("✎ Edit",   id="btn-edit")
                yield Button("↻ Verify", id="btn-verify")
                yield Button("✗ Remove", id="btn-remove")
                yield Button("Close",    id="btn-close")
                yield Label("ctrl+n · esc", id="key-hint")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Name", "Aliases", "Path", "Verified")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for entry in self._locations_db.all():
            aliases = ", ".join(entry.aliases) if entry.aliases else "—"
            verified = entry.last_verified[:10]
            table.add_row(entry.name, aliases, entry.path, verified, key=entry.name)

    def _selected_name(self) -> str | None:
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key.value is not None else None

    def action_close(self) -> None:
        self.dismiss(None)

    def action_add_location(self) -> None:
        from stash.tui.screens.location_picker import LocationPickerScreen
        self.app.push_screen(LocationPickerScreen(), self._on_entry_saved)

    def _on_entry_saved(self, entry: LocationEntry | None) -> None:
        if entry is None:
            return
        self._locations_db.upsert(entry)
        self._refresh_table()
        self.query_one("#status-label", Label).update(f"[#3FB950]Registered: {entry.name}[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id

        if bid == "btn-add":
            self.action_add_location()

        elif bid == "btn-edit":
            name = self._selected_name()
            if not name:
                self.query_one("#status-label", Label).update("[#F85149]Select a location first.[/]")
                return
            entry = self._locations_db.resolve(name)
            if entry:
                original_name = entry.name

                def _on_edited(updated: LocationEntry | None) -> None:
                    if updated is None:
                        return
                    if updated.name != original_name:
                        self._locations_db.delete(original_name)
                    self._locations_db.upsert(updated)
                    self._refresh_table()
                    self.query_one("#status-label", Label).update(f"[#3FB950]Updated: {updated.name}[/]")

                from stash.tui.screens.location_picker import LocationPickerScreen
                self.app.push_screen(LocationPickerScreen(entry=entry), _on_edited)

        elif bid == "btn-verify":
            name = self._selected_name()
            if not name:
                self.query_one("#status-label", Label).update("[#F85149]Select a location first.[/]")
                return
            entry = self._locations_db.resolve(name)
            if entry:
                ok, _ = self._locations_db.verify(entry)
                status = f"[#3FB950]{name}: path exists.[/]" if ok else f"[#F85149]{name}: path not found — re-register.[/]"
                self.query_one("#status-label", Label).update(status)
                self._refresh_table()

        elif bid == "btn-remove":
            name = self._selected_name()
            if not name:
                self.query_one("#status-label", Label).update("[#F85149]Select a location first.[/]")
                return
            self._locations_db.delete(name)
            self._refresh_table()
            self.query_one("#status-label", Label).update(f"[#8B949E]Removed: {name}[/]")

        elif bid == "btn-close":
            self.dismiss(None)
