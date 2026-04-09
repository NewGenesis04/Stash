"""
Callback chain — hooks that fire before and after every tool call.

Add callbacks without touching any other layer. Default set:
  - AuditLogger   → writes to SQLite
  - TUIUpdater    → posts ReactStepReady to StashApp via call_from_thread
  - StatusTracker → updates last_run / last_run_status on rule runs
"""

import logging
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from stash.tui.app import StashApp

log = logging.getLogger(__name__)


class Callback(Protocol):
    def on_before(self, tool: str, args: dict) -> None: ...
    def on_after(self, tool: str, args: dict, result: str) -> None: ...
    def on_error(self, tool: str, args: dict, error: Exception) -> None: ...


class AuditLogger:
    """Writes every tool call to the SQLite audit log."""

    def on_before(self, tool: str, args: dict) -> None:
        raise NotImplementedError

    def on_after(self, tool: str, args: dict, result: str) -> None:
        raise NotImplementedError

    def on_error(self, tool: str, args: dict, error: Exception) -> None:
        raise NotImplementedError


class TUIUpdater:
    """
    Bridges sync tool execution → async Textual app.
    Posts ReactStepReady after each tool call so the chat pane updates live.
    """

    def __init__(self, app: "StashApp") -> None:
        self._app = app

    def on_before(self, tool: str, args: dict) -> None:
        pass

    def on_after(self, tool: str, args: dict, result: str) -> None:
        from stash.core.agent import ReActStep
        from stash.tui.app import ReactStepReady
        step = ReActStep(type="observation", content=result, tool=tool, args=args, result=result)
        self._app.call_from_thread(self._app.post_message, ReactStepReady(step))

    def on_error(self, tool: str, args: dict, error: Exception) -> None:
        log.error("tool error", extra={"tool": tool, "args": args, "error": str(error)})


class StatusTracker:
    """Updates last_run and last_run_status in TinyDB after scheduled rule runs."""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id

    def on_before(self, tool: str, args: dict) -> None:
        pass

    def on_after(self, tool: str, args: dict, result: str) -> None:
        raise NotImplementedError

    def on_error(self, tool: str, args: dict, error: Exception) -> None:
        raise NotImplementedError
