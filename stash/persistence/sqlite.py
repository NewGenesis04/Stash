"""
SQLite persistence — audit log, task history, conversation history.

Schema
------
  react_steps   — every ReAct step from every run
  task_runs     — one row per agent invocation
  conversations — conversation history for context injection
"""

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    raise NotImplementedError
