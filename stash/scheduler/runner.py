"""
Scheduler — APScheduler setup, job registration, and live rescheduling.

Runs in-process alongside the Textual app. Holds a reference to StashApp
and posts RuleCompleted messages via call_from_thread after each job finishes.
Each enabled FolderRule gets an interval job registered on boot.
Changing an interval through the TUI reschedules the job live — no restart.
"""

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from stash.persistence.tinydb import FolderRule, RulesDB

if TYPE_CHECKING:
    from stash.tui.app import StashApp

log = logging.getLogger(__name__)


class StashScheduler:
    def __init__(self, rules_db: RulesDB, app: "StashApp") -> None:
        self._db = rules_db
        self._app = app
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        for rule in self._db.all():
            if rule.enabled:
                self._register(rule)
        self._scheduler.start()
        log.info("scheduler started")

    def reschedule(self, rule: FolderRule) -> None:
        raise NotImplementedError

    def remove(self, rule_id: str) -> None:
        raise NotImplementedError

    def _register(self, rule: FolderRule) -> None:
        self._scheduler.add_job(
            self._run_rule,
            "interval",
            hours=rule.interval_hours,
            id=rule.id,
            args=[rule.id],
        )
        log.info("rule registered", extra={"rule_id": rule.id, "interval_hours": rule.interval_hours})

    def _run_rule(self, rule_id: str) -> None:
        from stash.tui.app import RuleCompleted
        log.info("rule fired", extra={"rule_id": rule_id})
        try:
            raise NotImplementedError
        except Exception as e:
            log.error("rule failed", extra={"rule_id": rule_id, "error": str(e)})
            self._app.call_from_thread(
                self._app.post_message, RuleCompleted(rule_id, "failed")
            )
