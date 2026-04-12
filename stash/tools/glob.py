"""
glob — find files matching a pattern.
"""

from pathlib import Path

from pydantic import BaseModel


class GlobArgs(BaseModel):
    pattern: str
    base_path: str = "."


SCHEMA = {
    "name": "glob",
    "description": "Find files matching a glob pattern, relative to base_path.",
    "args": GlobArgs.model_json_schema(),
    "readonly": True,
}


def glob_tool(pattern: str, base_path: str = ".") -> str:
    base = Path(base_path)
    if not base.exists():
        return f"error: base_path does not exist: {base_path}"
    matches = sorted(base.glob(pattern))
    if not matches:
        return "(no matches)"
    return "\n".join(str(m) for m in matches)
