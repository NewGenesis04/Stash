"""
rm — delete a file. Does not delete directories.
"""

from pathlib import Path

from pydantic import BaseModel


class RmArgs(BaseModel):
    path: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "rm",
        "description": "Delete a file at the given path. Will not delete directories.",
        "parameters": RmArgs.model_json_schema(),
    },
}


def rm_tool(path: str) -> str:
    """
    Delete a file at the given path.

    This tool will not delete directories. Use it only for individual files.
    There is no recycle bin — deletion is permanent.

    Args:
        path: Absolute path of the file to delete.

    Returns:
        Confirmation string "deleted {path}" on success.
        Returns an error string if the path does not exist or is a directory.
    """
    p = Path(path)
    if not p.exists():
        return f"error: path does not exist: {path}"
    if p.is_dir():
        return f"error: will not delete a directory: {path}"
    p.unlink()
    return f"deleted {path}"
