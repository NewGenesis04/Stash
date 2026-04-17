"""
Tests for SQLite and TinyDB persistence layers.

SQLite tests use an in-memory database — no temp files needed.
TinyDB tests use tmp_path since TinyDB requires a real file.
"""

import sqlite3

import pytest

import stash.persistence.sqlite as db
from stash.core.agent import ReActStep
from stash.persistence.tinydb import FolderRule, RulesDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """Fresh in-memory SQLite connection with migrations applied."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db._migrate(c)
    yield c
    c.close()


@pytest.fixture
def rules_db(tmp_path):
    """Fresh RulesDB backed by a temp file."""
    return RulesDB(tmp_path / "rules.json")


def _make_rule(**kwargs) -> FolderRule:
    defaults = {
        "id": "rule-1",
        "name": "Test Rule",
        "target_path": "/tmp/test",
        "instructions": "Do something",
        "allowed_tools": ["ls", "glob"],
        "interval_hours": 6,
    }
    return FolderRule(**{**defaults, **kwargs})


# ---------------------------------------------------------------------------
# SQLite — task_runs
# ---------------------------------------------------------------------------

class TestSQLiteRuns:
    def test_begin_run_creates_row(self, conn):
        db.begin_run(conn, "run-1", "sort my downloads")
        row = conn.execute("SELECT * FROM task_runs WHERE id = 'run-1'").fetchone()
        assert row is not None
        assert row["task"] == "sort my downloads"
        assert row["status"] == "running"
        assert row["rule_id"] is None
        assert row["finished_at"] is None

    def test_begin_run_with_rule_id(self, conn):
        db.begin_run(conn, "run-2", "cleanup", rule_id="rule-abc")
        row = conn.execute("SELECT * FROM task_runs WHERE id = 'run-2'").fetchone()
        assert row["rule_id"] == "rule-abc"

    def test_finish_run_updates_status(self, conn):
        db.begin_run(conn, "run-1", "task")
        db.finish_run(conn, "run-1", "completed")
        row = conn.execute("SELECT * FROM task_runs WHERE id = 'run-1'").fetchone()
        assert row["status"] == "completed"
        assert row["finished_at"] is not None

    def test_finish_run_failed_status(self, conn):
        db.begin_run(conn, "run-1", "task")
        db.finish_run(conn, "run-1", "failed")
        row = conn.execute("SELECT * FROM task_runs WHERE id = 'run-1'").fetchone()
        assert row["status"] == "failed"


# ---------------------------------------------------------------------------
# SQLite — react_steps
# ---------------------------------------------------------------------------

class TestSQLiteSteps:
    def test_log_thought_step(self, conn):
        db.begin_run(conn, "run-1", "task")
        step = ReActStep(type="thought", content="I should list the files")
        db.log_step(conn, "run-1", step)
        row = conn.execute("SELECT * FROM react_steps WHERE run_id = 'run-1'").fetchone()
        assert row["step_type"] == "thought"
        assert row["content"] == "I should list the files"
        assert row["tool"] is None

    def test_log_observation_step_with_tool_and_args(self, conn):
        db.begin_run(conn, "run-1", "task")
        step = ReActStep(
            type="observation",
            content="file.txt\nother.txt",
            tool="ls",
            args={"path": "/tmp"},
            result="file.txt\nother.txt",
        )
        db.log_step(conn, "run-1", step)
        row = conn.execute("SELECT * FROM react_steps WHERE run_id = 'run-1'").fetchone()
        assert row["tool"] == "ls"
        assert row["result"] == "file.txt\nother.txt"
        import json
        assert json.loads(row["args"]) == {"path": "/tmp"}

    def test_multiple_steps_ordered(self, conn):
        db.begin_run(conn, "run-1", "task")
        db.log_step(conn, "run-1", ReActStep(type="thought", content="step 1"))
        db.log_step(conn, "run-1", ReActStep(type="action", content="ls", tool="ls", args={}))
        db.log_step(conn, "run-1", ReActStep(type="response", content="done"))
        rows = conn.execute(
            "SELECT step_type FROM react_steps WHERE run_id = 'run-1' ORDER BY id"
        ).fetchall()
        types = [r["step_type"] for r in rows]
        assert types == ["thought", "action", "response"]


# ---------------------------------------------------------------------------
# SQLite — conversations
# ---------------------------------------------------------------------------

SESSION = "test-session-abc"

class TestSQLiteConversations:
    def test_add_and_retrieve_message(self, conn):
        db.add_message(conn, "user", "sort my downloads", session_id=SESSION)
        history = db.get_history(conn, session_id=SESSION)
        assert len(history) == 1
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "sort my downloads"

    def test_history_returned_in_chronological_order(self, conn):
        db.add_message(conn, "user", "first", session_id=SESSION)
        db.add_message(conn, "assistant", "second", session_id=SESSION)
        db.add_message(conn, "user", "third", session_id=SESSION)
        history = db.get_history(conn, session_id=SESSION)
        assert [h["content"] for h in history] == ["first", "second", "third"]

    def test_history_scoped_by_rule_id(self, conn):
        db.add_message(conn, "user", "rule msg", rule_id="rule-1")
        db.add_message(conn, "user", "general msg", session_id=SESSION)
        rule_history = db.get_history(conn, rule_id="rule-1")
        chat_history = db.get_history(conn, session_id=SESSION)
        assert len(rule_history) == 1
        assert rule_history[0]["content"] == "rule msg"
        assert len(chat_history) == 1
        assert chat_history[0]["content"] == "general msg"

    def test_chat_history_isolated_between_sessions(self, conn):
        db.add_message(conn, "user", "session A msg", session_id="session-a")
        db.add_message(conn, "user", "session B msg", session_id="session-b")
        assert db.get_history(conn, session_id="session-a")[0]["content"] == "session A msg"
        assert db.get_history(conn, session_id="session-b")[0]["content"] == "session B msg"
        assert len(db.get_history(conn, session_id="session-a")) == 1

    def test_history_limit(self, conn):
        for i in range(10):
            db.add_message(conn, "user", f"msg {i}", session_id=SESSION)
        history = db.get_history(conn, session_id=SESSION, limit=3)
        assert len(history) == 3
        # should be the most recent 3, in chronological order
        assert history[-1]["content"] == "msg 9"


# ---------------------------------------------------------------------------
# TinyDB — RulesDB
# ---------------------------------------------------------------------------

class TestRulesDB:
    def test_upsert_and_get(self, rules_db):
        rule = _make_rule()
        rules_db.upsert(rule)
        retrieved = rules_db.get("rule-1")
        assert retrieved is not None
        assert retrieved.name == "Test Rule"
        assert retrieved.interval_hours == 6

    def test_get_nonexistent_returns_none(self, rules_db):
        assert rules_db.get("ghost-id") is None

    def test_all_returns_all_rules(self, rules_db):
        rules_db.upsert(_make_rule(id="rule-1", name="First"))
        rules_db.upsert(_make_rule(id="rule-2", name="Second"))
        all_rules = rules_db.all()
        assert len(all_rules) == 2
        names = {r.name for r in all_rules}
        assert names == {"First", "Second"}

    def test_upsert_updates_existing(self, rules_db):
        rule = _make_rule()
        rules_db.upsert(rule)
        updated = _make_rule(name="Updated Name")
        rules_db.upsert(updated)
        assert rules_db.get("rule-1").name == "Updated Name"
        assert len(rules_db.all()) == 1  # still one rule, not two

    def test_delete_removes_rule(self, rules_db):
        rules_db.upsert(_make_rule())
        rules_db.delete("rule-1")
        assert rules_db.get("rule-1") is None
        assert rules_db.all() == []

    def test_delete_nonexistent_is_silent(self, rules_db):
        rules_db.delete("ghost-id")  # should not raise

    def test_update_last_run(self, rules_db):
        rules_db.upsert(_make_rule())
        rules_db.update_last_run("rule-1", "completed")
        rule = rules_db.get("rule-1")
        assert rule.last_run_status == "completed"
        assert rule.last_run is not None

    def test_empty_db_returns_empty_list(self, rules_db):
        assert rules_db.all() == []

    def test_rule_fields_round_trip(self, rules_db):
        """All FolderRule fields survive a write/read cycle."""
        rule = _make_rule(
            allowed_tools=["ls", "mv", "rm"],
            interval_hours=12,
            enabled=False,
        )
        rules_db.upsert(rule)
        retrieved = rules_db.get("rule-1")
        assert retrieved.allowed_tools == ["ls", "mv", "rm"]
        assert retrieved.interval_hours == 12
        assert retrieved.enabled is False
