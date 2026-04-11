"""
mkdir — create a directory (and any missing parents).
"""

from pathlib import Path

from pydantic import BaseModel


class MkdirArgs(BaseModel):
    path: str


SCHEMA = {
    "name": "mkdir",
    "description": "Create a directory at the given path, including any missing parents.",
    "args": MkdirArgs.model_json_schema(),
}


def mkdir_tool(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return f"created {path}"
