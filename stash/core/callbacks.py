"""
Callback chain — hooks that fire before and after every tool call.

Add callbacks without touching any other layer. Default set:
  - AuditLogger   → writes to SQLite
  - TUIUpdater    → posts ReactStepReady to StashApp via call_from_thread
  - StatusTracker → updates last_run / last_run_status on rule runs
"""

import logging
import sqlite3
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from stash.tui.app import StashApp
    from stash.persistence.tinydb import RulesDB

log = logging.getLogger(__name__)


class Callback(Protocol):
    def on_before(self, tool: str, args: dict) -> None: ...
    def on_after(self, tool: str, args: dict, result: str) -> None: ...
    def on_error(self, tool: str, args: dict, error: Exception) -> None: ...


class AuditLogger:
    """Writes every tool call to the SQLite audit log."""

    def __init__(self, conn: "sqlite3.Connection", run_id: str) -> None:
        self._conn = conn
        self._run_id = run_id

    def on_before(self, tool: str, args: dict) -> None:
        pass

    def on_after(self, tool: str, args: dict, result: str) -> None:
        from stash.core.agent import ReActStep
        import stash.persistence.sqlite as db
        step = ReActStep(type="observation", content=result, tool=tool, args=args, result=result)
        db.log_step(self._conn, self._run_id, step)

    def on_error(self, tool: str, args: dict, error: Exception) -> None:
        from stash.core.agent import ReActStep
        import stash.persistence.sqlite as db
        step = ReActStep(type="observation", content=str(error), tool=tool, args=args, result=str(error))
        db.log_step(self._conn, self._run_id, step)
        db.finish_run(self._conn, self._run_id, "failed")


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
    """Marks a rule's last run as failed in TinyDB if a tool errors mid-run."""

    def __init__(self, rules_db: "RulesDB", rule_id: str) -> None:
        self._db = rules_db
        self._rule_id = rule_id

    def on_before(self, tool: str, args: dict) -> None:
        pass

    def on_after(self, tool: str, args: dict, result: str) -> None:
        pass

    def on_error(self, tool: str, args: dict, error: Exception) -> None:
        self._db.update_last_run(self._rule_id, "failed")
