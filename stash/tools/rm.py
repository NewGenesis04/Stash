"""
rm — delete a file. Does not delete directories.
"""

from pathlib import Path

from pydantic import BaseModel


class RmArgs(BaseModel):
    path: str


SCHEMA = {
    "name": "rm",
    "description": "Delete a file at the given path. Will not delete directories.",
    "args": RmArgs.model_json_schema(),
}


def rm_tool(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"error: path does not exist: {path}"
    if p.is_dir():
        return f"error: will not delete a directory: {path}"
    p.unlink()
    return f"deleted {path}"
