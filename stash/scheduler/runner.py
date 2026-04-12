"""
Scheduler — APScheduler setup, job registration, and live rescheduling.

Runs in-process alongside the Textual app. Each enabled FolderRule gets an
interval job on boot. Jobs are isolated — each run opens its own SQLite
connection and builds its own Agent instance. The blocking agent call runs
in a thread pool executor so the asyncio event loop (and TUI) stay responsive.

max_instances=1 per job prevents concurrent runs of the same rule.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from stash.core.agent import Agent
from stash.core.callbacks import AuditLogger, TUIUpdater, StatusTracker
from stash.core.registry import ToolRegistry
from stash.persistence.tinydb import FolderRule, RulesDB
import stash.persistence.sqlite as db

if TYPE_CHECKING:
    from stash.tui.app import StashApp

log = logging.getLogger(__name__)


class StashScheduler:
    def __init__(
        self,
        rules_db: RulesDB,
        app: "StashApp",
        tool_registry: ToolRegistry,
        tool_schemas: list[dict],
    ) -> None:
        self._rules_db = rules_db
        self._app = app
        self._tool_registry = tool_registry
        self._tool_schemas = tool_schemas
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        for rule in self._rules_db.all():
            if rule.enabled:
                self._register(rule)
        self._scheduler.start()
        log.info("scheduler.started", extra={"job_count": len(self._scheduler.get_jobs())})

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")

    def reschedule(self, rule: FolderRule) -> None:
        job = self._scheduler.get_job(rule.id)
        if job:
            self._scheduler.remove_job(rule.id)
            log.debug("scheduler.job_removed", extra={"rule_id": rule.id})

        if rule.enabled:
            self._register(rule)
            log.info("scheduler.rescheduled", extra={"rule_id": rule.id, "interval_hours": rule.interval_hours})
        else:
            log.info("scheduler.job_disabled", extra={"rule_id": rule.id})

    def remove(self, rule_id: str) -> None:
        job = self._scheduler.get_job(rule_id)
        if job:
            self._scheduler.remove_job(rule_id)
            log.info("scheduler.job_removed", extra={"rule_id": rule_id})
        else:
            log.warning("scheduler.job_not_found", extra={"rule_id": rule_id})

    # ------------------------------------------------------------------

    def _register(self, rule: FolderRule) -> None:
        self._scheduler.add_job(
            self._run_rule,
            "interval",
            hours=rule.interval_hours,
            id=rule.id,
            args=[rule.id],
            max_instances=1,
            replace_existing=True,
        )
        log.info("scheduler.job_registered", extra={"rule_id": rule.id, "interval_hours": rule.interval_hours})

    async def _run_rule(self, rule_id: str) -> None:
        from stash.tui.app import RuleCompleted

        rule = self._rules_db.get(rule_id)
        if rule is None:
            log.warning("scheduler.rule_not_found", extra={"rule_id": rule_id})
            return

        run_id = str(uuid.uuid4())
        log.info("scheduler.run_start", extra={"rule_id": rule_id, "run_id": run_id, "task": rule.instructions})

        conn = db.connect(Path(self._app.config["data"]["dir"]).expanduser() / "stash.db")

        try:
            db.begin_run(conn, run_id, rule.instructions, rule_id)

            registry = self._tool_registry.session(rule.allowed_tools)
            callbacks = [
                AuditLogger(conn, run_id),
                TUIUpdater(self._app),
                StatusTracker(self._rules_db, rule_id),
            ]
            agent_config = {
                **self._app.config,
                "_db_conn": conn,
                "_rule_id": rule_id,
            }
            agent = Agent(agent_config, callbacks, self._tool_schemas)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, agent.run, rule.instructions, registry, run_id)

            db.finish_run(conn, run_id, "completed")
            self._rules_db.update_last_run(rule_id, "completed")
            log.info("scheduler.run_complete", extra={"rule_id": rule_id, "run_id": run_id})
            self._app.call_from_thread(self._app.post_message, RuleCompleted(rule_id, "completed"))

        except Exception as e:
            log.error("scheduler.run_failed", extra={"rule_id": rule_id, "run_id": run_id, "error": str(e)}, exc_info=True)
            db.finish_run(conn, run_id, "failed")
            self._rules_db.update_last_run(rule_id, "failed")
            self._app.call_from_thread(self._app.post_message, RuleCompleted(rule_id, "failed"))

        finally:
            conn.close()
