"""
SidebarWidget — folder rules list and live audit log.

Two sections stacked vertically:
  FolderRulesSection  — one RuleItem per FolderRule; status dot updates live
  AuditLogSection     — scrolling RichLog; entries appended by the agent/scheduler

Public API (called by StashApp):
  load_rules(rules)                  — replace the rule list with fresh data
  update_rule_status(rule_id, status)— update a rule's status dot live
  append_audit_entry(tool, result)   — add a line to the audit log
  focus_audit_log()                  — focus the log for keyboard scrolling
  focus_rules()                      — focus the rules section
"""

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Label, RichLog

from stash.persistence.tinydb import FolderRule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tool_chip(tool: str) -> str:
    return f"[on #0D2B1A][#3FB950] {tool} [/][/]"


def _keybind_chip(key: str) -> str:
    return f"[on #21262D][#58A6FF] {key} [/][/]"


def _rule_status(rule: FolderRule) -> str:
    """Derive display status from rule fields."""
    if not rule.enabled:
        return "paused"
    if rule.last_run_status == "ok":
        return "ok"
    if rule.last_run_status is None:
        return "scheduled"
    return "error"


def _status_dot(status: str) -> str:
    if status == "ok":
        return "[#3FB950]●[/]"
    elif status == "scheduled":
        return "[#58A6FF]◷[/]"
    elif status == "error":
        return "[#F85149]●[/]"
    else:  # paused
        return "[#8B949E]○[/]"


# ---------------------------------------------------------------------------
# PaneHeader
# ---------------------------------------------------------------------------

class PaneHeader(Widget):
    DEFAULT_CSS = """
    PaneHeader {
        height: 2;
        background: #161B22;
        border-bottom: solid #30363D;
        layout: horizontal;
        align: left middle;
        padding: 0 1;
    }
    PaneHeader #pane-title { width: 1fr; height: 1; color: #8B949E; }
    PaneHeader #pane-key   { width: auto; height: 1; }
    """

    def __init__(self, title: str, keybind: str) -> None:
        super().__init__()
        self._title   = title
        self._keybind = keybind

    def compose(self) -> ComposeResult:
        yield Label(self._title.upper(), id="pane-title")
        yield Label(_keybind_chip(self._keybind), id="pane-key")


# ---------------------------------------------------------------------------
# RuleItem
# ---------------------------------------------------------------------------

class RuleItem(Widget):
    """Single rule row: status dot · name · interval + tools."""

    DEFAULT_CSS = """
    RuleItem {
        height: auto;
        padding: 1 1;
        border-bottom: solid #30363D;
    }
    RuleItem:hover { background: #21262D; }
    RuleItem #top-row {
        layout: horizontal;
        height: 1;
        width: 100%;
    }
    RuleItem #dot  { width: 3;   height: 1; }
    RuleItem #name { width: 1fr; height: 1; color: #C9D1D9; }
    RuleItem #meta { height: 1;  color: #8B949E; padding: 0 0 0 3; }
    """

    def __init__(self, rule: FolderRule) -> None:
        super().__init__(id=f"rule-{rule.id}")
        self._rule = rule

    def compose(self) -> ComposeResult:
        status = _rule_status(self._rule)
        tools  = "  ".join(self._rule.allowed_tools)
        with Horizontal(id="top-row"):
            yield Label(_status_dot(status), id="dot")
            yield Label(self._rule.name, id="name")
        yield Label(f"every {self._rule.interval_hours}h  ·  {tools}", id="meta")

    def set_status(self, status: str) -> None:
        self.query_one("#dot", Label).update(_status_dot(status))


# ---------------------------------------------------------------------------
# FolderRulesSection
# ---------------------------------------------------------------------------

class FolderRulesSection(Widget):
    DEFAULT_CSS = """
    FolderRulesSection {
        height: auto;
        width: 100%;
        layout: vertical;
    }
    """

    def compose(self) -> ComposeResult:
        yield PaneHeader("Folder Rules", "ctrl+r")

    def load_rules(self, rules: list[FolderRule]) -> None:
        for item in list(self.query(RuleItem)):
            item.remove()
        for rule in rules:
            self.mount(RuleItem(rule))

    def update_rule_status(self, rule_id: str, status: str) -> None:
        try:
            self.query_one(f"#rule-{rule_id}", RuleItem).set_status(status)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# AuditLogSection
# ---------------------------------------------------------------------------

class AuditLogSection(Widget):
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

    def append_entry(self, tool: str, result: str) -> None:
        ts   = datetime.now().strftime("%H:%M")
        line = f"[#8B949E]{ts}[/]  {_tool_chip(tool)}  [#C9D1D9]{result}[/]"
        self.query_one("#log", RichLog).write(line)


# ---------------------------------------------------------------------------
# SidebarWidget
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

    def load_rules(self, rules: list[FolderRule]) -> None:
        self.query_one(FolderRulesSection).load_rules(rules)

    def update_rule_status(self, rule_id: str, status: str) -> None:
        self.query_one(FolderRulesSection).update_rule_status(rule_id, status)

    def append_audit_entry(self, tool: str, result: str) -> None:
        self.query_one(AuditLogSection).append_entry(tool, result)

    def focus_audit_log(self) -> None:
        self.query_one("#log", RichLog).focus()

    def focus_rules(self) -> None:
        self.query_one(FolderRulesSection).focus()
