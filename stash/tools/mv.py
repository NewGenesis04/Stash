"""
mv — move a file or directory from src to dst.
"""

from pathlib import Path

from pydantic import BaseModel


class MvArgs(BaseModel):
    src: str
    dst: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "mv",
        "description": "Move a file or directory from src to dst.",
        "parameters": MvArgs.model_json_schema(),
    },
}


def mv_tool(src: str, dst: str) -> str:
    """
    Move a file or directory from src to dst.

    Args:
        src: Absolute path of the file or directory to move.
        dst: Absolute path of the intended destination.
             Must not already exist — this tool will not overwrite.

    Returns:
        Confirmation string "moved {src} → {dst}" on success.
        Returns an error string if the source does not exist or the destination
        already exists.
    """
    s, d = Path(src), Path(dst)
    if not s.exists():
        return f"error: source does not exist: {src}"
    if d.exists():
        return f"error: destination already exists: {dst}"
    s.rename(d)
    return f"moved {src} → {dst}"
