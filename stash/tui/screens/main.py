"""
Main screen — primary layout of the Stash TUI.

Three-pane layout:
  left   — Chat widget (task input + live ReAct stream)
  center — Plan approval panel
  right  — Sidebar (audit log, rules list, status indicators)
"""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header

from stash.tui.widgets.chat import ChatWidget
from stash.tui.widgets.plan_approval import PlanApprovalWidget
from stash.tui.widgets.sidebar import SidebarWidget


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="left"):
                yield ChatWidget()
            with Vertical(id="center"):
                yield PlanApprovalWidget()
            with Vertical(id="right"):
                yield SidebarWidget()
        yield Footer()
