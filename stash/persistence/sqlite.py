"""
SQLite persistence — audit log, task history, conversation history.

Schema
------
  react_steps   — every ReAct step from every run
  task_runs     — one row per agent invocation
  conversations — conversation history for context injection
"""

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from stash.core.agent import ReActStep


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.executescript("""
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
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id   TEXT,
            role      TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """)
    conn.commit()


def begin_run(conn: sqlite3.Connection, run_id: str, task: str, rule_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO task_runs (id, rule_id, task, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (run_id, rule_id, task, datetime.now(UTC).isoformat()),
    )
    conn.commit()


def finish_run(conn: sqlite3.Connection, run_id: str, status: str) -> None:
    conn.execute(
        "UPDATE task_runs SET status = ?, finished_at = ? WHERE id = ?",
        (status, datetime.now(UTC).isoformat(), run_id),
    )
    conn.commit()


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


def add_message(conn: sqlite3.Connection, role: str, content: str, rule_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO conversations (rule_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (rule_id, role, content, datetime.now(UTC).isoformat()),
    )
    conn.commit()


def get_history(conn: sqlite3.Connection, rule_id: str | None = None, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM conversations WHERE rule_id IS ? ORDER BY id DESC LIMIT ?",
        (rule_id, limit),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
