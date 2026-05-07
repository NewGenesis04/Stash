"""
SQLite persistence — audit log, task history, conversation history.

Schema
------
  react_steps   — every ReAct step from every run
  task_runs     — one row per agent invocation
  conversations — conversation history for context injection
"""

import json
import logging
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from stash.core.agent import ReActStep

log = logging.getLogger(__name__)


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS task_runs (
            id          TEXT PRIMARY KEY,
            rule_id     TEXT,
            task        TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'running',
            started_at  TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS react_steps (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id    TEXT    NOT NULL REFERENCES task_runs(id),
            step_type TEXT    NOT NULL,
            content   TEXT    NOT NULL,
            tool      TEXT,
            args      TEXT,
            result    TEXT,
            timestamp TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id    TEXT,
            session_id TEXT,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL,
            timestamp  TEXT NOT NULL
        );
    """)
    # Migrate existing DBs that predate the session_id column.
    try:
        conn.execute("ALTER TABLE conversations ADD COLUMN session_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()


def begin_run(conn: sqlite3.Connection, run_id: str, task: str, rule_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO task_runs (id, rule_id, task, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (run_id, rule_id, task, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    log.debug("sqlite.begin_run", extra={"run_id": run_id, "rule_id": rule_id})


def finish_run(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute(
        "UPDATE task_runs SET status = ?, finished_at = ? WHERE id = ?",
        (status, datetime.now(UTC).isoformat(), run_id),
    )
    conn.commit()
    log.debug("sqlite.finish_run", extra={"run_id": run_id, "status": status})


def log_step(conn: sqlite3.Connection, run_id: str, step: ReActStep) -> None:
    conn.execute(
        """
        INSERT INTO react_steps (run_id, step_type, content, tool, args, result, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            step.type,
            step.content,
            step.tool,
            json.dumps(step.args) if step.args is not None else None,
            step.result,
            step.timestamp,
        ),
    )
    conn.commit()
    log.debug("sqlite.log_step", extra={"run_id": run_id, "step_type": step.type, "tool": step.tool})


def add_message(
    conn: sqlite3.Connection,
    role: str,
    content: str,
    rule_id: str | None = None,
    session_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO conversations (rule_id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
        (rule_id, session_id, role, content, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    log.debug("sqlite.add_message", extra={"rule_id": rule_id, "session_id": session_id, "role": role})


def get_history(
    conn: sqlite3.Connection,
    rule_id: str | None = None,
    session_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    if rule_id is not None:
        # Rule-scoped: return all history for this rule across all sessions.
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE rule_id = ? ORDER BY id DESC LIMIT ?",
            (rule_id, limit),
        ).fetchall()
    else:
        if session_id is None:
            log.warning("sqlite.get_history_no_session_id")
            return []
        # Chat: scoped to the current session only.
        # Uses = (not IS) so that a None session_id can never match NULL rows.
        rows = conn.execute(
            "SELECT role, content FROM conversations WHERE rule_id IS NULL AND session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    log.debug("sqlite.get_history", extra={"rule_id": rule_id, "session_id": session_id, "limit": limit, "returned": len(rows)})
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
