"""
rename — rename a file or directory within the same parent directory.
"""

from pathlib import Path

from pydantic import BaseModel


class RenameArgs(BaseModel):
    path: str
    new_name: str


SCHEMA = {
    "name": "rename",
    "description": "Rename a file or directory. new_name is just the name, not a full path.",
    "args": RenameArgs.model_json_schema(),
}


def rename_tool(path: str, new_name: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"error: path does not exist: {path}"
    dst = p.parent / new_name
    if dst.exists():
        return f"error: destination already exists: {dst}"
    p.rename(dst)
    return f"renamed {p.name} → {new_name}"
