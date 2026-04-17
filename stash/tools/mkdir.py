"""
mkdir — create a directory (and any missing parents).
"""

from pathlib import Path

from pydantic import BaseModel


class MkdirArgs(BaseModel):
    path: str


SCHEMA = {
    "type": "function",
    "function": {
        "name": "mkdir",
        "description": "Create a directory at the given path, including any missing parents.",
        "parameters": MkdirArgs.model_json_schema(),
    },
}


def mkdir_tool(path: str) -> str:
    """
    Create a directory at the given path, including any missing parents.

    Safe to call even if the directory already exists — it will not raise an error.

    Args:
        path: Absolute path of the directory to create.
              Intermediate parent directories are created automatically.

    Returns:
        Confirmation string "created {path}" on success.
    """
    Path(path).mkdir(parents=True, exist_ok=True)
    return f"created {path}"
