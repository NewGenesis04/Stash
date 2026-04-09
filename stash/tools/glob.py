"""
glob — find files matching a pattern.
"""

from pydantic import BaseModel


class GlobArgs(BaseModel):
    pattern: str
    base_path: str = "."


SCHEMA = {
    "name": "glob",
    "description": "Find files matching a glob pattern, relative to base_path.",
    "args": GlobArgs.model_json_schema(),
}


def glob_tool(pattern: str, base_path: str = ".") -> str:
    raise NotImplementedError
