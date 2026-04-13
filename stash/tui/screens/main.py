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
from textual.widgets import Footer

from stash.tui.widgets.chat import ChatWidget
from stash.tui.widgets.sidebar import SidebarWidget
from stash.tui.widgets.title_bar import TitleBar


class MainScreen(Screen):
    DEFAULT_CSS = """
    MainScreen {
        layout: vertical;
    }
    MainScreen #main-columns {
        width: 100%;
        height: 1fr;
        layout: horizontal;
    }
    MainScreen #chat-col {
        width: 1fr;
        height: 100%;
    }
    MainScreen #sidebar-col {
        width: 44;
        height: 100%;
    }
    """

    def __init__(self, model: str = "") -> None:
        super().__init__()
        self._model = model

    def compose(self) -> ComposeResult:
        yield TitleBar(model=self._model)
        with Horizontal(id="main-columns"):
            with Vertical(id="chat-col"):
                yield ChatWidget()
            with Vertical(id="sidebar-col"):
                yield SidebarWidget()
        yield Footer()

    def on_screen_resume(self) -> None:
        """Focus the chat input whenever this screen returns to the foreground."""
        self.call_after_refresh(self._restore_focus)

    def _restore_focus(self) -> None:
        try:
            for inp in self.query("Input"):
                if not inp.disabled:
                    inp.focus()
                    return
        except Exception:
            pass
