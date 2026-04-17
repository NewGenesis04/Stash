"""
ls — list the contents of a directory.
"""

from pathlib import Path

from pydantic import BaseModel


class LsArgs(BaseModel):
    path: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "ls",
        "description": "List the files and directories at the given path.",
        "parameters": LsArgs.model_json_schema(),
    },
    "readonly": True,
}


def ls_tool(path: str) -> str:
    """
    List the contents of a directory.

    Args:
        path: Absolute path to the directory to list.

    Returns:
        Newline-separated list of entry names. Directories are suffixed with '/'.
        Directories are listed before files; both groups are sorted alphabetically.
        Returns "(empty)" if the directory exists but contains no entries.
        Returns an error string if the path does not exist or is not a directory.
    """
    p = Path(path)
    if not p.exists():
        return f"error: path does not exist: {path}"
    if not p.is_dir():
        return f"error: not a directory: {path}"
    entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name))
    if not entries:
        return "(empty)"
    return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries)
