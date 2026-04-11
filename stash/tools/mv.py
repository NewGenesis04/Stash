"""
mv — move a file or directory from src to dst.
"""

from pathlib import Path

from pydantic import BaseModel


class MvArgs(BaseModel):
    src: str
    dst: str


SCHEMA = {
    "name": "mv",
    "description": "Move a file or directory from src to dst.",
    "args": MvArgs.model_json_schema(),
}


def mv_tool(src: str, dst: str) -> str:
    s, d = Path(src), Path(dst)
    if not s.exists():
        return f"error: source does not exist: {src}"
    if d.exists():
        return f"error: destination already exists: {dst}"
    s.rename(d)
    return f"moved {src} → {dst}"
