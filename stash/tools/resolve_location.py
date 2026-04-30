"""
resolve_location — look up a registered folder by name or alias.
"""

from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from stash.persistence.tinydb import LocationsDB


class ResolveLocationArgs(BaseModel):
    name: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "resolve_location",
        "description": (
            "Resolve a folder name or alias to its absolute path using the location registry. "
            "Always call this before any operation that references a folder by name. "
            "If the name is not in the registry, the user will be prompted to pick and register the folder."
        ),
        "parameters": ResolveLocationArgs.model_json_schema(),
    },
    "readonly": True,
}


def make_resolve_location_tool(
    locations_db: LocationsDB,
    request_picker: Callable[[str], str | None],
) -> Callable[[str], str]:
    def resolve_location(name: str) -> str:
        entry = locations_db.resolve(name)
        if entry:
            p = Path(entry.path)
            if not p.exists():
                return (
                    f"error: '{name}' was registered at {entry.path} but that path no longer exists. "
                    "Ask the user to re-register it."
                )
            return entry.path
        path = request_picker(name)
        if path is None:
            return f"error: '{name}' is not in the location registry and the user cancelled."
        return path

    return resolve_location
