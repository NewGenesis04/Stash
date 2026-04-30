"""
TinyDB persistence — folder rules CRUD.

Each rule document matches the FolderRule schema. Rules are read by the
scheduler on boot and mutated through the TUI rule editor.
"""

import logging
from datetime import datetime, UTC
from pathlib import Path

from pydantic import BaseModel, Field
from tinydb import TinyDB, Query

log = logging.getLogger(__name__)


class LocationEntry(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    path: str
    added: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_verified: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class LocationsDB:
    def __init__(self, path: Path) -> None:
        self._db = TinyDB(path)
        self._table = self._db.table("locations")

    def all(self) -> list[LocationEntry]:
        return [LocationEntry(**doc) for doc in self._table.all()]

    def resolve(self, name: str) -> LocationEntry | None:
        needle = name.strip().lower()
        for doc in self._table.all():
            entry = LocationEntry(**doc)
            if entry.name.lower() == needle:
                return entry
            if any(a.strip().lower() == needle for a in entry.aliases):
                return entry
        return None

    def upsert(self, entry: LocationEntry) -> None:
        Location = Query()
        self._table.upsert(entry.model_dump(), Location.name == entry.name)
        log.debug("locations_db.upsert", extra={"name": entry.name, "path": entry.path})

    def delete(self, name: str) -> None:
        Location = Query()
        self._table.remove(Location.name == name)
        log.debug("locations_db.delete", extra={"name": name})

    def verify(self, entry: LocationEntry) -> tuple[bool, LocationEntry]:
        exists = Path(entry.path).exists()
        updated = entry.model_copy(update={"last_verified": datetime.now(UTC).isoformat()})
        if exists:
            self.upsert(updated)
        return exists, updated


class FolderRule(BaseModel):
    id: str
    name: str
    target_path: str
    instructions: str
    allowed_tools: list[str]
    interval_hours: int
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_run: str | None = None
    last_run_status: str | None = None


class RulesDB:
    def __init__(self, path: Path) -> None:
        self._db = TinyDB(path)
        self._table = self._db.table("rules")

    def all(self) -> list[FolderRule]:
        return [FolderRule(**doc) for doc in self._table.all()]

    def get(self, rule_id: str) -> FolderRule | None:
        Rule = Query()
        doc = self._table.get(Rule.id == rule_id)
        return FolderRule(**doc) if doc else None

    def upsert(self, rule: FolderRule) -> None:
        Rule = Query()
        self._table.upsert(rule.model_dump(), Rule.id == rule.id)
        log.debug("rules_db.upsert", extra={"rule_id": rule.id, "name": rule.name})

    def delete(self, rule_id: str) -> None:
        Rule = Query()
        self._table.remove(Rule.id == rule_id)
        log.debug("rules_db.delete", extra={"rule_id": rule_id})

    def update_last_run(self, rule_id: str, status: str) -> None:
        Rule = Query()
        self._table.update(
            {"last_run": datetime.now(UTC).isoformat(), "last_run_status": status},
            Rule.id == rule_id,
        )
        log.debug("rules_db.update_last_run", extra={"rule_id": rule_id, "status": status})
