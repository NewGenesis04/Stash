"""
Stash prototype — sidebar widget.

Demonstrates folder rules list and audit log sections with live updates.

Keys:
    a   — append a random audit log entry
    s   — cycle the first rule's status dot (ok → scheduled → paused → ok)
    q   — quit

Run with:
    uv run python prototype/sidebar.py
"""

import random
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, RichLog


# ---------------------------------------------------------------------------
# Fake data
# ---------------------------------------------------------------------------

FAKE_RULES = [
    {
        "id": "rule_001",
        "name": "Downloads Cleanup",
        "interval_hours": 6,
        "allowed_tools": ["ls", "mv", "rm", "glob"],
        "status": "ok",
    },
    {
        "id": "rule_002",
        "name": "Desktop Organiser",
        "interval_hours": 24,
        "allowed_tools": ["ls", "mv", "mkdir"],
        "status": "scheduled",
    },
    {
        "id": "rule_003",
        "name": "Archive Old Docs",
        "interval_hours": 168,
        "allowed_tools": ["glob", "mv"],
        "status": "paused",
    },
]

FAKE_ENTRIES = [
    ("glob",   "~/Downloads → 23 files found"),
    ("mv",     "report_2024.pdf → ~/Docs/Reports"),
    ("mv",     "invoice_jan.pdf → ~/Docs/Finance"),
    ("rm",     "tmp_build.zip → deleted"),
    ("ls",     "~/Desktop → 8 items"),
    ("glob",   "*.log → 4 files matched"),
    ("rename", "IMG_001.jpg → photo_beach.jpg"),
    ("mkdir",  "~/Docs/Archive/2024 → created"),
]

_STATUS_CYCLE = ["ok", "scheduled", "paused"]


# ---------------------------------------------------------------------------
# Rich markup helpers
# ---------------------------------------------------------------------------

def _tool_chip(tool: str) -> str:
    return f"[on #0D2B1A][#3FB950] {tool} [/][/]"


def _status_dot(status: str) -> str:
    if status == "ok":
        return "[#3FB950]●[/]"
    elif status == "scheduled":
        return "[#58A6FF]◷[/]"
    else:
        return "[#8B949E]○[/]"


def _keybind_chip(key: str) -> str:
    return f"[on #21262D][#58A6FF] {key} [/][/]"


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

class PaneHeader(Widget):
    """Muted uppercase section label + right-aligned keybinding chip."""

    DEFAULT_CSS = """
    PaneHeader {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
    }
    PaneHeader #pane-title {
        width: 1fr;
        height: 1;
        color: #8B949E;
    }
    PaneHeader #pane-key {
        width: auto;
        height: 1;
    }
    """

    def __init__(self, title: str, keybind: str) -> None:
        super().__init__()
        self._title   = title
        self._keybind = keybind

    def compose(self) -> ComposeResult:
        yield Label(self._title.upper(), id="pane-title")
        yield Label(_keybind_chip(self._keybind), id="pane-key")


class RuleItem(Widget):
    """Single rule row: status dot · name · interval + tools."""

    DEFAULT_CSS = """
    RuleItem {
        height: auto;
        padding: 1 1;
        border-bottom: solid #30363D;
    }
    RuleItem:hover {
        background: #21262D;
    }
    RuleItem #top-row {
        layout: horizontal;
        height: 1;
        width: 100%;
    }
    RuleItem #dot {
        width: 3;
        height: 1;
    }
    RuleItem #name {
        width: 1fr;
        height: 1;
        color: #C9D1D9;
    }
    RuleItem #meta {
        height: 1;
        color: #8B949E;
        padding: 0 0 0 3;
    }
    """

    def __init__(self, rule: dict) -> None:
        super().__init__(id=f"rule-{rule['id']}")
        self._rule = rule

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-row"):
            yield Label(_status_dot(self._rule["status"]), id="dot")
            yield Label(self._rule["name"], id="name")
        tools    = "  ".join(self._rule["allowed_tools"])
        interval = self._rule["interval_hours"]
        yield Label(f"every {interval}h  ·  {tools}", id="meta")

    def set_status(self, status: str) -> None:
        self._rule["status"] = status
        self.query_one("#dot", Label).update(_status_dot(status))


class FolderRulesSection(Widget):
    """Pane header + rule list."""

    DEFAULT_CSS = """
    FolderRulesSection {
        height: auto;
        width: 100%;
        layout: vertical;
    }
    """

    def compose(self) -> ComposeResult:
        yield PaneHeader("Folder Rules", "ctrl+r")
        for rule in FAKE_RULES:
            yield RuleItem(rule)

    def update_rule_status(self, rule_id: str, status: str) -> None:
        item = self.query_one(f"#rule-{rule_id}", RuleItem)
        item.set_status(status)


class AuditLogSection(Widget):
    """Pane header + scrollable audit log."""

    DEFAULT_CSS = """
    AuditLogSection {
        height: 1fr;
        width: 100%;
        layout: vertical;
    }
    AuditLogSection #log {
        height: 1fr;
        background: #0E0E0F;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield PaneHeader("Audit Log", "ctrl+l")
        yield RichLog(id="log", markup=True, auto_scroll=True)

    def on_mount(self) -> None:
        # Pre-populate with fake entries
        for tool, result in FAKE_ENTRIES:
            self.append_entry(tool, result)

    def append_entry(self, tool: str, result: str) -> None:
        ts   = datetime.now().strftime("%H:%M:%S")
        line = f"[#8B949E]{ts}[/]  {_tool_chip(tool)}  [#C9D1D9]{result}[/]"
        self.query_one("#log", RichLog).write(line)


# ---------------------------------------------------------------------------
# Sidebar widget
# ---------------------------------------------------------------------------

class SidebarWidget(Widget):
    """Full sidebar: folder rules on top, audit log below."""

    DEFAULT_CSS = """
    SidebarWidget {
        width: 100%;
        height: 100%;
        layout: vertical;
        background: #161B22;
        border-left: solid #30363D;
    }
    """

    def compose(self) -> ComposeResult:
        yield FolderRulesSection()
        yield AuditLogSection()

    def load_rules(self, rules: list[dict]) -> None:
        section = self.query_one(FolderRulesSection)
        for child in list(section.query(RuleItem)):
            child.remove()
        for rule in rules:
            section.mount(RuleItem(rule))

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self.query_one(FolderRulesSection).update_rule_status(rule_id, status)

    def append_audit_entry(self, tool: str, result: str) -> None:
        self.query_one(AuditLogSection).append_entry(tool, result)

    def focus_audit_log(self) -> None:
        self.query_one("#log").focus()

    def focus_rules(self) -> None:
        self.query_one(FolderRulesSection).focus()


# ---------------------------------------------------------------------------
# Prototype app
# ---------------------------------------------------------------------------

class SidebarProto(App):

    CSS = """
    Screen {
        layout: horizontal;
        background: #0E0E0F;
    }
    #main-area {
        width: 1fr;
        height: 100%;
        align: center middle;
    }
    #hint {
        color: #8B949E;
    }
    #sidebar-col {
        width: 44;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("a", "add_entry",     "Add audit entry"),
        Binding("s", "cycle_status",  "Cycle rule status"),
        Binding("q", "quit",          "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="main-area"):
            yield Label(
                "[#8B949E]a[/] add audit entry   [#8B949E]s[/] cycle rule status   [#8B949E]q[/] quit",
                id="hint",
            )
        with Vertical(id="sidebar-col"):
            yield SidebarWidget()

    def action_add_entry(self) -> None:
        tool, result = random.choice(FAKE_ENTRIES)
        self.query_one(SidebarWidget).append_audit_entry(tool, result)

    def action_cycle_status(self) -> None:
        rule    = FAKE_RULES[0]
        current = rule["status"]
        nxt     = _STATUS_CYCLE[(_STATUS_CYCLE.index(current) + 1) % len(_STATUS_CYCLE)]
        rule["status"] = nxt
        self.query_one(SidebarWidget).update_rule_status(rule["id"], nxt)


if __name__ == "__main__":
    SidebarProto().run()
