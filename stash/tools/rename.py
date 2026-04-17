"""
rename — rename a file or directory within the same parent directory.
"""

from pathlib import Path

from pydantic import BaseModel


class RenameArgs(BaseModel):
    path: str
    new_name: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "rename",
        "description": "Rename a file or directory. new_name is just the name, not a full path.",
        "parameters": RenameArgs.model_json_schema(),
    },
}


def rename_tool(path: str, new_name: str) -> str:
    """
    Rename a file or directory within its current parent directory.

    This tool only changes the name — it does not move the entry to a different
    directory. To move, use mv instead.

    Args:
        path:     Absolute path of the file or directory to rename.
        new_name: The new name only (not a full path). Must not include path
                  separators. The renamed entry stays in the same directory.

    Returns:
        Confirmation string "renamed {old_name} → {new_name}" on success.
        Returns an error string if the path does not exist or a file with
        new_name already exists in the same directory.
    """
    p = Path(path)
    if not p.exists():
        return f"error: path does not exist: {path}"
    dst = p.parent / new_name
    if dst.exists():
        return f"error: destination already exists: {dst}"
    p.rename(dst)
    return f"renamed {p.name} → {new_name}"
