"""
Stash TUI — Textual app root.

Owns all Textual message types that cross layer boundaries. Agent and
Scheduler push updates here via app.call_from_thread(app.post_message, ...).
Nothing in tui/ touches the filesystem directly — all side effects go
through core/ and persistence/.
"""

import logging
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.message import Message

from stash.core.agent import ReActStep
from stash.tui.screens.main import MainScreen

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cross-layer message types
# ---------------------------------------------------------------------------

class ReactStepReady(Message):
    """Posted by Agent (via TUIUpdater callback) as each step completes."""
    def __init__(self, step: ReActStep) -> None:
        self.step = step
        super().__init__()


class RuleCompleted(Message):
    """Posted by Scheduler after a scheduled rule finishes."""
    def __init__(self, rule_id: str, status: str) -> None:
        self.rule_id = rule_id
        self.status = status
        super().__init__()


class OllamaStatusChanged(Message):
    """Posted by health check if Ollama availability changes."""
    def __init__(self, available: bool) -> None:
        self.available = available
        super().__init__()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class StashApp(App):
    TITLE = "Stash"
    SUB_TITLE = "local-first file agent"
    THEME = "nord"

    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, config: dict) -> None:
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield MainScreen()

    # --- cross-layer message handlers ---

    def on_react_step_ready(self, message: ReactStepReady) -> None:
        raise NotImplementedError

    def on_rule_completed(self, message: RuleCompleted) -> None:
        log.info("rule completed", extra={"rule_id": message.rule_id, "status": message.status})
        raise NotImplementedError

    def on_ollama_status_changed(self, message: OllamaStatusChanged) -> None:
        raise NotImplementedError
