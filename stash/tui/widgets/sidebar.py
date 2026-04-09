"""
Sidebar widget — audit log, rules list, and status indicators.

Shows:
  - Ollama status
  - Scheduler status + active rule (if any)
  - List of folder rules with last-run status
  - Recent audit log entries
"""

from textual.app import ComposeResult
from textual.widget import Widget


class SidebarWidget(Widget):
    def compose(self) -> ComposeResult:
        raise NotImplementedError
