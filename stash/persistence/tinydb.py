"""
TinyDB persistence — folder rules CRUD.

Each rule document matches the FolderRule schema. Rules are read by the
scheduler on boot and mutated through the TUI rule editor.
"""

from datetime import datetime, UTC
from pathlib import Path

from pydantic import BaseModel, Field
from tinydb import TinyDB, Query


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
        raise NotImplementedError

    def get(self, rule_id: str) -> FolderRule | None:
        raise NotImplementedError

    def upsert(self, rule: FolderRule) -> None:
        raise NotImplementedError

    def delete(self, rule_id: str) -> None:
        raise NotImplementedError

    def update_last_run(self, rule_id: str, status: str) -> None:
        raise NotImplementedError
